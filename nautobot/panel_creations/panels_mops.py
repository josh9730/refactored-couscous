"""
    - create panels, cassettes, ports, trunk cables in Nautobot based on data.yaml input
    - print shipping items for pasting panels shipment into shipping spreadsheet
    - create shipping ticket for panels with shipping info
    - update master ticket with panel pairs in the Description
    - create panels install MOP ticket and MOP YAML (for input to the MOPs program)
    - create shipping ticket for jumpers (and print to screen for the spreadsheet)
    - create jumpers install MOP ticket and MOP YAML (for input to the MOPs program)
"""
import re
from collections import Counter
from datetime import datetime

import keyring
import typer
import urllib3
import yaml
from atlassian import Jira
from jinja2 import Environment, FileSystemLoader
from pynautobot import api

main = typer.Typer(
    add_completion=False,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Data:
    def __init__(self):
        with open("data.yaml", "r") as f:
            data = yaml.safe_load(f)

        self.site = data["site"]
        self.hub_rack = data["hub_rack"]
        self.fac_hub_rack = data["fac_hub_rack"]
        self.xcp_ru = data["xcp_ru"]
        self.c6_ru = data["c6_ru"]
        self.shipping_info = data["shipping_info"]
        self.assignee = keyring.get_password("cas", "user")
        self.panels_list = [
            [
                f"HUB-{self.site}-{self.hub_rack}-{i['hub_ru']}",
                f"SPK-{self.site}-{i['spoke']}",
                i["cat6"],
                i["jumper"],
            ]
            for i in data["panels_list"]
        ]
        self.jumpers_list = [f'{i["jumper"]}m OS2 MPO-24' for i in data["panels_list"]]


class PanelsNautobot(Data):
    def __init__(self):
        super().__init__()
        self.nautobot = api(
            url=keyring.get_password("nautobot_stage", "url"),
            token=keyring.get_password("nautobot-stage", self.assignee + "mfa"),
        )

        self.nautobot.http_session.verify = False
        self.tenant = self.nautobot.tenancy.tenants.get(slug="cenic-hubsite").id
        self.remote_panel = self.nautobot.extras.relationships.get(name="remote_panel")

    def _next_cable_id(self):
        # cables = tuple(self.nautobot.dcim.cables.filter(label__re=".*--C[0-9]{4}"))  # this is not working in nautobot-stage for some reason
        # last_cable_label = sorted(tuple(map(lambda x: x.label, cables)))[-1]
        # last_id = last_cable_label.split("--C")[-1]

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

        return "C" + str(int(trunk_cables[-1].split("--C")[1]) + 1).rjust(4, "0")

    def _relate_panels(self, panels):
        self.nautobot.extras.relationship_associations.create(
            relationship=self.remote_panel.id,
            source_type=self.remote_panel.destination_type,
            source_id=panels[0].id,
            destination_type=self.remote_panel.source_type,
            destination_id=panels[1].id,
        )

    def _create_cassettes(self, panel, slot, cassette_type, name):
        return self.nautobot.dcim.devices.create(
            name=panel.name + f" -- Slot {slot} {name}",
            site={"slug": self.site.lower()},
            rack={"name": panel.name.split("-")[2], "site__slug": self.site.lower()},
            device_type={"slug": cassette_type},
            device_role={"slug": "modular-panel-cassettes"},
            status="active",
            tenant=self.tenant,
        )

    def _create_trunk(self):
        try:
            self.nautobot.dcim.cables.create(
                type="smf",
                termination_a_type="dcim.rearport",
                termination_b_type="dcim.rearport",
                termination_a_id=self.trunk_list[1].id,
                termination_b_id=self.trunk_list[0].id,
                status="connected",
                label=f"COM--{self.new_panel_list[0].name}--{self.new_panel_list[1].name}--{self._next_cable_id()}",
            )
        except ValueError:
            print(
                f"CREATE MANUALLY: COM--{self.new_panel_list[0].name}--{self.new_panel_list[1].name}--CXXXX"
            )

    def create_panels(self):
        for panel_pair in self.panels_list:

            self.new_panel_list, self.trunk_list = [], []
            cassette_list, c6_list = [], []

            for panel in panel_pair[0:2]:
                # create panel
                new_panel = self.nautobot.dcim.devices.create(
                    name=panel,
                    site={"slug": self.site.lower()},
                    rack={"name": panel.split("-")[2], "site__slug": self.site.lower()},
                    position=int(panel.split("-U")[1]),
                    face="front",
                    device_type={"slug": "fhd-enclosure-blank"},
                    device_role={"slug": "modular-panels"},
                    status="active",
                    tenant=self.tenant,
                )
                print(f"Created panel: {new_panel.name}")
                self.new_panel_list.append(new_panel)

                # create ports
                trunk = self.nautobot.dcim.rear_ports.create(
                    device=new_panel.id,
                    name="Slot 1 Port 1 Rear",
                    type="lc",
                    positions=12,
                    custom_fields={"jumper_type": "SMF"},
                )
                self.trunk_list.append(trunk)
                for i in range(1, 13):
                    self.nautobot.dcim.front_ports.create(
                        device=new_panel.id,
                        name=f"Slot 1 Port {i} Front",
                        type="lc",
                        rear_port=trunk.id,
                        rear_port_position=i,
                        custom_fields={"jumper_type": "SMF"},
                    )

                # create and assign cassettes
                cassette_type = "fhd-mpo-24lc-os2-cassette-type-a"
                if panel.startswith("HUB"):
                    cassette_type += "f"
                cassette = self._create_cassettes(
                    new_panel, 1, cassette_type, "MPO24-LC OS2"
                )
                cassette_list.append(cassette)

                if panel_pair[2]:
                    c6_cassette = self._create_cassettes(
                        new_panel, 4, "fhd-6xcat6-adapter", "Cat6"
                    )
                    c6_list.append(c6_cassette)

                    # create ports
                    for i in range(1, 7):
                        cat6_trunk = self.nautobot.dcim.rear_ports.create(
                            device=new_panel.id,
                            name=f"Slot 4 Port {i} Rear",
                            type="8p8c",
                            positions=12,
                            custom_fields={"jumper_type": "SMF"},
                        )
                        self.nautobot.dcim.front_ports.create(
                            device=new_panel.id,
                            name=f"Slot 4 Port {i} Front",
                            type="8p8c",
                            rear_port=cat6_trunk.id,
                            rear_port_position=1,
                            custom_fields={"jumper_type": "CAT6"},
                        )

            # relate panels and cassettes
            self._relate_panels(self.new_panel_list)
            self._relate_panels(cassette_list)
            if c6_list:
                self._relate_panels(c6_list)

            self._create_trunk()


class Panels(Data):
    def __init__(self):
        super().__init__()
        self.jira = Jira(
            url=keyring.get_password("jira", "url"),
            username=self.assignee,
            password=keyring.get_password("cas", self.assignee),
        )

    @staticmethod
    def _load_template(template_name: str, data: dict):
        env = Environment(loader=FileSystemLoader("./"))
        template = env.get_template(f"{template_name}.j2")
        return template.render(data)

    def create_panels_shipment(self, render: bool = True):
        panels = {
            "Modular Panels": 2 * len(self.panels_list),
            "MPO-LC Type A Cassettes": len(self.panels_list),
            "MPO-LC Type AF Cassettes": len(self.panels_list),
            "Cat6 Cassettes": 2 * len([i for i in self.panels_list if i[2] == 1]),
            "48-port LC Panel": 1,
            "24-port Cat6 Panel": 1,
        }
        shipping_list = {
            "date": datetime.today().strftime("%m/%d/%y"),
            "contact": self.shipping_info["contact"],
            "company": self.shipping_info["company"],
            "address": self.shipping_info["address"],
            "phone": self.shipping_info["phone"],
            "items_list": [f"** ({j}) {i}" for i, j in panels.items()],
        }

        print()
        print("\nFOR SHIPPING SPREADSHEET\n\nQUANTITIES\n")
        [print(i) for i in panels.values()]
        print("\nITEMS\n")
        [print(i) for i in panels.keys()]
        print("\n")
        return Panels._load_template("shipping", shipping_list)

    def upload_pairings(self, parent_ticket):
        jumper_text_list = "".join([f"{i[0]} -- {i[1]}\n" for i in self.panels_list])
        output = (
            "Creating the following HUB-SPK pairings:{noformat}"
            + jumper_text_list
            + "{noformat}"
        )
        self.jira.update_issue_field(parent_ticket, {"description": output})

    def create_jumper_shipment(self):
        jumpers = Counter(self.jumpers_list)
        shipping_list = {
            "date": datetime.today().strftime("%m/%d/%y"),
            "contact": self.shipping_info["contact"],
            "company": self.shipping_info["company"],
            "address": self.shipping_info["address"],
            "phone": self.shipping_info["phone"],
            "items_list": [f"** ({j}) {i}" for i, j in list(jumpers.items())],
        }
        print("\nFOR SHIPPING SPREADSHEET\n\nQUANTITIES\n")
        _ = [print(i) for i in jumpers.values()]
        print("\nITEMS\n")
        _ = [print(i) for i in jumpers.keys()]
        print("\n")
        return Panels._load_template("shipping", shipping_list)

    def create_ticket(self, parent, ticket_name, description):
        summary = self.jira.get_issue(parent, fields=["summary"])["fields"]["summary"]
        new_ticket = self.jira.issue_create(
            fields={
                "summary": f"{summary} - {ticket_name}",
                "description": description,
                "assignee": {
                    "name": self.assignee,
                },
                "reporter": {
                    "name": self.assignee,
                },
                "project": {
                    "key": "NOC",
                },
                "issuetype": {
                    "name": "CENIC Request",
                },
                "customfield_10002": [8],
            }
        )["key"]
        self.jira.create_issue_link(
            data={
                "type": {
                    "name": "Members",
                },
                "inwardIssue": {
                    "key": parent,
                },
                "outwardIssue": {
                    "key": new_ticket,
                },
            }
        )
        print(f"{new_ticket=}")
        return new_ticket

    def create_mop(self, template, mop_name, rh_ticket, shipping_ticket):
        input_dict = {
            "site": self.site,
            "title": f"{self.site} Panels Install",
            "ticket": rh_ticket,
            "summary": f"Install new patch paneling at {self.site}",
            "shipping_ticket": shipping_ticket,
            "fac_hub_rack": self.fac_hub_rack,
            "hub_rack": self.hub_rack,
            "xcp_ru": self.xcp_ru,
            "c6_ru": self.c6_ru,
            "panels_list": self.panels_list,
        }
        mop = Panels._load_template(template, input_dict)
        with open(f"mops/{self.site}_{mop_name}", "w") as f:
            f.write(mop)


@main.command()
def print_shipping():
    """Print only the shipping spreadsheet list."""
    Panels().create_panels_shipment(render=False)


@main.command()
def create_panels():
    """Create all panels in Nautobot, similar to CreatePanels/Cassettes Job."""
    PanelsNautobot().create_panels()


@main.command()
def install_panels(parent_ticket: str):
    panels = Panels()
    # panels.upload_pairings(parent_ticket)

    # shipment_form = panels.create_panels_shipment()
    # shipping_ticket = panels.create_ticket(
    #     parent_ticket, "Panels Shipping", shipment_form
    # )
    # rh_ticket = panels.create_ticket(parent_ticket, "Panels Install", "")
    rh_ticket = 'NOC-692426'
    shipping_ticket = 'NOC-683847'
    panels.create_mop("panel_install", "mop_panel.yml", rh_ticket, shipping_ticket)


@main.command()
def install_jumpers(parent_ticket: str):
    # add jumper length to panels in Comments
    panels = Panels()

    shipment_form = panels.create_jumper_shipment()
    shipping_ticket = panels.create_ticket(
        parent_ticket, "Jumpers Shipping", shipment_form
    )
    rh_ticket = panels.create_ticket(parent_ticket, "Jumpers Install", "")
    panels.create_mop("jumper_install", "mop_jumper.yml", rh_ticket, shipping_ticket)


if __name__ == "__main__":
    main()
