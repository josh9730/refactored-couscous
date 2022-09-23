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
            region=self.nautobot.dcim.regions.get(slug="california").id,
            description=site_name,
            tenant=tenant_id,
            physical_address=address,
        )

        self.nautobot.dcim.racks.create(
            site=new_site.id,
            name="CPE_RACK",
            tenant=tenant_id,
            status="active",
            role=self.nautobot.dcim.rack_roles.get(slug="associate"),
            comments="# NOT A REAL RACK\nThis is an abstraction only, Associate racks are not tracked or managed by CENIC.",
        )


@main.command()
def new_site(
    site_code: str = typer.Argument(..., help="Unique site Code for new site."),
    site_name: str = typer.Argument(..., help="Full site name."),
    address: str = typer.Argument(..., help="Physical site address."),
    tenant: Tenants = typer.Argument(
        ..., case_sensitive=False, help="Select Tenant from choices, case-insensitve."
    ),
):
    """Create a new site and CPE rack in Nautobot."""
    nautobot = NBTools()
    nautobot.create_new_site(site_code, site_name, address, tenant.value)


if __name__ == "__main__":
    main()
