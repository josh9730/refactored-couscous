import base64
import csv
import datetime
import re
from typing import Final

import typer
import yaml

from tools import GoogleTools, JiraTools

main = typer.Typer(
    add_completion=False,
    help="""
Misc. Jira, GCal, Confluence tools. May be run
individually or regularly via a scheduler.
""",
)

RH_LABEL: Final[str] = "Label_3737818148016423963"


def open_yaml():
    """YAML file for inputs."""
    with open("/Users/jdickman/Google Drive/My Drive/Scripts/usernames.yml", "r") as f:
        return yaml.safe_load(f)


def decode_mail_payload(message: dict) -> str:
    try:
        return base64.b64decode(message["payload"]["body"]["data"]).decode("utf-8")
    except UnicodeDecodeError:
        print(message["snippet"])
        return ""


def parse_rh_message(message: str) -> list[str | int]:
    def re_search(regex):
        result = re.search(regex, message)
        if result:
            return result.group()
        return None

    def format_return(raw: str) -> str:
        if raw:
            return raw.split(":")[1].strip().upper()
        return ""

    def parse_time(input_time: str) -> int:
        """Return time in minutes."""
        if not input_time:
            return ""

        t_list = input_time.split()
        if len(t_list) <= 2:
            return int(float(t_list[0]) * 60)  # assume its an integer of hours if len == 1
        elif len(t_list) == 3:
            ...  # not sure if this is possible
        elif len(t_list) == 4:
            return int(float(t_list[0]) * 60 + float(t_list[2]))

    charge = format_return(re_search(r"Charge:\s*((\w+\s\w+)|(\w+))"))
    vendor = format_return(re_search(r"Vendor:\s*((\w+\s\w+)|(\w+))"))
    ticket = format_return(re_search(r"Jira Ticket:\s*\S+"))
    billable = format_return(re_search(r"Billable Time.*:\s*((\d+\s\w+\s\d+\s\w+)|(\d+\.\d+\s\w+)|(\d+\s\w+))"))

    return [vendor, ticket, charge, parse_time(billable)]


def convert_date(epoch_ms: str) -> str:
    return datetime.datetime.utcfromtimestamp(int(epoch_ms) / 1000).strftime("%Y-%m-%d")


@main.command()
def rh_emails(
    start_date: str = typer.Option("", help="Search start date, YYYY/MM/DD"),
    end_date: str = typer.Option("", help="Search end date, YYYY/MM/DD"),
):
    google = GoogleTools()
    rh_mail = google.get_mail_by_label(RH_LABEL, start_date=start_date, end_date=end_date)

    output = []
    for mail in rh_mail["messages"]:
        message_raw = google.get_mail_by_id(mail["id"])
        payload = decode_mail_payload(message_raw)
        if payload:
            msg_date = convert_date(message_raw["internalDate"])
            msg_output = parse_rh_message(payload)
            msg_output.append(msg_date)
            output.append(msg_output)

    with open("billables.csv", "w", encoding="UTF-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VENDOR", "TICKET", "CHARGE", "BILLABLE MIN", "DATE"])
        for i in output:
            writer.writerow(i)


@main.command()
def core_tickets():
    """Return all tickets for designated engineers and dumps as pd to gsheet."""
    jql_tickets = "assignee={engineer} and status not in (Resolved, Deleted, Done, Merged) order by project ASC"
    eng_list = open_yaml()["engineer"]
    jtools.core_tickets(eng_list, jql_tickets)


@main.command()
def update_resource_buckets():
    """Update rotating resources Buckets. Requires input from yaml data.

    EngRv: Rotates schedule based on gcal.
    Circuits: Updates hours based on active circuits, and updates start/end dates.
    """
    data = open_yaml()
    engineer_list = GoogleTools().get_engrv(data["engrv_url"])
    jtools.update_engrv(engineer_list, data["engrv_tickets"], data["engrv_hours"])
    jtools.update_circuit(data["circuit_hours"])


@main.command()
def calendar_pull():
    """Pull previous week's maintenance & internal calendar events, create DF
    and dump to gSheet
    """
    data = open_yaml()
    gtools = GoogleTools()
    gtools.weekly_events(data["maint_url"], data["ic_url"])


@main.command()
def resources_report():
    """Pull weekly resources report and dump to sheet."""
    data = open_yaml()
    jql_string = 'assignee={engineer} and status = "In Progress" and originalEstimate > 0 and "End date" >= now() and "Start date" <= now()'
    jtools.resources_reporting(data["engineer"], jql_string)


@main.command()
def cor_updates():
    """Pull weekly COR Jira ticket updates."""
    jql_tickets = 'project = "CENIC Core Projects" and (updated > startOfWeek() or createdDate > startOfWeek() or resolutiondate > startOfWeek()) ORDER BY updated ASC'
    eng_list = open_yaml()["engineer"]
    jtools.cor_project_updates(eng_list, jql_tickets)


@main.command()
def cpe_tracker():
    """Update CPE Hardware Tracker data."""
    jtools.get_cpe_tracker_info()


@main.command()
def purchasing_tracker():
    """Purchasing Tracker for all Core purchasing."""
    core_list = open_yaml()["core_all"]
    jtools.purchases_tracking(core_list)


@main.command()
def la2_tracker():
    """LA2 status tracker for the migration."""
    jtools.la2_migration_status()


@main.command()
def scheduled():
    """Main function for scheduled runs."""
    core_tickets()
    cpe_tracker()
    la2_tracker()
    day = datetime.datetime.now().strftime("%a")
    if day == "Mon":
        # update_resource_buckets()
        calendar_pull()
        purchasing_tracker()

    elif day == "Fri":
        # resources_report()
        cor_updates()


@main.command()
def create_predep(master_ticket: str):
    """Create Install, Migration, Closeout child tickets."""
    summary = jtools.get_ticket_summary(master_ticket)
    jtools.create_ticket(master_ticket, summary.replace("Circuit Install", "Install Planning"))
    jtools.create_ticket(master_ticket, summary.replace("Circuit Install", "Migration Planning"))
    jtools.create_ticket(master_ticket, summary.replace("Circuit Install", "Closeout"))


@main.command()
def convert_dep(master_ticket: str, noc_ticket: str):
    """ """

    with open("convert_dep.yaml", "r") as f:
        data = yaml.safe_load(f)

    for i, j in data.items():
        if not j:
            data[i] = ""

    fields = jtools.get_ticket_fields(noc_ticket)
    dep_ticket = jtools.create_dep_install(
        master_ticket,
        fields["summary"],
        fields["assignee"]["name"],
        fields["reporter"]["name"],
        fields["description"],
        **data,
    )
    print(f"Created new DEP ticket: {dep_ticket}")
    jtools.change_status(noc_ticket, "Resolved")
    print(f"Changed ticket status for: {noc_ticket}")

    # new_tickets = [
    #     [
    #         "Amador COE",
    #         "FERG1",
    #         "New",
    #         "Amador COE to FERG1 - AT&T 10 Gbps  - Circuit Install",
    #     ],
    # ]

    # for i in new_tickets:
    #     if i[2] == "Upgrade":
    #         replace = "Yes"
    #     else:
    #         replace = "No"
    #
    #     dep_ticket = jtools.create_dep_install(
    #         "DEP-303",
    #         i[3],
    #         "snguyen",
    #         "FY 23-24",
    #         i[1],
    #         "DC",
    #         replace,
    #         "",
    #         "Lit",
    #         "Yes",
    #         i[2],
    #         "6333.33",
    #         "K12",
    #         i[0],
    #     )
    #     print(i[3])
    #     print(dep_ticket)


if __name__ == "__main__":
    jtools = JiraTools()
    main()
