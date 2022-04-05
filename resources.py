import sys
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


class Resources:
    def __init__(self):
        cas_user = keyring.get_password("cas", "user")
        cas_pass = keyring.get_password("cas", cas_user)
        jira_url = keyring.get_password("jira", "url")
        self.jira = Jira(url=jira_url, username=cas_user, password=cas_pass)
        self.today = datetime.today()

    def check_ticket(self, *args: str) -> None:
        """Check project of user-supplied ticket against list of project keys.

        args: list of tickets
        """
        projects = self.jira.projects(included_archived=None)  # returns list of dicts
        self.key_list = [project["key"] for project in projects]
        for ticket in args:
            if ticket:
                if ticket.split("-")[0] not in self.key_list:  # handle None defaults
                    raise ValueError(
                        f"\nTicket Project Key must be one of {self.key_list}.\n"
                    )
                if not ticket.split("-")[1].isdigit():
                    raise ValueError(f"{ticket} must be a valid ticket number.")

    def check_project(self, ticket: str, project: Optional[str]) -> None:
        """Check project, ticket for coherence."""
        self.parent_project = self.jira.project(ticket[:3])["projectTypeKey"]
        if self.parent_project == "service_desk" and not project:
            raise ValueError(
                "Project is in Service Desk, Software project must be defined for resource ticket."
            )
        if project and project not in self.key_list:
            raise ValueError(f"Project must be one of {self.key_list}.")

    def check_date(self, date: str) -> None:
        """Check date string format."""
        try:
            date = self.convert_date(date) if "/" in date else date
            datetime.fromisoformat(date)
            return date
        except ValueError:
            sys.exit("\nDate Error: Date must be in YYYY-MM-DD or MM/DD/YYYY format.\n")

    def convert_date(self, date: str) -> str:
        """Convert MM/DD/YYYY -> YYYY-MM-DD."""
        month, day, year = date.split("/")
        return f"{year}-{month}-{day}"

    def get_ticket(self, ticket: str) -> None:
        """Return start_date, end_date, orginal_estimate from ticket."""
        ticket_return = self.jira.get_issue(
            ticket, fields=["customfield_10410, customfield_10411", "timetracking"]
        )
        self.ticket_start = ticket_return["fields"]["customfield_10410"]
        self.ticket_end = ticket_return["fields"]["customfield_10411"]
        self.ticket_hours = ticket_return["fields"].get("timetracking")

    def print_ticket_return(self) -> None:
        hours = (
            int(self.ticket_hours.get("originalEstimateSeconds")) / 3600
            if self.ticket_hours
            else None
        )
        print(
            f"\nstart_date: {self.ticket_start}\nend_date: {self.ticket_end}\nhours: {hours}\n"
        )

    def create_new_resource(
        self,
        parent_ticket: str,
        epic_ticket: Optional[str],
        project: Optional[str],
        title: str,
    ) -> None:
        """Create new resource ticket."""
        # uses parent summary and assignee for new ticket
        parent_fields = self.jira.get_issue(
            parent_ticket,
            fields=["summary", "assignee", "project", "customfield_10401"],
        )["fields"]
        epic = epic_ticket if epic_ticket else parent_fields["customfield_10401"]
        new_ticket = self.jira.issue_create(
            fields={
                "summary": f'{parent_fields["summary"]} - {title}',
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

        # create linking between parent and child tickets
        # Jira SD uses Parent/Child
        # Jira SW uses DependsOn/DependedOnBy
        link_name = "Members" if self.parent_project == "service_desk" else "DependsOn"
        self.jira.create_issue_link(
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

    def holidays_list(self) -> list:
        """Return list of holidays for current and upcoming year."""
        year = self.today.year
        ca_holidays = holidays.CountryHoliday(
            "US", prov=None, state="CA", years=[year, year + 1]
        )
        return [i.isoformat() for i in ca_holidays]

    def num_weekdays(self, date1: str, date2: str) -> int:
        """Count of business days between date1, date2 less holidays."""
        return int(np.busday_count(date1, date2, holidays=self.holidays_list()))

    def new_org_est(self, ticket_start: str, end_date: str, new_hours: int) -> int:
        """Return Original Estimate based on new hours input.

        Gets new hours/day between today to end_date.
        Multiplies that out over the days from start date to end date
        """
        today = self.today.strftime("%Y-%m-%d")
        days_remaining = (
            self.num_weekdays(today, end_date) + 1
        )  # add 1 to account for today
        hrs_remaining = new_hours / days_remaining
        total_days = self.num_weekdays(ticket_start, end_date) + 1
        return int(hrs_remaining * total_days)

    def update_ticket(
        self, ticket: str, start_date: str, end_date: str, rem_est: int
    ) -> None:
        """Update start_date, end_date, estimates and check ticket is In Progress."""
        self.jira.issue_update(
            ticket,
            {
                "customfield_10410": start_date,
                "customfield_10411": end_date,
                "timetracking": {
                    "originalEstimate": str(self.org_est) + "h",
                    "remainingEstimate": str(rem_est) + "h",
                },
            },
        )
        self.jira.set_issue_status(ticket, "In Progress")

    def update_resource(
        self,
        ticket: str,
        end_date: str,
        hours: int,
        new_start: Optional[str],
        rem_est=0,
    ):
        """Update resource ticket."""
        if hours > 0 and end_date >= self.today.strftime("%Y-%m-%d"):
            if new_start:
                # New ticket being tracked for resources or changing start date
                start_date = new_start
                self.org_est = (
                    hours
                    if new_start > self.ticket_start
                    else self.new_org_est(new_start, end_date, hours)
                )
            else:
                # Adjust hours, end date may/may not be same as ticket end date.
                start_date = self.ticket_start
                self.org_est = self.new_org_est(self.ticket_start, end_date, hours)
        else:
            raise SystemExit(
                "\nSupplied End Date must be >= Current End and Hours must be >= 0"
            )
        self.update_ticket(ticket, start_date, end_date, rem_est)


main = typer.Typer(
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


@main.command()
def retrieve(
    ticket: str = typer.Argument(..., help="Ticket, including project field")
) -> None:
    """Retrieve and print Start, End, and Hours from ticket."""
    resources = Resources()
    resources.check_ticket(ticket)
    resources.get_ticket(ticket)
    resources.print_ticket_return()


@main.command()
def create(
    parent_ticket: str = typer.Argument(
        ..., help="Parent Ticket, including project field"
    ),
    epic: str = typer.Option(None, help="Epic Ticket, including project field"),
    project: str = typer.Option(None, help="Set Project field, three letter shorthand"),
    title: str = typer.Option(
        "Resources", help="Set ticket title, adds to inherited parent title"
    ),
) -> None:
    """Create and link a new ticket for resource tracking.

    Based on parent_ticket field (and optionally Epic ticket), creates a new ticket
    and links appropriately.
    """
    resources = Resources()
    resources.check_ticket(parent_ticket, epic)
    resources.check_project(parent_ticket, epic)
    resources.create_new_resource(parent_ticket, epic, project, title)


@main.command()
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
    resources = Resources()
    resources.check_ticket(ticket)
    end_date = resources.check_date(end_date)
    if start_date:
        start_date = resources.check_date(start_date)
    resources.get_ticket(ticket)
    resources.update_resource(ticket, end_date, hours, start_date)


if __name__ == "__main__":
    main()
