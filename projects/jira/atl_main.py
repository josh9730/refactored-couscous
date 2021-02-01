from atlassian import Jira, Confluence
from gspread_pandas import Spread
from datetime import datetime, timedelta
import pandas as pd
import keyring
import gspread


class Logins:

    def __init__(self, username):
        self.username = username
        self.password = keyring.get_password('cas', self.username)

    def jira_login(self):
        jira = Jira(
            url = 'https://servicedesk.cenic.org',
            username = self.username,
            password = self.password)

        return jira

    def conf_login(self):
        confluence = Confluence(
            url = 'https://documentation.cenic.org/',
            username = self.username,
            password = self.password)

        return confluence


class AtlassianStuff(Logins):

    def __init__(self, username, sheet_key):
       self.jira = Logins(username).jira_login()
       self.confluence = Logins(username).conf_login()
       self.sheet_key = sheet_key

    def outages(self, jql_request):
        """Get all outage tickets tagged with JQ:

        Args:
            jql_request (str): JQL search criteria
        """

        name = 'outages'
        gsheet = Spread(self.sheet_key, name)

        results = self.jira.jql(jql_request, limit=100, fields=['key','summary'])
        df = pd.json_normalize(results['issues'])
        FoI = ['key', 'fields.summary']
        gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True)

    def open_rh(self, jql_request):
        """Get all open RH tickets

        Args:
            jql_request (str): JQL search criteria
        """

        name = 'RH_bulk'
        gsheet = Spread(self.sheet_key, name)

        results = self.jira.jql(jql_request, limit=100, fields=['assignee','reporter','key','summary','updated','status'])
        df = pd.json_normalize(results['issues'])
        FoI = ['fields.assignee.name','fields.reporter.name','key', 'fields.summary','fields.updated','fields.status.name']
        gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True)

    def core_tickets(self, engineer, jql_request):
        """Get all open tickets for Core

        Args:
            engineer (list): Engineers to pull tickets for
            jql_request (str): JQL search criteria
        """

        name = 'Bulk'
        gsheet = Spread(self.sheet_key, name)
        j = 65

        for i in engineer:

            results = self.jira.jql(jql_request.format(engineer = i), limit=500, fields=['assignee','key','summary','customfield_10209','updated'])
            df = pd.json_normalize(results['issues'])
            k = chr(j) # convert integer to ascii (uppercase letter)

            if i != 'sbellamine':# Sana has no milestones

                FoI = ['fields.assignee.name','key', 'fields.summary','fields.customfield_10209.value','fields.updated']
                if j == 65:
                    gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True, start=f'{k}1') # clear and push to sheet
                else:
                    gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=False, start=f'{k}1')

            else:

                FoI = ['fields.assignee.name','key', 'fields.summary', 'fields.updated']
                gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=False, start=f'{k}1')

            j += 5 # increment for cell

    def update_rotating_bucket(self, bucket, hours):
        """Update rotation buckets (shipping and EngRv)
        Allocation is per week
        """

        last_week = (datetime.today() - timedelta(weeks=1)).strftime('%Y-%m-%d')

        for i in bucket:

            start_date = self.jira.issue_field_value(i, 'customfield_10410')
            orig_est = {'timetracking': {'originalEstimate': str(hours)+ 'h'}}
            self.jira.update_issue_field(i, orig_est)

            if start_date == last_week:
                # Rotates the previous week's bucket to end of rotation

                new_start = (datetime.today() + timedelta(weeks=(len(bucket)-1))).strftime('%Y-%m-%d')
                new_end = (datetime.today() + timedelta(weeks=(len(bucket)-1), days=5)).strftime('%Y-%m-%d')

                field_start = {'customfield_10410': new_start}
                field_end = {'customfield_10411': new_end}

                self.jira.update_issue_field(i, field_start)
                self.jira.update_issue_field(i, field_end)

    def update_circuit(self, bucket, hours):
        """Update circuit deployment bucket based on # of active circuits
        """

        gc = gspread.oauth()
        sh = gc.open('Core Tickets')
        worksheet = sh.worksheet('Tables')

        # Get # of active circuits, eng_list must match yaml (order in yaml)
        engineer = [
            worksheet.get('C2')[0][0],
            worksheet.get('C3')[0][0],
            worksheet.get('C4')[0][0],
            worksheet.get('C5')[0][0]
        ]

        new_start = datetime.today().strftime('%Y-%m-%d')
        new_end = (datetime.today() + timedelta(weeks=(len(bucket)-1), days=5)).strftime('%Y-%m-%d')

        # Get time in hours - # of circuits * hours/circuit * 4 (weeks), and update list
        for i, circuits in enumerate(engineer):
            engineer[i] = str(int(circuits) * hours * 4) + 'h'

        # Update buckets - move start/end ahead one week, update hours
        for i, ticket in enumerate(bucket):
            field_start = {'customfield_10410': new_start}
            field_end = {'customfield_10411': new_end}
            orig_est = {'timetracking': {'originalEstimate': engineer[i]}}

            self.jira.update_issue_field(ticket, field_start)
            self.jira.update_issue_field(ticket, field_end)
            self.jira.update_issue_field(ticket, orig_est)