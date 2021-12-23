"""Weekly and daily automated runs, used by LaunchControl. Argparse to manually launch a script.
"""

import sys
import os

import argparse
import datetime

from tools.utils import get_user_vars
from tools.atl_main import JiraStuff
from tools.cal_main import CalendarStuff


data = get_user_vars()

parser = argparse.ArgumentParser(description="Manually run scheduled Jira tasks.")
parser.add_argument(
    "-b", "--buckets", help="Run EngRv bucket update script", action="store_true"
)
parser.add_argument(
    "-o", "--outages", help="Run outage pull script", action="store_true"
)
parser.add_argument(
    "-cal", "--gcal", help="Run calendar events script", action="store_true"
)
parser.add_argument(
    "-t", "--tickets", help="Run Core tickets pull script", action="store_true"
)
parser.add_argument(
    "-r", "--open_rh", help="Run Open RH pull script", action="store_true"
)
parser.add_argument(
    "-c", "--circuits", help="Pull all open Circuits tickets", action="store_true"
)
args = parser.parse_args()


def outages(atl_stuff):
    # Outages
    jql_outage = 'labels = "CC|outage"'
    atl_stuff.outages(jql_outage)


def gcal_pull(cal_stuff):
    # GCal events pull
    cal_stuff.weekly_events()


def ticket_pull(atl_stuff):
    # Update Core tickets
    jql_tickets = (
        "assignee={engineer} and status not in (Resolved, Deleted, Done, Merged)"
    )
    atl_stuff.core_tickets(data["engineer"], jql_tickets)


def open_rh(atl_stuff):
    # Update open RH tickets
    jql_rh = 'labels = "RH" and status not in (Resolved, Deleted, Done)'
    atl_stuff.open_rh(jql_rh)


def circuits(atl_stuff):
    # Update circuit milestone tracker
    jql_circuits = 'Milestone is not EMPTY and Milestone not in ("M1-Eng Mgr assign resource to deployment issue", "M2-Order and Deliver Hardware")  and assignee in (jdickman, myunus, nlo, eho, tsanda) and status not in (Resolved, Deleted, Merged)'
    atl_stuff.circuits(jql_circuits)


def buckets(cal_stuff, atl_stuff):
    # Update EngRv bucket based on gCal entry for rotation
    # Update Circuits bucket based on Active circuits from gcal
    eng = cal_stuff.get_engrv()
    atl_stuff.update_rotating_bucket(data["engrv_tickets"], data["engrv_hours"], eng)
    atl_stuff.update_circuit(
        list(data["circuit_tickets"].values()), data["circuit_hours"]
    )


def main(args):

    sheet_key = data["sheet_key"]

    jira = JiraStuff(sheet_key=sheet_key)
    cal = CalendarStuff()

    if args.buckets:
        buckets(cal, jira)
    elif args.outages:
        outages(jira)
    elif args.gcal:
        gcal_pull(cal)
    elif args.tickets:
        ticket_pull(jira)
    elif args.open_rh:
        open_rh(jira)
    elif args.circuits:
        circuits(jira)

    else:

        day = datetime.datetime.now().strftime("%a")
        if day == "Mon":
            buckets(cal, jira)
            outages(jira)
            gcal_pull(cal)

        else:
            ticket_pull(jira)
            open_rh(jira)
            # circuits(jira)


if __name__ == "__main__":
    main(args)
