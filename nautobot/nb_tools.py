import re
from enum import Enum

import keyring
import typer
import urllib3
from pynautobot import api

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

main = typer.Typer(
    add_completion=False,
)


class Tenants(str, Enum):
    CCC = "CCC"
    K12 = "K12"
    Library = "Library"
    CSU = "CSU"
    UC = "UC"
    UCHS = "UCHS"
    CAS = "CAS"
    Health = "Health"
    Independent = "Independent"


class JumperType(str, Enum):
    smf = "smf"
    mmf = "mmf"
    cop = "cop"


class PortType(str, Enum):
    lc = "lc"
    sc = "sc"


class NBTools:
    """Misc. Nautobot scripts"""

    def __init__(self):
        self.nautobot = api(
            url=keyring.get_password("nautobot_stage", "url"),
            token=keyring.get_password(
                "nautobot-stage", keyring.get_password("cas", "user") + "mfa"
            ),
        )
        self.nautobot.http_session.verify = False

    def _next_cable_id(self):
        """Get"""
        cables = self.nautobot.dcim.cables.all()
        cable_labels = tuple(map(lambda x: x.label, cables))
        trunk_cables = []
        for i in cable_labels:
            if i:
                label = re.search("--C[0-9]{4}$", i)
                try:
                    label.group()
                except AttributeError:
                    pass
                else:
                    trunk_cables.append(label.group())
        trunk_cables.sort()

        return int(trunk_cables[-1].split("--C")[1]) + 1

    def create_new_site(
        self, site_code: str, site_name: str, address: str, tenant: str
    ):
        tenant_id = self.nautobot.tenancy.tenants.get(slug=tenant.lower()).id
        new_site = self.nautobot.dcim.sites.create(
            name=site_code,
            status="active",
            region=self.nautobot.dcim.regions.get(slug="ca").id,
            description=site_name,
            tenant=tenant_id,
            physical_address=address,
        )
        print(f"Created new site {site_name}")

        self.nautobot.dcim.racks.create(
            site=new_site.id,
            name="CPE_RACK",
            tenant=tenant_id,
            status="active",
            role=self.nautobot.dcim.rack_roles.get(slug="associate").id,
            comments="# NOT A REAL RACK\nThis is an abstraction only, Associate racks are not tracked or managed by CENIC.",
        )
        print("Created CPE Rack")

    def update_simplex_panel(
        self,
        site_code: str,
        name: str,
        num_ports: int,
        port_type: str,
        jumper_type: str,
    ):
        site = self.nautobot.dcim.sites.get(name=site_code.upper())
        device = self.nautobot.dcim.devices.get(name=name, site=site.slug)

        for i in range(1, num_ports * 2, 2):
            port_name = f"Port {i}/{i+1} "
            rp = self.nautobot.dcim.rear_ports.create(
                device=device.id,
                type=port_type,
                positions=1,
                custom_fields={"jumper_type": jumper_type.upper()},
                name=f"Port {i}/{i+1} Rear",
            )
            print(f"Created port: {port_name+'Rear'}")
            self.nautobot.dcim.front_ports.create(
                device=device.id,
                rear_port=rp.id,
                type=port_type,
                custom_fields={"jumper_type": jumper_type.upper()},
                name=f"Port {i}/{i+1} Front",
            )
            print(f"Created port: {port_name+'Front'}")

    def connect_rear_ports(
        self, site_code: str, device_1_name: str, device_2_name: str, jumper_type: str
    ):
        site = self.nautobot.dcim.sites.get(name=site_code.upper())
        device_1 = self.nautobot.dcim.devices.get(name=device_1_name, site=site.slug)
        device_2 = self.nautobot.dcim.devices.get(name=device_2_name, site=site.slug)

        device_1_rp = self.nautobot.dcim.rear_ports.filter(device_id=device_1.id)
        device_2_rp = self.nautobot.dcim.rear_ports.filter(device_id=device_2.id)

        LAST_CABLE_ID = self._next_cable_id()
        for i in zip(device_1_rp, device_2_rp):
            cable_id = "C" + str(LAST_CABLE_ID).rjust(4, "0")
            cable_label = f"COM--{device_1.name}--{device_2.name}--{cable_id}"
            LAST_CABLE_ID += 1

            self.nautobot.dcim.cables.create(
                termination_a_id=i[0].id,
                termination_b_id=i[1].id,
                termination_a_type="dcim.rearport",
                termination_b_type="dcim.rearport",
                type=jumper_type,
                status="connected",
                label=cable_label,
            )
            print(f"Created new cable: {cable_label}")


@main.command()
def new_site(
    tenant: Tenants = typer.Argument(
        ...,
        case_sensitive=False,
        help="Select Tenant from choices, case-insensitve.",
    ),
    site_code: str = typer.Option(
        ..., prompt="Site Code", help="Unique site Code for new site."
    ),
    site_name: str = typer.Option(..., prompt="Site Name", help="Full site name."),
    address: str = typer.Option(..., prompt=True, help="Physical site address."),
):
    """Create a new site and CPE rack in Nautobot."""
    nautobot = NBTools()
    nautobot.create_new_site(site_code, site_name, address, tenant.value)


@main.command()
def update_simplex_panel(
    site_code: str = typer.Argument(..., help="Site Code"),
    name: str = typer.Argument(..., help="Device Name"),
    num_ports: int = typer.Argument(..., help="Total number of duplex ports."),
    port_type: PortType = typer.Argument("lc", case_sensitive=False),
    jumper_type: JumperType = typer.Argument("smf", case_sensitive=False),
):
    """Update a patch panel with simplex ports, i.e. 'Port 1/2 Front'."""
    nautobot = NBTools()
    nautobot.update_simplex_panel(
        site_code, name, num_ports, port_type.value, jumper_type.value
    )


@main.command()
def connect_rear_ports(
    site_code: str = typer.Argument(..., help="Site Code"),
    device_1: str = typer.Argument(..., help="Device 1"),
    device_2: str = typer.Argument(..., help="Device 2"),
    jumper_type: JumperType = typer.Argument("smf", case_sensitive=False),
):
    """Connect rear ports of a linked panel pair."""
    nautobot = NBTools()
    nautobot.connect_rear_ports(site_code, device_1, device_2, jumper_type.value)


if __name__ == "__main__":
    main()
