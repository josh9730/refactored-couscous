from datetime import datetime
import argparse

from tools.utils import jira_login

"""
start = customfield_10410
end = customfield_10411
hours = timetracking.originalEstimateSeconds
.strftime("%Y-%m-%d")
"""


def check_date(date):
    # Date must be in isoformat

    try:
        date = datetime.fromisoformat(date)
    except ValueError:
        print("\nDate Error: Date must be provided in YYYY-MM-DD format.\n")


def get_ticket(jira, args):
    # get start_date, end_date, orginal_estimate from ticket

    ticket = jira.get_issue(
        args.ticket, fields=["customfield_10410", "customfield_10411", "timetracking"]
    )
    start = ticket["fields"]["customfield_10410"]
    end = ticket["fields"]["customfield_10411"]

    try:
        hrs = ticket["fields"]["timetracking"]["originalEstimateSeconds"] / 3600
    except KeyError:
        hrs = 0

    return start, end, int(hrs)


def update_ticket(jira, ticket, start, end, org_est, rem_est):
    # update start_date, end_date, estimates, and make sure ticket is In Progress

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
    check_date(args.end)
    jira = jira_login()
    tic_start, tic_end, tic_hrs = get_ticket(jira, args)
    check_date(args.end)

    if args.end == tic_end and args.hours > 0:
        """adjust hours with same end date

        original estimate = tic_hrs + args.hours
        remaining estimate = args.hours
        """
        org_est = int(tic_hrs + args.hours)
        rem_est = int(args.hours)
        update_ticket(jira, args.ticket, tic_start, tic_end, org_est, rem_est)

    elif args.end > tic_end and args.hours == 0:
        """adjust end date with same hours

        end date = args.end
        """
        update_ticket(jira, args.ticket, tic_start, args.end, tic_hrs, 0)

    elif args.end > tic_end and args.hours > 0:
        """adjust end date with additional hours

        original estimate = tic_hrs + args.hours
        remaining estimate = args.hours
        end date = args.end
        """
        org_est = int(tic_hrs + args.hours)
        rem_est = int(args.hours)
        update_ticket(jira, args.ticket, tic_start, args.end, org_est, rem_est)

    else:
        print("\nSupplied End Date must be >= Current End and Hours must be >= 0")
        exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("ticket", metavar="Ticket", help="Jira ticket")
    parser.add_argument("end", metavar="End", help="New End Date in YYYY-MM-DD format.")
    parser.add_argument(
        "hours",
        metavar="Add Hours",
        help="Additional Hours to be added as integer",
        type=int,
    )
    args = parser.parse_args()
    main(args)
