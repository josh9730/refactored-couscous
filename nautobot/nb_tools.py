import re
from enum import Enum
from typing import Any

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

    def guess_port_type(self, port_name: str, port_device_id: str) -> tuple[Any, str]:
        """Determine if given port is FrontPort, RearPort, or Interface. None is returned if not found
        from the nautobot get method.

        Return:
            port: Nautobot port object, one of Front, RearPort, Interface
            port_type: type of Nautobot port for the api
        """
        if port := self.nautobot.dcim.front_ports.get(
            device_id=port_device_id, name=port_name
        ):
            return port, "dcim.frontport"
        elif port := self.nautobot.dcim.rear_ports.get(
            device_id=port_device_id, name=port_name
        ):
            return port, "dcim.rearport"
        elif port := self.nautobot.dcim.interfaces.get(
            device_id=port_device_id, name=port_name
        ):
            return port, "dcim.interface"
        else:
            raise Exception("No matching Front/RearPort or Interface was found.")

    def _next_cable_id(self) -> int:
        """Get last used cabled ID (i.e. CLR increment)."""
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
    ) -> None:
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
    ) -> None:
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
    ) -> None:
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

    def create_jumper(
        self,
        site_code: str,
        device_1: str,
        device_1_port: str,
        device_2: str,
        device_2_port: str,
        label: str,
        jumper_type: Enum,
    ) -> None:
        site = self.nautobot.dcim.sites.get(name=site_code.upper())
        term_a_device = self.nautobot.dcim.devices.get(name=device_1, site=site.slug)
        term_b_device = self.nautobot.dcim.devices.get(name=device_2, site=site.slug)
        term_a_port, term_a_port_type = self.guess_port_type(
            device_1_port, term_a_device.id
        )
        term_b_port, term_b_port_type = self.guess_port_type(
            device_2_port, term_b_device.id
        )

        self.nautobot.dcim.cables.create(
            termination_a_id=term_a_port.id,
            termination_b_id=term_b_port.id,
            termination_a_type=term_a_port_type,
            termination_b_type=term_b_port_type,
            type=jumper_type.value,
            status="connected",
            label=label,
        )
        print(f"Created new cable: {label}")


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


@main.command()
def create_jumper(
    site_code: str = typer.Option(..., prompt="Site Code"),
    device_1: str = typer.Option(..., prompt="Device 1"),
    device_1_port: str = typer.Option(..., prompt="Device 1 Port"),
    device_2: str = typer.Option(..., prompt="Device 2"),
    device_2_port: str = typer.Option(..., prompt="Device 2 Port"),
    label: str = typer.Option(..., prompt="Cable Label"),
    jumper_type: JumperType = typer.Option(
        "smf", prompt="Jumper Type", case_sensitive=False
    ),
):
    args = locals()
    nautobot = NBTools()
    nautobot.create_jumper(*list(args.values()))


if __name__ == "__main__":
    main()
