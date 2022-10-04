from enum import Enum
from pickle import TRUE

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
def test():
    pass


if __name__ == "__main__":
    main()
