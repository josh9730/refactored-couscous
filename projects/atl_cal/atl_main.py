from atlassian import Jira, Confluence
from gspread_pandas import Spread
from datetime import date, datetime, timedelta
import pandas as pd
import keyring
import gspread
import time
import json


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


class JiraStuff(Logins):

    def __init__(self, username, sheet_key=''):
       self.jira = Logins(username).jira_login()
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
            k = chr(j)

            if i != 'sbellamine': # Sana has no milestones

                FoI = ['fields.assignee.name','key', 'fields.summary','fields.customfield_10209.value','fields.updated']
                if j == 65:
                    gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True, start=f'{k}1') # clear and push to sheet
                else:
                    gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=False, start=f'{k}1')

            else:

                FoI = ['fields.assignee.name','key', 'fields.summary', 'fields.updated']
                gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=False, start=f'{k}1')

            j += 5 # increment for cell

    def circuits(self, jql_request):
        """Retrieve all tickets with a Milestone in M4 - M9, push to sheet, and update how long the ticket has been in that milestone.

        circuits_raw: sheet to push unstructured data from Jira to
        Circuits: filtered sheet, retrieve ordered list of tickets from
        circuits.json: DF stored as json, ticket number to Milestone & Date

            1. Get JQL and push to sheet
            2. open circuits.json, create (from sheet) lists of tickets and milestones
            3. Iterate over list of tickets
            4. Push Milestone date and days in milestone to sheet
            5. Overwrite circuits.json (in case new circuits are added or dates change)

        """

        # get jql and create DF
        results = self.jira.jql(jql_request)
        df = pd.json_normalize(results['issues'])
        FoI = ['fields.assignee.name','fields.customfield_10209.value','key', 'fields.summary','fields.updated']
        df['fields.updated'] = df['fields.updated'].str.slice(start=0, stop=10) # get date field from isoformat

        # push to gsheet
        name = 'circuits_raw'
        gsheet = Spread(self.sheet_key, name)
        gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True)

        time.sleep(2) # delay for query to run

        # get current tickets & milestones from gsheet
        gc = gspread.oauth()
        sh = gc.open('Core Tickets')
        worksheet = sh.worksheet('Circuits')
        tickets_list = worksheet.col_values(1)[1:]
        milestones_list = worksheet.col_values(6)[1:]

        # Clear previous entries
        previous_tickets = worksheet.col_values(7)[1:]
        length = len(previous_tickets)
        clear_list = []
        for _ in range(length):
            clear_list.append(['', ''])
        worksheet.update(f'G2:H{length+1}', clear_list)

        # read from 'database'
        circuits_df = pd.read_json('/Users/jdickman/Git/refactored-couscous/projects/atl_cal/circuits.json')

        # lopp to create milestone updated date and days in milestone lists
        today = date.today()
        days_list = []
        milestones_date = []
        for index, ticket in enumerate(tickets_list):

            try:
                # if ticket exists in DF
                if circuits_df.at[ticket, 'Current Milestone'] == milestones_list[index]:

                    # if milestone has NOT been updated
                    ticket_date = circuits_df.at[ticket, 'Date Updated']
                    date_iso =  date.fromisoformat(str(ticket_date))
                    num_days = str(today - date_iso).split(' ')[0]

                    if num_days == '0:00:00': num_days = '0'

                else:
                    # if milestone has been updated
                    circuits_df.at[ticket, 'Current Milestone'] = milestones_list[index]
                    circuits_df.at[ticket, 'Date Updated'] = today
                    num_days = '0'
                    ticket_date = str(today)

            except:
                # if ticket not in DF
                circuits_df.at[ticket] = [milestones_list[index], str(today)]
                num_days = '0'
                ticket_date = str(today)

            days_list.append(num_days)
            milestones_date.append(ticket_date)

        # push to 'database'
        circuits_df.to_json('/Users/jdickman/Git/refactored-couscous/projects/atl_cal/circuits.json', indent=2)

        # Create DF
        data_tuples = list(zip(milestones_date, days_list))
        col = ['Milestone Date', 'Days in Milestone']
        upload_df = pd.DataFrame(data_tuples, columns=col)

        # push to gsheet
        name = 'Circuits'
        gsheet = Spread(self.sheet_key, name)
        gsheet.df_to_sheet(upload_df, index=False, sheet=name, start='G1')

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
        """Update circuit deployment bucket based on # of active circuits"""

        gc = gspread.oauth()
        sh = gc.open('Core Tickets')
        worksheet = sh.worksheet('Tables')

        # Get # of active circuits, eng_list must match yaml order
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

    def update_jira_link(self, ticket, page_title):
        """Updates links in Jira ticket (adding link via API to confluence is unidirectional)

        Args:
            ticket (str): full ticket # (NOC-123456)
            page_title (str): Title (with spaces), ie 'LAX-AGG10 SR Maintnenace`
        """

        link_title = page_title.replace(" ", "+")
        page_url = f'https://documentation.cenic.org/display/Core/{link_title}'
        self.jira.create_or_update_issue_remote_links(ticket, page_url, page_title, relationship='mentioned in')

    def create_issue(self, cust_fields):
        
        self.jira.issue_create(fields=cust_fields)


class ConfluenceStuff(Logins):

    def __init__(self, username):
        self.confluence = Logins(username).conf_login()

    def page_update_wiki_format(self, parent_id, page_title, page_body):
        """Update or Create Confluence page

        Args:
            parent_id (str): Page ID number of the parent page (where the page will be created if needed)
            page_title (str): Title of page
            page_body (str): Body of page (in 'wiki' format)
        """

        self.confluence.update_or_create(parent_id, page_title, page_body, representation='wiki')