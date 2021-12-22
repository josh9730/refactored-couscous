from jinja2 import Environment, FileSystemLoader
import yaml
import argparse
from utils import Utils, yaml_defaults
from gcal import Calendar


class CreateMOPs:
    """Create MOP/CD pages, link to Jira and create Calendar event (if applicable)."""

    def __init__(self, args):

        with open(f"{args.mop_type}.yaml") as file:
            self.yaml_file = yaml.full_load(file)
            self.mop_type = args.mop_type
        file.close()

        # Initalize utils (schema validators)
        self.utils = Utils(self.yaml_file, self.mop_type)

        # Atlassian login objects
        self.jira = self.utils.jira_login()
        self.confluence = self.utils.conf_login()

        # script vars
        self.args = args
        self.page_title = self.yaml_file["page_title"]
        self.parent_page_id = self.yaml_file["parent_page_id"]
        self.ticket = self.yaml_file["ticket"]

    def create_mop(self):
        """Create MOP from Jinja template, launch confluence & jira methods."""

        env = Environment(
            loader=FileSystemLoader("renderers/"), trim_blocks=True, lstrip_blocks=True
        )
        template = env.get_template("mop.j2")
        self.page_body = template.render(self.yaml_file)

        print(
            f"\n\tCreating MOP:\n\n\t\tTitle: {self.page_title}\n\t\tTicket: {self.ticket}\n\t\tJira Link: {self.args.link}\n"
        )

        self.update_confluence()
        if self.args.link:
            self.update_jira()
        self.utils.move_yaml(self.yaml_file, self.page_title)
        if args.default:
            yaml_defaults(self.yaml_file, self.mop_type)

    def create_cd(self):
        """Create CD from Jinja template, launch confluence, jira and calendar methods."""

        env = Environment(
            loader=FileSystemLoader("renderers/"), trim_blocks=True, lstrip_blocks=True
        )
        template = env.get_template("cd.j2")
        self.page_body = template.render(self.yaml_file)

        print(
            f"\n\tCreating Change Doc:\n\n\t\tTitle: {self.page_title}\n\t\tTicket: {self.ticket}\n\t\tJira Link: {self.args.link}\n"
        )

        self.update_confluence()
        if self.args.calendar:
            self.create_calendar_event()
        if self.args.link:
            self.update_jira()
        self.utils.move_yaml(self.yaml_file, self.page_title)
        if args.default:
            yaml_defaults(self.yaml_file, self.mop_type)

    def update_confluence(self):
        """Create/Update Confluence page based on Title and parent page ID."""

        self.confluence.update_or_create(
            self.parent_page_id, self.page_title, self.page_body, representation="wiki"
        )

    def update_jira(self):
        """Create Jira links to Confluence page if YAML 'link' entry is true."""

        if self.args.link:
            print(f"\tAdding link to {self.ticket}")
            link_title = self.page_title.replace(" ", "+")
            page_url = f"https://documentation.cenic.org/display/Core/{link_title}"
            self.jira.create_or_update_issue_remote_links(
                self.ticket, page_url, self.page_title, relationship="mentioned in"
            )

    def create_calendar_event(self):
        """Create Internal Change event for CD."""

        start_time = str(self.yaml_file["start_time"])
        end_time = str(self.yaml_file["end_time"])
        day = self.yaml_file["start_day"]
        title = self.yaml_file["ticket"] + ": " + self.yaml_file["page_title"]

        print(
            f"\tCreating Internal Change entry:\n\n\t\tDay: {day}\n\t\tStart: {start_time}\n\t\tEnd: {end_time}\n"
        )
        Calendar(self.utils).create_event(start_time, end_time, day, title)

    def print_rendered(self):
        """Print rendered MOP to screen, but no other actions."""

        env = Environment(
            loader=FileSystemLoader("renderers/"), trim_blocks=True, lstrip_blocks=True
        )
        template = env.get_template("mop.j2")
        print(template.render(self.yaml_file))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate MOP/CD and push to Confluence/Jira/gCal"
    )
    parser.add_argument(
        "mop_type",
        metavar="mop_type",
        choices=["mop", "cd"],
        help="Type of document to create. Allowed values are 'mop' and 'cd'",
    )
    parser.add_argument("-l", "--link", help="Create Jira Link", action="store_true")
    parser.add_argument(
        "-p",
        "--print",
        help="Print rendered MOP, no other actions",
        action="store_true",
    )
    parser.add_argument(
        "-c", "--calendar", help="Add CD to calendar", action="store_true"
    )
    parser.add_argument(
        "-d",
        "--default",
        help="Return yaml to defaults (keeping mop_repo & login_vars)",
        action="store_true",
    )
    parser.add_argument(
        "-r",
        "--reset",
        help="Return yaml to defaults (keeping mop_repo & login_vars) and exit script",
        action="store_true",
    )
    args = parser.parse_args()

    mops = CreateMOPs(args)

    if args.reset:
        with open(f"{args.mop_type}.yaml") as file:
            yaml_file = yaml.full_load(file)
        file.close()

        yaml_defaults(yaml_file, args.mop_type)
        print(f"\nReset {args.mop_type.upper()} YAML file.")
        exit(1)

    if args.print:
        mops.print_rendered()

    elif args.mop_type == "mop":
        mops.create_mop()

    elif args.mop_type == "cd":
        mops.create_cd()
