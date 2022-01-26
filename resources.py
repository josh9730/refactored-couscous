from datetime import datetime
import numpy as np
import argparse
import holidays

from tools.utils import jira_login

"""
start = customfield_10410
end = customfield_10411
hours = timetracking.originalEstimateSeconds
.strftime("%Y-%m-%d")
"""


def holidays_list():
    """Return list of holidays for current and upcoming year"""
    ### MAKE A CHANGE
    year = datetime.today().year
    ca_holidays = holidays.CountryHoliday(
        "US", prov=None, state="CA", years=[year, year + 1]
    )
    return [i.isoformat() for i in ca_holidays]


def num_weekdays(date1, date2):
    """Count of business days between date1, date2 less holidays."""
    return np.busday_count(date1, date2, holidays=holidays_list())


def new_org_est(tic_start, end_date, new_hours):
    """Return Original Estimate based on new hours
    gets new hours/day between today - end_date
    multiplies that out over the days start date - end date
    """
    today = datetime.today().strftime("%Y-%m-%d")
    days_remaining = num_weekdays(today, end_date) + 1
    hrs_remaining = new_hours / days_remaining
    total_days = num_weekdays(tic_start, end_date) + 1
    return int(hrs_remaining * total_days)


def check_date(date):
    """Check date string format"""
    try:
        date = datetime.fromisoformat(date)
    except ValueError:
        print("\nDate Error: Date must be in YYYY-MM-DD or MM/DD/YYYY format.\n")


def convert_date(date):
    """Convert MM/DD/YYYY -> YYYY-MM-DD"""
    try:
        month, day, year = date.split("/")
        date = f"{year}-{month}-{day}"
    except ValueError:
        print("\nDate Error: Date must be in YYYY-MM-DD or MM/DD/YYYY format.\n")
    return date


def get_ticket(jira, args):
    """Return start_date, end_date, orginal_estimate from ticket."""
    ticket = jira.get_issue(
        args.ticket, fields=["customfield_10410, customfield_10411"]
    )
    start = ticket["fields"]["customfield_10410"]
    end = ticket["fields"]["customfield_10411"]

    return start, end


def update_ticket(jira, ticket, start, end, org_est, rem_est):
    """Update start_date, end_date, estimates and check ticket is In Progress"""
    jira.issue_update(
        ticket,
        {
            "customfield_10410": start,
            "customfield_10411": end,
            "timetracking": {
                "originalEstimate": str(org_est) + "h",
                "remainingEstimate": str(rem_est) + "h",
            },
        },
    )
    jira.set_issue_status(ticket, "In Progress")


def main(args):
    jira = jira_login()
    tic_start, tic_end = get_ticket(jira, args)

    if "/" in args.end:
        args.end = convert_date(args.end)
    check_date(args.end)

    if args.start:
        """new ticket being tracked for resources"""
        update_ticket(jira, args.ticket, args.start, args.end, args.hours, 0)

    elif args.end > tic_end and args.hours == 0:
        """adjust end date with same hours

        end date = args.end
        """
        update_ticket(jira, args.ticket, tic_start, args.end, args.hours, 0)

    elif args.hours > 0:
        org_est = new_org_est(tic_start, args.end, args.hours)
        update_ticket(jira, args.ticket, tic_start, args.end, org_est, 0)

    else:
        print("\nSupplied End Date must be >= Current End and Hours must be >= 0")
        exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate resources & update ticket")
    parser.add_argument(
        "end", metavar="End-Date", help="New End Date in YYYY-MM-DD format."
    )
    parser.add_argument("ticket", metavar="Ticket", help="Jira ticket")
    parser.add_argument(
        "hours",
        metavar="New-Hours",
        type=int,
        help="Additional Hours to be added as integer",
    )
    parser.add_argument(
        "start",
        metavar="Start-Date",
        nargs="?",
        default=None,
        help="Optionally set new Start Date in YYYY-MM-DD format",
    )
    args = parser.parse_args()
    main(args)
