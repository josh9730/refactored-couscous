from datetime import datetime
from typing import Optional, Tuple
import numpy as np
import keyring
import typer
import holidays
from atlassian import Jira

"""
start = customfield_10410
end_date = customfield_10411
hours = timetracking.originalEstimateSeconds
.strftime("%Y-%m-%d")
"""

main = typer.Typer(add_completion=False)


def jira_login():
    cas_user = keyring.get_password("cas", "user")
    cas_pass = keyring.get_password("cas", cas_user)
    jira_url = keyring.get_password("jira", "url")

    jira = Jira(url=jira_url, username=cas_user, password=cas_pass)
    return jira


def holidays_list() -> list:
    """Return list of holidays for current and upcoming year"""
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
    Mltiplies that out over the days from start date to end date
    """
    today = datetime.today().strftime("%Y-%m-%d")
    days_remaining = num_weekdays(today, end_date) + 1
    hrs_remaining = new_hours / days_remaining
    total_days = num_weekdays(ticket_start, end_date) + 1
    return int(hrs_remaining * total_days)


def check_date(date: str):
    """Check date string format."""
    try:
        date = datetime.fromisoformat(date)
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


def get_ticket(jira: Jira, ticket: str) -> Tuple[str, str]:
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
    """Update start_date, end_date, estimates and check ticket is In Progress"""
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


@main.command()
def resources(
    end_date: str = typer.Argument(..., help="Ticket End Date"),
    ticket: str = typer.Argument(..., help="Ticket, including COR/SYS/DEV/etc"),
    hours: int = typer.Argument(..., help="Hours from Today until End Date"),
    start_date: Optional[str] = typer.Argument(None, help="Ticket Start Date"),
) -> None:
    """Calculate resources and update ticket based on supplied fields.

    Primary use will be extending end_dates and adding hours. Hours are calculated from
    new end_date - today, counting only weekdays (minus holidays). Does not account for
    PTO or other variables.

    May also be used to add/change a start_date or extend end_date with no new hours.


    Relies on keyring for Jira logins:

        - keyring set jira url {{ URL }}

        - keyring set mfa {{ USERNAME }}

        - keyring set otp {{ USERNAME }}
    """
    jira = jira_login()
    ticket_start, ticket_end = get_ticket(jira, ticket)

    if "/" in end_date:
        end_date = convert_date(end_date)
    check_date(end_date)

    if start_date:
        # New ticket being tracked for resources or changing start date
        update_ticket(jira, ticket, start_date, end_date, hours, 0)

    elif end_date > ticket_end and hours == 0:
        # Adjust end date with same hours
        update_ticket(jira, ticket, ticket_start, end_date, hours, 0)

    elif hours > 0:
        # Adjust hours, end date may/may not be same as ticket end date.
        org_est = new_org_est(ticket_start, end_date, hours)
        update_ticket(jira, ticket, ticket_start, end_date, org_est, 0)

    else:
        print("\nSupplied End Date must be >= Current End and Hours must be >= 0")
        exit(1)


if __name__ == "__main__":
    main()
