import typer
import yaml
import datetime

from tools import JiraTools

main = typer.Typer(
    add_completion=False,
    help="""
Misc. Jira, GCal, Confluence tools. May be run
individually or regularly via a scheduler.
""",
)


def open_yaml():
    """YAML file for inputs."""
    with open("/Users/jdickman/Google Drive/My Drive/Scripts/usernames.yml", "r") as f:
        return yaml.safe_load(f)


@main.command()
def core_tickets():
    """Return all tickets for designated engineers and dumps as pd to gsheet."""
    jtools = JiraTools()
    jql_tickets = "assignee={engineer} and status not in (Resolved, Deleted, Done, Merged) order by project ASC"
    eng_list = open_yaml()["engineer"]
    jtools.core_tickets(eng_list, jql_tickets)


@main.command()
def update_resource_buckets():
    """Update rotating resources Buckets. Requires input from yaml data.

    EngRv: Rotates schedule based on gcal.
    Circuits: Updates hours based on active circuits, and updates start/end dates.
    """
    jtools = JiraTools()
    data = open_yaml()
    jtools.update_engrv(data["engrv_tickets"], data["engrv_hours"], data["engrv_url"])
    jtools.update_circuit(data["circuit_hours"])


@main.command()
def dump_resouces_report():
    """Pull weekly resources report and dump to sheet."""
    pass


@main.command()
def scheduled():
    """Main function for scheduled runs."""
    core_tickets()
    day = datetime.datetime.now().strftime("%a")
    if day == "Mon":
        update_resource_buckets()
    if day == "Fri":
        dump_resouces_report()


if __name__ == "__main__":
    main()
