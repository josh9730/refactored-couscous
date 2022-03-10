import pickle
import os
import keyring
import numpy as np
import pygsheets
import pandas as pd
from datetime import datetime, timedelta
from atlassian import Jira, Confluence
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


"""
Tools for Jira, Confluence, and Google Calendar.
"""


class GCalTools:
    def __init__(self):

        # If modifying these scopes, delete the file token.pickle.
        SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
        home_dir = os.getenv("HOME")
        creds = None
        if os.path.exists(f"{home_dir}/Google Drive/My Drive/Scripts/token.pickle"):
            with open(
                f"{home_dir}/Google Drive/My Drive/Scripts/token.pickle",
                "rb",
            ) as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    f"{home_dir}/Google Drive/My Drive/Scripts/credentials.json",
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)

            with open(
                f"{home_dir}/Google Drive/My Drive/Scripts/token.pickle",
                "wb",
            ) as token:
                pickle.dump(creds, token)
        self.service = build("calendar", "v3", credentials=creds)

    def cal_checks_auth(self, wb_title: str):
        """Return pysheets object for Core Tickets sheet."""
        sheet_title = "Calendar Checks"
        home_dir = os.getenv("HOME")
        client = pygsheets.authorize(
            client_secret=f"{home_dir}/Google Drive/My Drive/Scripts/client_secret.json"
        )
        sheet = client.open(sheet_title).worksheet_by_title(wb_title)
        return sheet

    def get_engrv(self, engrv_url: str) -> list:
        """Get engineer on EngRv, to be run each Monday"""

        now = (datetime.utcnow() - timedelta(days=2)).isoformat() + "Z"
        d1 = (datetime.utcnow() + timedelta(weeks=4)).isoformat() + "Z"
        engrv_rotation = (
            self.service.events()
            .list(
                calendarId=engrv_url,
                q="EngRv",
                singleEvents=True,
                orderBy="startTime",
                timeMin=now,
                timeMax=d1,
            )
            .execute()
        )

        # filter out for just the names from the gcal entry
        return [i["summary"].split(" ")[0] for i in engrv_rotation["items"]]

    def return_calendar(self, date1: str, date2: str, cal_url: str) -> pd.DataFrame:
        """Returns DF of events from specified calendar."""
        events = (
            self.service.events()
            .list(
                calendarId=cal_url,
                timeMin=date1,
                timeMax=date2,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        ).get("items", [])
        return pd.json_normalize(events)[
            [
                "summary",
                "creator.email",
                "description",
                "start.dateTime",
                "end.dateTime",
            ]
        ]

    def weekly_events(self, maint_cal_url: str, internal_cal_url: str):
        now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        d1 = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"

        # return maintenance calendar events and create DF
        maint_events_df = self.return_calendar(d1, now, maint_cal_url)
        maint_events_df = maint_events_df[
            maint_events_df["summary"].str.contains("CENIC")
        ]  # filter only CENIC Maintenance
        maint_events_df["calendar"] = "Maint. Cal"

        # return internal calendar events and create df
        internal_cal_df = self.return_calendar(d1, now, internal_cal_url)
        internal_cal_df["calendar"] = "Internal Cal"

        # combine dfs and normalize
        df = pd.concat([maint_events_df, internal_cal_df])
        df["creator"] = df["creator.email"].apply(lambda x: x.replace("@cenic.org", ""))
        df["end.dateTime"] = df["end.dateTime"].apply(
            lambda x: x[11:-6]
        )  # trim to hours/minutes only
        df[["start_date", "start_time"]] = df["start.dateTime"].str.split(
            "T", expand=True
        )
        df["start_time"] = df["start_time"].apply(
            lambda x: x[:-6]
        )  # extract hours/minutes only
        df["summary"] = df["summary"].apply(
            lambda x: "NOC-" + x if x[0].isdigit() else x
        )  # Add NOC- if starts with ticket number only
        df["ticket"] = df["summary"].str.extract(
            r"((?:NOC|COR|SYS|ISO)-[0-9]{3,7})", expand=True
        )  # extract ticket from summary for creating link

        # Add columns from related Jira ticket
        ticket_lists = JiraTools().events_jira_outputs(list(df["ticket"]))
        df["assignee"] = ticket_lists[0]
        df["reporter"] = ticket_lists[1]
        df["ticket_sum"] = ticket_lists[2]
        df["last_comment"] = ticket_lists[3]

        df["ticket"] = df["ticket"].apply(
            lambda x: f'=HYPERLINK("https://servicedesk.cenic.org/browse/{x}", "{x}")'
        )

        df = df[
            [
                "ticket",
                "creator",
                "assignee",
                "reporter",
                "ticket_sum",
                "summary",
                "calendar",
                "start_date",
                "start_time",
                "end.dateTime",
                "description",
                "last_comment",
            ]
        ]

        tickets_sheet = self.cal_checks_auth(str(datetime.now().year))
        first_row = len(tickets_sheet.get_col(1, include_tailing_empty=False)) + 1
        tickets_sheet.set_dataframe(
            df, start=(first_row, 1), copy_head=False, extend=True, nan=""
        )


class ConflTools:
    def __init__(self):
        cas_user = keyring.get_password("cas", "user")
        cas_pass = keyring.get_password("cas", cas_user)
        confl_url = keyring.get_password("confl", "url")
        self.confl = Confluence(url=confl_url, username=cas_user, password=cas_pass)

    def push_new_page(self, parent_page_id: str, page_title: str):
        """Push Wiki formatted .txt file to Confluence as a new page.

        Formatting guide:
        https://confluence.atlassian.com/doc/confluence-wiki-markup-251003035.html
        """
        with open("doc.txt", "r") as f:
            doc = f.read()
        self.confl.update_or_create(
            parent_page_id, page_title, doc, representation="wiki"
        )


class JiraTools:
    def __init__(self):
        cas_user = keyring.get_password("cas", "user")
        cas_pass = keyring.get_password("cas", cas_user)
        jira_url = keyring.get_password("jira", "url")
        self.jira = Jira(url=jira_url, username=cas_user, password=cas_pass)

    def events_jira_outputs(self, tickets_list: list):
        """Return several output lists based on input ticket list."""
        assignee_list, reporter_list, ticket_sum_list, comments_list = [], [], [], []
        for ticket in tickets_list:
            if isinstance(ticket, str):
                # ticket will be float nan if no ticket is on event
                output = self.jira.issue(ticket)
                assignee_list.append(output["fields"]["assignee"]["name"])
                reporter_list.append(output["fields"]["reporter"]["name"])
                ticket_sum_list.append(output["fields"]["summary"])
                comments_list.append(
                    output["fields"]["comment"]["comments"][-1]["body"]
                )  # get most recent comment
            else:
                assignee_list.append("")
                reporter_list.append("")
                ticket_sum_list.append("")
                comments_list.append("")
        return assignee_list, reporter_list, ticket_sum_list, comments_list

    def core_tickets_auth(self, wb_title: str):
        """Return pysheets object for Core Tickets sheet."""
        sheet_title = "Core Tickets"
        home_dir = os.getenv("HOME")
        client = pygsheets.authorize(
            client_secret=f"{home_dir}/Google Drive/My Drive/Scripts/client_secret.json"
        )
        sheet = client.open(sheet_title).worksheet_by_title(wb_title)
        return sheet

    def core_tickets(self, engineer: list, jql_request: str):
        """Get all open tickets for engineers"""
        tickets_sheet = self.core_tickets_auth("Bulk")
        tickets_sheet.clear()

        full_df = pd.DataFrame()
        for i in engineer:
            results = self.jira.jql(
                jql_request.format(engineer=i),
                limit=500,
                fields=[
                    "assignee",
                    "key",
                    "status",
                    "summary",
                    "updated",
                    "customfield_10209",
                ],
            )
            df = pd.json_normalize(results["issues"]).filter(
                [
                    "fields.assignee.name",
                    "fields.summary",
                    "key",
                    "fields.status.name",
                    "fields.updated",
                    "fields.customfield_10209.value",
                ]
            )
            # trim to YYYY-MM-DD format
            df["fields.updated"] = df["fields.updated"].apply(lambda x: x[:10])
            full_df = pd.concat([full_df, df])
        tickets_sheet.set_dataframe(full_df, start=(1, 1), extend=True, nan="")

    def update_engrv(self, engineer_list: str, bucket_dict: dict, hours: int):
        """Update rotating buckets for EngRv. Allocation is per week, gets the upcoming month's order"""
        today = datetime.today()
        for count, eng in enumerate(engineer_list):
            ticket = bucket_dict[eng]
            self.jira.issue_update(
                ticket,
                {
                    "timetracking": {"originalEstimate": str(hours) + "h"},
                    "customfield_10410": (today + timedelta(days=count * 7)).strftime(
                        "%Y-%m-%d"
                    ),
                    "customfield_10411": (
                        today + timedelta(days=count * 7 + 4)
                    ).strftime("%Y-%m-%d"),
                },
            )

    def update_circuit(self, hours: int):
        """Updates resource tickets for circuit deployment work.

        Args:
            hours (int): Hours/Circuit for each engineer

        Retrieves the following from gsheets:
        - list of # of circuits, per engineer (named_range)
        - list of resource tickets for circuits, per engineer (named_range)

        """
        circuit_sheet = self.core_tickets_auth("Tables")

        # named range of active circuits / engineer, and range of engineer's tickets
        active_circuits = circuit_sheet.get_named_range("active_circuits")
        resources_tickets = circuit_sheet.get_named_range("resource_tickets")

        circuits_list = [i[0].value for i in active_circuits.cells]
        tickets_list = [i[0].value for i in resources_tickets.cells]

        # new_start is today, new_end is
        new_start = datetime.today().strftime("%Y-%m-%d")
        new_end = (datetime.today() + timedelta(weeks=3, days=4)).strftime("%Y-%m-%d")

        # Get time in hours - # of circuits * hours/circuit * 4 (weeks), and update list
        weeks = 4
        hours_list = [
            str(int(circuits) * hours * weeks) + "h" for circuits in circuits_list
        ]

        # Update buckets - move start/end ahead one week, update hours
        for i, ticket in enumerate(tickets_list):
            self.jira.issue_update(
                ticket,
                {
                    "timetracking": {"originalEstimate": hours_list[i]},
                    "customfield_10410": new_start,
                    "customfield_10411": new_end,
                },
            )

    def resources_reporting(self, engineers: list, jql_request: str):
        """Pull this week's report of resource allocations from BP.

        - get all In Progress tickets by engineer with org_est set
        - start_date of monday, end_date of friday
        - append to sheet
        """
        resources_sheet = self.core_tickets_auth("resources")
        engineers.remove("jdickman")
        engineers.remove("sshibley")

        full_df = pd.DataFrame()
        for i in engineers:
            results = self.jira.jql(
                jql_request.format(engineer=i),
                limit=50,
                fields=[
                    "assignee",
                    "key",
                    "summary",
                    "timetracking",
                    "customfield_10410",
                    "customfield_10411",
                ],
            )
            df = pd.json_normalize(results["issues"]).filter(
                [
                    "fields.assignee.name",
                    "fields.summary",
                    "key",
                    "fields.timetracking.originalEstimateSeconds",
                    "fields.customfield_10410",
                    "fields.customfield_10411",
                ]
            )
            df = df.rename(
                columns={
                    "fields.assignee.name": "assignee",
                    "fields.summary": "summary",
                }
            )
            df["key"] = df["key"].apply(
                lambda x: f'=HYPERLINK("https://servicedesk.cenic.org/browse/{x}", "{x}")'
            )

            # convert original estimate to hours
            # get original hours / day, multiply by 5 and divide by number of business
            # days to get hours allocated over the current week
            org_est_list = [
                int(i) / 3600 for i in df["fields.timetracking.originalEstimateSeconds"]
            ]
            df["weekly_hours"] = (
                org_est_list
                / np.busday_count(
                    list(df["fields.customfield_10410"]),
                    list(df["fields.customfield_10411"]),
                )
                * 5
            )
            df["weekly_hours"] = df["weekly_hours"].apply(lambda x: round(x, 2))

            # get previous monday as datetime string
            today = datetime.today()
            df["week_start"] = (today - timedelta(days=today.weekday())).strftime(
                "%Y-%m-%d"
            )

            df = df[
                [
                    "assignee",
                    "summary",
                    "key",
                    "weekly_hours",
                    "week_start",
                ]
            ]
            full_df = pd.concat([full_df, df])

        first_row = len(resources_sheet.get_col(1, include_tailing_empty=False)) + 1
        resources_sheet.set_dataframe(
            full_df, start=(first_row, 1), copy_head=False, extend=True, nan=""
        )
