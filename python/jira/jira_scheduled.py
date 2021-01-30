"""Weekly and daily automated runs, used by LaunchControl
"""

from atl_main import AtlassianStuff
from cal_main import CalendarStuff
import datetime
import yaml

with open('data.yaml') as file:
    data = yaml.full_load(file)

def resources(atl_stuff):
    engrv_hours = 4
    shipping_hours = 5
    circuit_hours = 2

    atl_stuff.update_rotating_bucket(list(data['circuit_tickets'].values()), engrv_hours)
    atl_stuff.update_rotating_bucket(list(data['shipping_tickets'].values()), shipping_hours)
    atl_stuff.update_circuit(list(data['engrv_tickets'].values()), circuit_hours)

def main():

    username = data['username']
    sheet_key = data['sheet_key']

    atl_stuff = AtlassianStuff(username, sheet_key)
    cal_stuff = CalendarStuff(username)

    day = datetime.datetime.now().strftime("%a")

    if day == 'Mon':

        # Update resources
        resources(atl_stuff)

        # Outages
        jql_outage = 'labels = "CC|outage"'
        atl_stuff.outages(jql_outage)

        # GCal events pull
        cal_stuff.weekly_events()

    elif not day == 'Sat' or not day == 'Sun':

        # Update Core tickets
        jql_tickets = 'assignee={engineer} and status not in (Resolved, Deleted, Done)'
        atl_stuff.core_tickets(data['engineer'], jql_tickets)

        # Update open RH tickets
        jql_rh = 'labels = "RH" and status not in (Resolved, Deleted, Done)'
        atl_stuff.open_rh(jql_rh)


if __name__ == '__main__':
    main()