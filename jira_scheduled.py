"""Weekly and daily automated runs, used by LaunchControl. Argparse to manually launch a script.
"""

import argparse
import datetime
import yaml
import sys

#pylint: disable=import-error
sys.path.append('/Users/jdickman/Git/refactored-couscous/projects/atl_cal')
from atl_main import JiraStuff
from cal_main import CalendarStuff


with open('/Users/jdickman/Git/refactored-couscous/usernames.yml') as file:
    data = yaml.full_load(file)

parser = argparse.ArgumentParser(description='Manually run scheduled Jira tasks.')
parser.add_argument("-b", "--buckets", help="Run bucket update script", action="store_true")
parser.add_argument("-o", "--outages", help="Run outage pull script", action="store_true")
parser.add_argument("-c", "--gcal", help="Run calendar events script", action="store_true")
parser.add_argument("-t", "--tickets", help="Run Core tickets pull script", action="store_true")
parser.add_argument("-r", "--open_rh", help="Run open RH pull script", action="store_true")
args = parser.parse_args()

def buckets(atl_stuff):
    # Update resources
    atl_stuff.update_rotating_bucket(list(data['engrv_tickets'].values()), data['engrv_hours'])
    atl_stuff.update_rotating_bucket(list(data['shipping_tickets'].values()), data['shipping_hours'])
    atl_stuff.update_circuit(list(data['circuit_tickets'].values()), data['circuit_hours'])

def outages(atl_stuff):
    # Outages
    jql_outage = 'labels = "CC|outage"'
    atl_stuff.outages(jql_outage)

def gcal_pull(cal_stuff):
    # GCal events pull
    cal_stuff.weekly_events()

def ticket_pull(atl_stuff):
    # Update Core tickets
    jql_tickets = 'assignee={engineer} and status not in (Resolved, Deleted, Done)'
    atl_stuff.core_tickets(data['engineer'], jql_tickets)

def open_rh(atl_stuff):
    # Update open RH tickets
    jql_rh = 'labels = "RH" and status not in (Resolved, Deleted, Done)'
    atl_stuff.open_rh(jql_rh)

def main(args):

    username = data['cas']
    sheet_key = data['sheet_key']

    atl_stuff = JiraStuff(username, sheet_key=sheet_key)
    cal_stuff = CalendarStuff(username=username)

    if args.buckets: buckets(atl_stuff)
    elif args.outages: outages(atl_stuff)
    elif args.gcal: gcal_pull(cal_stuff)
    elif args.tickets: ticket_pull(atl_stuff)
    elif args.open_rh: open_rh(atl_stuff)

    else:

        day = datetime.datetime.now().strftime("%a")

        if day == 'Mon':
            buckets(atl_stuff)
            outages(atl_stuff)
            gcal_pull(cal_stuff)

        else:
            ticket_pull(atl_stuff)
            open_rh(atl_stuff)


if __name__ == '__main__':
    main(args)