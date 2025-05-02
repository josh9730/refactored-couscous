import csv
import json
import re
from enum import Enum

import keyring
import pynetbox
import requests
import typer
import urllib3
from pynautobot import api
from rich import print
from rich.prompt import Prompt, IntPrompt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = typer.Typer(add_completion=False)


class PortType(str, Enum):
    rear = "rear"
    front = "front"
    iface = "iface"


class Segment(str, Enum):
    ccc = "CCC"
    k12 = "K12"
    uc = "UC"
    uchs = "UCHS"
    csu = "CSU"
    lib = "Library"


def get_auth() -> tuple[str, str]:
    url = keyring.get_password("netbox", "url")
    if not url:
        url = Prompt.ask("Enter NetBox URL")

    api_key = keyring.get_password("netbox", "api")
    if not api_key:
        api_key = Prompt.ask("Enter NetBox API Token", password=True)

    return url, api_key


def get_pynb() -> pynetbox:
    url, api_key = get_auth()
    return pynetbox.api(url, token=api_key)


def get_pynautobot() -> api:
    url = keyring.get_password("nautobot_stage", "url")
    token = keyring.get_password("nautobot_stage", keyring.get_password("cas", "user") + "mfa")
    return api(url=url, token=token, verify=False)


@app.command()
def post_asns() -> None:
    url, api_key = get_auth()
    url = url + "/api/"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }

    with open("asns.csv", "r") as f:
        """Import list of ASNs to NetBox and add to Site.

        - pynetbox does not support adding individual ASNs, used requests instead
        - NetBox does not allow adding sites during a CSV import
        asns: asn in col1, list of sites in col2
        """
        asns = csv.reader(f)
        for asn in asns:
            try:
                # post ASN
                asn_data = {"asn": asn[0], "rir": 1}
                asn_response = requests.post(url + "ipam/asns/", json=asn_data, headers=headers)
                asn_response.raise_for_status()
                asn_id = asn_response.json()["id"]

                # iterate over sites and add ASN to the Site object
                for site in asn[1].split(", "):
                    get_site = requests.get(url + f"dcim/sites/?slug={site.lower()}", headers=headers)
                    get_site.raise_for_status()
                    site_id = get_site.json()["results"][0]["id"]

                    site_data = {"asns": [asn_id]}
                    site_response = requests.patch(url + f"dcim/sites/{site_id}/", json=site_data, headers=headers)
                    site_response.raise_for_status()

            except (requests.HTTPError, IndexError):
                print("failed: ", asn[0])


@app.command()
def remove_all_devices() -> None:
    """Remove all Devices in NetBox one-by-one to avoid 504s."""
    nb = get_pynb()
    devices = nb.dcim.devices.all()  # can't bulk delete without a 504
    for device in list(devices):
        try:
            device.delete()
        except pynetbox.RequestError:
            print(f"[red]Failed to delete {device}, re-attempt manually.")


@app.command()
def bulk_add_ports(
    port_type: PortType = typer.Argument(...), csv_file: str = typer.Argument(..., help="CSV input file")
) -> None:
    def add_rp(rp: list[str]) -> None:
        device = nb.dcim.devices.get(name=rp[0])
        data = {
            "device": device.id,
            "name": rp[1],
            "label": rp[2],
            "type": rp[3].lower(),
            "positions": rp[4],
            "description": rp[5],
            "custon_fields": {"jumper_type": rp[6]},
        }
        port = nb.dcim.rear_ports.create(**data)
        port.save()

    def add_fp(fp: list[str]) -> None:
        device = nb.dcim.devices.get(name=fp[0])
        rp = nb.dcim.rear_ports.get(device=device.name, name=fp[4])
        data = {
            "device": device.id,
            "name": fp[1],
            "label": fp[2],
            "type": fp[3].lower(),
            "rear_port": rp.id,
            "rear_port_position": fp[5],
            "description": fp[6],
            "custon_fields": {"jumper_type": fp[7]},
        }
        port = nb.dcim.front_ports.create(**data)
        port.save()

    def add_iface(iface: list[str]) -> None:
        type_inputs = {
            "QSFP28 (100GE)": "100gbase-x-qsfp28",
            "Other": "other",
            "SFP+ (10GE)": "10gbase-x-sfpp",
            "1000BASE-T (1GE)": "1000base-t",
            "QSFP-DD (400GE)": "400gbase-x-qsfpdd",
            "SFP (1GE)": "1000base-x-sfp",
            "100BASE-TX (10/100ME)": "100base-tx",
            "X2 (10GE)": "10gbase-x-x2",
            "OC-192/STM-64": "sonet-oc192",
            "GBIC (1GE)": "1000base-x-gbic",
        }
        device = nb.dcim.devices.get(name=iface[0])
        data = {
            "device": device.id,
            "name": iface[1],
            "label": iface[2],
            "type": type_inputs[iface[4]],
            "description": iface[9],
        }
        iface = nb.dcim.interfaces.create(**data)
        iface.save()

    nb = get_pynb()
    failures = []
    with open(csv_file, "r") as f:
        ports = csv.reader(f)
        for port in ports:
            if port[0] == "device":
                continue
            try:
                match port_type.value:
                    case "rear":
                        add_rp(port)
                    case "front":
                        add_fp(port)
                    case "iface":
                        add_iface(port)
            except Exception as err:
                port.append(str(err))
                failures.append(port)

    with open("failures.csv", "w") as f:
        write = csv.writer(f)
        write.writerows(failures)


@app.command()
def migrate_cables():
    def create_cable(cable: dict) -> None:
        def find_netbox_port(term_type: str, term: dict):
            if term_type == "dcim.powerfeed":
                data = {"name": term["name"]}
            elif term_type == "circuits.circuittermination":
                circuit = netbox.circuits.circuits.get(cid=term["circuit"]["cid"])
                data = {"circuit_id": circuit.id, "term_side": term["term_side"]}
            else:
                site = nautobot.dcim.devices.get(id=term["device"]["id"]).site.slug
                data = {"device": term["device"]["name"], "name": term["name"], "site": site}
            match term_type:
                case "dcim.rearport":
                    return netbox.dcim.rear_ports.get(**data)
                case "dcim.frontport":
                    return netbox.dcim.front_ports.get(**data)
                case "dcim.interface":
                    return netbox.dcim.interfaces.get(**data)
                case "dcim.powerport":
                    return netbox.dcim.power_ports.get(**data)
                case "dcim.powerfeed":
                    return netbox.dcim.power_feeds.get(**data)
                case "dcim.poweroutlet":
                    return netbox.dcim.power_outlets.get(**data)
                case "circuits.circuittermination":
                    return netbox.circuits.circuit_terminations.get(**data)
                case _:
                    raise ValueError(f"Invalid term type: {term_type}")

        a_port = find_netbox_port(cable["termination_a_type"], cable["termination_a"])
        b_port = find_netbox_port(cable["termination_b_type"], cable["termination_b"])
        data = {
            "a_terminations": [{"object_id": a_port.id, "object_type": cable["termination_a_type"]}],
            "b_terminations": [{"object_id": b_port.id, "object_type": cable["termination_b_type"]}],
            "status": cable["status"]["value"],
            "label": cable["label"],
            "length": cable["length"],
            "length_unit": cable["length_unit"],
        }
        if re.match(r"COM--.*--C\d+", cable["label"]):
            data.update(tags=[mod_tag.id])

        c = netbox.dcim.cables.create(**data)
        c.save()

    nautobot = get_pynautobot()
    netbox = get_pynb()
    mod_tag = list(netbox.extras.tags.all())[0]  # modular tag is the only one

    failures = []

    # all_cables = nautobot.dcim.cables.all()
    # with open("failures.json", "r") as f:
    #     all_cables = json.load(f)
    with open("circuit_terms.json", "r") as f:
        all_cables = json.load(f)

    print(len(all_cables))
    for cable in all_cables:
        try:
            create_cable(cable)
        except Exception as err:
            cable = dict(cable)
            cable.update({"error": str(err)})
            failures.append(cable)

    print(len(failures))
    with open("failures.json", "w") as f:
        json.dump(failures, f)


@app.command()
def bulk_add_devices() -> None:
    """Create new devices in NetBox from a CSV file. Failures are dumped to a new csv for analysis"""

    def add_device(device: list[list[str]]) -> None:
        site = nb.dcim.sites.get(name=device[9])
        data = {
            "name": device[0],
            "role": nb.dcim.device_roles.get(name=device[1]).id,
            "device_type": nb.dcim.device_types.get(model=device[4]).id,
            "status": device[8].lower(),
            "site": site.id,
            "position": device[12],
            "face": device[13].lower(),
            "comments": device[14],
            "custom_fields": {
                "deployment_ticket": device[15],
                "facility_device_id": device[16],
                "oob_number": device[17],
            },
        }
        tenant_str = device[2]
        if tenant_str:
            data.update({"tenant": nb.tenancy.tenants.get(name=tenant_str).id})

        location_str = device[10]
        if location_str:
            location = nb.dcim.locations.get(name=location_str, site=site.slug)
            data.update({"rack": nb.dcim.racks.get(name=device[11], location=location.slug).id})
        else:
            data.update({"rack": nb.dcim.racks.get(name=device[11], site=site.slug).id})

        _ = nb.dcim.devices.create(**data)

    filename = "devices.csv"
    failure_file = "failures.csv"
    failed_devices = []

    nb = get_pynb()
    try:
        with open(filename) as f:
            devices = csv.reader(f)
            print("[green]Adding devices...")
            for device in devices:
                if device[0] == "name":  # header row
                    device.append("FAILURE REASON")
                    failed_devices.append(device)
                    continue

                try:
                    add_device(device)
                except pynetbox.RequestError as err:
                    if "already occupied" in err.error:
                        continue
                    else:
                        device.append(err.error)
                        failed_devices.append(device)
                        print(f"[bold red]Failed to upload {device[0]}, re-attempt manually.")
                except (IndexError, AttributeError, ValueError):
                    failed_devices.append(device)
                    print(f"[bold red]Failed to upload {device[0]}, re-attempt manually.")

    except FileNotFoundError:
        print(f"[bold red]Unable to find file: [white]{filename}")

    with open(failure_file, "w") as f:
        write = csv.writer(f)
        write.writerows(failed_devices)

    print("[green]Program finished!")


@app.command()
def move_remote_panels():
    """Move remote_panel relationships from Nautobot to NetBox as a custom field"""

    def get_relationships(url: str, token: str) -> list[dict[str, str]]:
        """Get relationship associations from Nautobot, parse for only source/dest IDs."""
        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }
        rels = requests.get(
            f"{url}/api/extras/relationship-associations/?limit=500", headers=headers, verify=False
        ).json()

        rel_list = []
        for rel in rels["results"]:
            if rel["relationship"]["name"] == "remote_panel":
                rel_list.append({"source_id": rel["source_id"], "dest_id": rel["destination_id"]})

        assert rels["count"] == len(rel_list)
        return rel_list

    def convert_id_to_name(nautobot, rel_list: list[dict[str, str]]) -> list[dict[str, str]]:
        """Convert UUIDs to device names."""
        output_list = []
        for rel in rel_list:
            source = nautobot.dcim.devices.get(id=rel["source_id"])
            dest = nautobot.dcim.devices.get(id=rel["dest_id"])

            if "cassette" not in source.device_role.slug:
                output_list.append({"source": source.name, "dest": dest.name})
        return output_list

    def update_netbox(netbox, rels_list: list[dict[str, str]]) -> None:
        """Create custom field link by finding the NetBox IDs."""
        for rel in rels_list:
            source = netbox.dcim.devices.get(name=rel["source"])
            dest = netbox.dcim.devices.get(name=rel["dest"])

            source.custom_fields["remote_panel"] = dest.id
            source.save()
            dest.custom_fields["remote_panel"] = source.id
            dest.save()

    url = keyring.get_password("nautobot_stage", "url")
    token = keyring.get_password("nautobot_stage", keyring.get_password("cas", "user") + "mfa")
    rel_list = get_relationships(url, token)

    nautobot = get_pynautobot()
    cleaned_rel_list = convert_id_to_name(nautobot, rel_list)

    netbox = get_pynb()
    update_netbox(netbox, cleaned_rel_list)


@app.command()
def make_c1100_conn(
    hostname: str = typer.Argument(..., help="C1100 hostname"),
    panel: str = typer.Argument(..., help="Cat6 panel name"),
    count: int = typer.Argument(16, help="Number of connections"),
):
    netbox = get_pynb()
    panel_ports = list(netbox.dcim.rear_ports.filter(device=panel))
    ports = list(netbox.dcim.console_server_ports.filter(device=hostname))

    for i in range(count):
        cable = netbox.dcim.cables.create(
            a_terminations=[{"object_id": panel_ports[i].id, "object_type": "dcim.rearport"}],
            b_terminations=[{"object_id": ports[i].id, "object_type": "dcim.consoleserverport"}],
            status="connected",
        )
        cable.save()


@app.command()
def make_simplex_ports(
    panel_name: str = typer.Argument(..., help="Panel name"),
    port_count: int = typer.Argument(..., help="Number of ports"),
):
    netbox = get_pynb()
    device = netbox.dcim.devices.get(name=panel_name)

    j = 0
    for i in range(port_count):
        i = j + 1
        j = i + 1

        rp = netbox.dcim.rear_ports.create(
            device=device.id,
            name=f"Ports {i},{j} Rear",
            type="sc",
            positions=1,
            custom_fields={"jumper_type": "SMF"},
        )
        rp.save()
        fp = netbox.dcim.front_ports.create(
            device=device.id,
            name=f"Ports {i},{j} Front",
            type="sc",
            rear_port=rp.id,
            rear_port_position=1,
            custom_fields={"jumper_type": "SMF"},
        )
        fp.save()

        print(f"Created port {i},{j}")


@app.command()
def new_site(segment: Segment = typer.Argument(...)):
    site_code = Prompt.ask("Unique Site Code")
    site_name = Prompt.ask("Full Site Name")
    address = Prompt.ask("Site Address")
    zip_code = IntPrompt.ask("ZIP Code")

    nb = get_pynb()
    tenant_id = nb.tenancy.tenants.get(name=segment).id

    new_site = nb.dcim.sites.create(
        name=site_code.upper(),
        slug=site_code.lower(),
        status="active",
        region=nb.dcim.regions.get(slug="ca").id,
        description=site_name,
        tenant=tenant_id,
        physical_address=address,
        custom_fields={"zip": zip_code},
    )
    print(f"Created new site {site_name}")

    nb.dcim.racks.create(
        site=new_site.id,
        name="CPE_RACK",
        tenant=tenant_id,
        status="active",
        role=nb.dcim.rack_roles.get(slug="associate").id,
        comments="# NOT A REAL RACK\nThis is an abstraction only, Associate racks are not tracked or managed by CENIC.",
        custom_field_data={"hub_rack": False},
    )
    print("Created CPE Rack")


if __name__ == "__main__":
    app()
