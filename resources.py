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


def check_ticket(jira: Jira, ticket: str) -> None:
    """Check project of user-supplied ticket against list of project keys."""

    # returns list of dicts
    projects = jira.projects(included_archived=None)

    # create list of project keys
    key_list = [project["key"] for project in projects]

    if ticket.split("-")[0] not in key_list:
        raise SystemExit(f"\nTicket Project Key must be one of {key_list}.\n")


def check_date(date: str) -> None:
    """Check date string format."""
    try:
        datetime.fromisoformat(date)
    except ValueError:
        print("\nDate Error: Date must be in YYYY-MM-DD or MM/DD/YYYY format.\n")


def convert_date(date: str) -> str:
    """Convert MM/DD/YYYY -> YYYY-MM-DD."""
    try:
        month, day, year = date.split("/")
        date = f"{year}-{month}-{day}"
    except ValueError:
        print("\nDate Error: Date must be in YYYY-MM-DD or MM/DD/YYYY format.\n")
    return date


def get_ticket(jira: Jira, ticket: str) -> tuple[str, str]:
    """Return start_date, end_date, orginal_estimate from ticket."""
    ticket_return = jira.get_issue(
        ticket, fields=["customfield_10410, customfield_10411"]
    )
    ticket_start = ticket_return["fields"]["customfield_10410"]
    ticket_end = ticket_return["fields"]["customfield_10411"]
    return ticket_start, ticket_end


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
def create(
    parent_ticket: str = typer.Argument(
        ..., help="Parent Ticket, including project field"
    ),
    epic: str = typer.Option(None, help="Epic Ticket, including project field"),
) -> None:
    """Create and link a new ticket for resource tracking.

    Based on parent_ticket field (and optionally Epic ticket), creates a new ticket
    and links appropriately.
    """
    jira = jira_login()
    check_ticket(jira, parent_ticket)
    if epic:
        check_ticket(jira, epic)

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
                "key": parent_fields["project"]["key"],
            },
            "issuetype": {
                "name": "Task",
            },
            "customfield_10401": epic,
        }
    )["key"]
    print(f"{new_ticket=}")

    # create DependsOn / DependedOnBy linking
    jira.create_issue_link(
        data={
            "type": {
                "name": "DependsOn",
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
    end_date: str = typer.Argument(
        ..., help="Ticket End Date, YYYY-MM-DD or MM/DD/YYYY"
    ),
    ticket: str = typer.Argument(..., help="Ticket, including project field"),
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
    jira = jira_login()
    check_ticket(jira, ticket)
    ticket_start, ticket_end = get_ticket(jira, ticket)

    if "/" in end_date:
        end_date = convert_date(end_date)
    check_date(end_date)

    if start_date:
        # New ticket being tracked for resources or changing start date
        if "/" in start_date:
            start_date = convert_date(start_date)
        check_date(start_date)
        update_ticket(jira, ticket, start_date, end_date, hours, 0)

    elif end_date > ticket_end and hours == 0:
        # Adjust end date with same hours
        update_ticket(jira, ticket, ticket_start, end_date, hours, 0)

    elif hours > 0:
        # Adjust hours, end date may/may not be same as ticket end date.
        org_est = new_org_est(ticket_start, end_date, hours)
        update_ticket(jira, ticket, ticket_start, end_date, org_est, 0)

    else:
        raise SystemExit(
            "\nSupplied End Date must be >= Current End and Hours must be >= 0"
        )


if __name__ == "__main__":
    resources()
