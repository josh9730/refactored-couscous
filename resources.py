from datetime import datetime
from atlassian import Jira
from typing import Optional
import numpy as np
import keyring
import typer
import holidays

"""

Uses Typer, see 'resources.py --help'

"""

resources = typer.Typer(
    add_completion=False,
    help="""
Create ticket or updates ticket resource allocations.

\b
Both commands rely on keyring for Jira login (username, password, url):
    - keyring set jira url {{ URL }}
    - keyring set cas user
    - keyring set cas {{ USERNAME }}
""",
)


def jira_login() -> Jira:
    """Fetch Jira login params and return Jira object."""
    cas_user = keyring.get_password("cas", "user")
    cas_pass = keyring.get_password("cas", cas_user)
    jira_url = keyring.get_password("jira", "url")

    jira = Jira(url=jira_url, username=cas_user, password=cas_pass)
    return jira


def holidays_list() -> list:
    """Return list of holidays for current and upcoming year."""
    year = datetime.today().year
    ca_holidays = holidays.CountryHoliday(
        "US", prov=None, state="CA", years=[year, year + 1]
    )
    return [i.isoformat() for i in ca_holidays]


def num_weekdays(date1: str, date2: str) -> int:
    """Count of business days between date1, date2 less holidays."""
    return np.busday_count(date1, date2, holidays=holidays_list())


def new_org_est(ticket_start: str, end_date: str, new_hours: int) -> int:
    """Return Original Estimate based on new hours input.

    Gets new hours/day between today to end_date.
    Multiplies that out over the days from start date to end date
    """
    today = datetime.today().strftime("%Y-%m-%d")
    days_remaining = num_weekdays(today, end_date) + 1  # add 1 to account for today
    hrs_remaining = new_hours / days_remaining
    total_days = num_weekdays(ticket_start, end_date) + 1
    return int(hrs_remaining * total_days)


def check_ticket(jira: Jira, *args: str) -> None:
    """Check project of user-supplied ticket against list of project keys.

    args: list of tickets
    """
    projects = jira.projects(included_archived=None)  # returns list of dicts
    key_list = [project["key"] for project in projects]

    for ticket in args:
        if ticket.split("-")[0] not in key_list:
            raise SystemExit(f"\nTicket Project Key must be one of {key_list}.\n")


def check_date(date: str) -> None:
    """Check date string format."""
    date = convert_date(date) if "/" in date else date
    try:
        return datetime.fromisoformat(date)
    except ValueError:
        print("\nDate Error: Date must be in YYYY-MM-DD or MM/DD/YYYY format.\n")


def convert_date(date: str) -> str:
    """Convert MM/DD/YYYY -> YYYY-MM-DD."""
    try:
        month, day, year = date.split("/")
        new_date = "{year}-{month}-{day}"
        check_date(new_date)
        return new_date
    except ValueError:
        print("\nDate Error: Date must be in YYYY-MM-DD or MM/DD/YYYY format.\n")


def get_ticket(jira: Jira, ticket: str) -> tuple[str, str]:
    """Return start_date, end_date, orginal_estimate from ticket."""
    ticket_return = jira.get_issue(
        ticket, fields=["customfield_10410, customfield_10411", "timetracking"]
    )
    ticket_start = ticket_return["fields"]["customfield_10410"]
    ticket_end = ticket_return["fields"]["customfield_10411"]
    hours = ticket_return["fields"].get("timetracking")
    return ticket_start, ticket_end, hours


def update_ticket(
    jira: Jira, ticket: str, start_date: str, end_date: str, org_est: int, rem_est: int
) -> None:
    """Update start_date, end_date, estimates and check ticket is In Progress."""
    jira.issue_update(
        ticket,
        {
            "customfield_10410": start_date,
            "customfield_10411": end_date,
            "timetracking": {
                "originalEstimate": str(org_est) + "h",
                "remainingEstimate": str(rem_est) + "h",
            },
        },
    )
    jira.set_issue_status(ticket, "In Progress")


@resources.command()
def retrieve(
    ticket: str = typer.Argument(..., help="Ticket, including project field")
) -> None:
    """Retrieve Start, End, and Hours from ticket."""
    jira = jira_login()
    check_ticket(jira, ticket)
    output = get_ticket(jira, ticket)
    hours = int(output[2].get("originalEstimateSeconds")) / 3600 if output[2] else None
    print(f"\nstart_date: {output[0]}\nend_date: {output[1]}\nhours: {hours}\n")


@resources.command()
def create(
    parent_ticket: str = typer.Argument(
        ..., help="Parent Ticket, including project field"
    ),
    epic: str = typer.Option(None, help="Epic Ticket, including project field"),
    project: str = typer.Option(None, help="Set Project field"),
) -> None:
    """Create and link a new ticket for resource tracking.

    Based on parent_ticket field (and optionally Epic ticket), creates a new ticket
    and links appropriately.
    """
    jira = jira_login()
    check_ticket(jira, parent_ticket, epic)

    # uses parent summary and assignee for new ticket
    parent_fields = jira.get_issue(
        parent_ticket, fields=["summary", "assignee", "project"]
    )["fields"]

    new_ticket = jira.issue_create(
        fields={
            "summary": f'{parent_fields["summary"]} - Resources',
            "description": "Task for resource allocation needs.",
            "assignee": {
                "name": parent_fields["assignee"]["name"],
            },
            "project": {
                "key": project if project else parent_fields["project"]["key"],
            },
            "issuetype": {
                "name": "Task",
            },
            "customfield_10401": epic,
        }
    )["key"]
    print(f"{new_ticket=}")

    # create DependsOn / DependedOnBy linking
    link_name = "Members" if parent_ticket.startswith("NOC") else "DependsOn"
    jira.create_issue_link(
        data={
            "type": {
                "name": link_name,
            },
            "inwardIssue": {
                "key": parent_ticket,
            },
            "outwardIssue": {
                "key": new_ticket,
            },
        }
    )


@resources.command()
def update(
    ticket: str = typer.Argument(..., help="Ticket, including project field"),
    end_date: str = typer.Argument(
        ..., help="Ticket End Date, YYYY-MM-DD or MM/DD/YYYY"
    ),
    hours: int = typer.Argument(..., help="Hours from Today until End Date"),
    start_date: Optional[str] = typer.Option(
        None, help="Ticket Start Date, YYYY-MM-DD or MM/DD/YYYY"
    ),
) -> None:
    """Calculate resources and update ticket based on supplied fields.

    Primary use will be extending end_dates and adding hours. Hours/day are calculated from
    new end_date -> today, counting only weekdays (minus holidays). Hours/day then calculated from
    start_date -> end_date, and the original_estimate is updated with the new hours. Automatically
    updates ticket status to In Progress if needed.

    Does not account for PTO or other variables. May also be used to add/change a start_date
    or extend end_date with no new hours.
    """
    today = datetime.today().strftime("%Y-%m-%d")
    jira = jira_login()
    check_ticket(jira, ticket)
    ticket_start, *args = get_ticket(jira, ticket)
    check_date(end_date)
    rem_est = 0

    if hours > 0 and end_date >= today:
        if start_date:
            # New ticket being tracked for resources or changing start date
            check_date(start_date)
            org_est = (
                hours
                if start_date > ticket_start
                else new_org_est(start_date, end_date, hours)
            )

        else:
            # Adjust hours, end date may/may not be same as ticket end date.
            start_date = ticket_start
            org_est = new_org_est(ticket_start, end_date, hours)

    else:
        raise SystemExit(
            "\nSupplied End Date must be >= Current End and Hours must be >= 0"
        )

    update_ticket(jira, ticket, start_date, end_date, org_est, rem_est)


if __name__ == "__main__":
    resources()
