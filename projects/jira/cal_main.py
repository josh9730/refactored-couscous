from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pickle
import os.path
import gspread
import re
import json
import keyring
from atl_main import Logins


class CalendarStuff:

    def __init__(self, username):
        self.jira = Logins(username).jira_login()

    def create_row(self, requestor, ticket, cal_type, desc, event):
        """Create row for each event.

        Returns:
            list: Will be appeneded to list of rows (of events)
        """

        dates = self.get_dates(event)

        row_list = []
        row_list.append(requestor)
        row_list.append(ticket)
        row_list.append(cal_type)
        row_list.append(desc)
        row_list.append(dates[0])
        row_list.append(dates[1])

        return row_list

    def get_dates(self, event):
        """Find start and end date from passed string.

        Returns:
            list: strings of start day and time
        """

        start = event['start'].get('dateTime', event['start'].get('date'))
        start_date = str(datetime.fromisoformat(start))
        start_day = start_date.split(' ')[0]
        start_time = (start_date.split(' ')[1]).split('-')[0]

        return start_day, start_time

    def get_maint_events(self, maint_events):
        """Get interesting data from Maintenance Calendar events

        Args:
            maint_events (list): List of Maintenance Calendar events

        Returns:
            list: list of rows
        """

        regex = re.compile(r'\d+:\sCENIC')
        maint_data = []

        for event in maint_events:

            if re.match(regex, event['summary']):

                summary = event['summary'].split(':')
                ticket = 'NOC-' + summary[0]
                desc = summary[1].strip()

                jql_request = f'issue = {ticket}'
                try:
                    requestor = self.jira.jql(jql_request, limit=1)['issues'][0]['fields']['reporter']['name']
                except:
                    requestor = ''

                maint_data.append(self.create_row(requestor, ticket, 'Maintenance', desc, event))

        return maint_data

    def get_int_events(self, internal_events):
        """Get interesting data from Internal Change events.

        Args:
            internal_events (list): List of Internal Change events

        Returns:
            list: list of rows
        """

        full_ticket_re = re.compile(r"(NOC|COR|DEV|SYS)-[0-9]{3,6}")
        ticket_re = re.compile(r"[0-9]{4,6}")
        int_data = []

        for event in internal_events:

            requestor = event['creator']['email'].split('@')[0]
            desc = event['summary']

            if full_ticket_re.match(event['summary']):
                ticket = full_ticket_re.match(event['summary']).group()
            elif ticket_re.match(event['summary']):
                ticket = 'NOC-' + ticket_re.match(event['summary']).group()
            else:
                ticket = ''

            int_data.append(self.create_row(requestor, ticket, 'Internal', desc, event))

        return int_data

    def weekly_events(self):
        """Get calendar events on maintenance and internal change calendar.
        """

        # if os.path.exists('token.pickle'):
        with open('/Users/jdickman/Git/refactored-couscous/projects/jira/token.pickle', 'rb') as token:
            creds = pickle.load(token)

        service = build('calendar', 'v3', credentials=creds)
        now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        d1 = ((datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z')

        # Call the Calendar API
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

        for i in range(2):
            if i == 0:
                cal_data = self.get_maint_events(maint_events)
                lastRow = len(worksheet.col_values(1))
            else:
                cal_data = self.get_int_events(internal_events)
                lastRow = len(worksheet.col_values(4))

            firstRow = lastRow + 1
            worksheet.update(f'C{firstRow}:H', cal_data)