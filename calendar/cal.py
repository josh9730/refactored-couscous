from __future__ import print_function
import datetime
from datetime import datetime, timedelta
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import re
from gspread_pandas import Spread
from pprint import pprint
import gspread
from atlassian import Jira
import json
import keyring

regex = re.compile(r'\d+:\sCENIC')

full_ticket_re = re.compile(r"(NOC|COR|DEV|SYS)-[0-9]{3,6}")
ticket_re = re.compile(r"[0-9]{4,6}")

def main():
    # if os.path.exists('token.pickle'):
    with open('/Users/jdickman/Git/refactored-couscous/calendar/token.pickle', 'rb') as token:
        creds = pickle.load(token)

    service = build('calendar', 'v3', credentials=creds)

    # Call the Calendar API
    now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    d1 = ((datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z')
    # d2 = ((datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z')

    maint_cal = service.events().list(calendarId='cenic.org_36uqe435vlel8qv9ul57tomo1g@group.calendar.google.com',
                                        timeMin=d1, timeMax=now, singleEvents=True,
                                        orderBy='startTime').execute()
    maint_events = maint_cal.get('items', [])

    internal_cal = service.events().list(calendarId='cenic.org_oggku8rjbli9v7163ocroug09s@group.calendar.google.com',
                                        timeMin=d1, timeMax=now, singleEvents=True,
                                        orderBy='startTime').execute()
    internal_events = internal_cal.get('items', [])

    gc = gspread.oauth()
    sh = gc.open('Core Tickets')
    worksheet = sh.worksheet('gcal_pull')

    # worksheet.clear()

    maint_data = []
    int_data = []

    username = 'jdickman'
    passw = keyring.get_password('cas', username)

    jira = Jira(
    url = 'https://servicedesk.cenic.org',
    username = username,
    password = passw)

    for event in maint_events:
        row_list = []
        if re.match(regex, event['summary']):
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_date = str(datetime.fromisoformat(start))
            start_day = start_date.split(' ')[0]
            start_time = (start_date.split(' ')[1]).split('-')[0]
            summary = event['summary'].split(':')
            ticket = 'NOC-' + summary[0]

            jql_request = f'issue = {ticket}'
            try:
                requestor = jira.jql(jql_request, limit=1)['issues'][0]['fields']['reporter']['name']
            except:
                requestor = ''

            row_list.append(requestor)
            row_list.append(ticket)
            row_list.append('Maintenance')
            row_list.append(summary[1].strip())
            row_list.append(start_day)
            row_list.append(start_time)
            maint_data.append(row_list)

    lastRow = len(worksheet.col_values(1))
    firstRow = lastRow + 1
    worksheet.update(f'C{firstRow}:H', maint_data)

    for event in internal_events:
        row_list = []
        start = event['start'].get('dateTime', event['start'].get('date'))
        start_date = str(datetime.fromisoformat(start))
        start_day = start_date.split(' ')[0]
        start_time = (start_date.split(' ')[1]).split('-')[0]
        desc = event['summary']

        if full_ticket_re.match(event['summary']):
            ticket = full_ticket_re.match(event['summary']).group()
        elif ticket_re.match(event['summary']):
            ticket = 'NOC-' + ticket_re.match(event['summary']).group()
            print(ticket)
        else:
            ticket = ''

        requestor = event['creator']['email'].split('@')[0]
        row_list.append(requestor)
        row_list.append(ticket)
        row_list.append('Internal')
        row_list.append(desc)
        row_list.append(start_day)
        row_list.append(start_time)
        int_data.append(row_list)

    lastRow = len(worksheet.col_values(4))
    firstRow = lastRow + 1
    worksheet.update(f'C{firstRow}:H', int_data)


if __name__ == '__main__':
    main()
