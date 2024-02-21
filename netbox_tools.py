import csv

import keyring
import pynetbox
import requests
import typer
from rich import print
from rich.prompt import Prompt

app = typer.Typer(add_completion=False)


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
            "rack": nb.dcim.racks.get(name=device[11], site=site.slug).id,
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
                    device.append(err.error)
                    failed_devices.append(device)
                    print(f"[bold red]Failed to upload {device[0]}, re-attempt manually.")

    except FileNotFoundError:
        print(f"[bold red]Unable to find file: [white]{filename}")

    with open(failure_file, "w") as f:
        write = csv.writer(f)
        write.writerows(failed_devices)

    print("[green]Program finished!")


if __name__ == "__main__":
    app()
