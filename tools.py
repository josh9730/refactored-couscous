import pickle
import os
import keyring
import pygsheets
import pandas as pd
from datetime import datetime, timedelta
from atlassian import Jira, Confluence
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


"""
hide file paths
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
        engrv_order = [i["summary"].split(" ")[0] for i in engrv_rotation["items"]]
        return engrv_order


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
            df = pd.json_normalize(results["issues"])[
                [
                    "fields.assignee.name",
                    "fields.summary",
                    "key",
                    "fields.status.name",
                    "fields.updated",
                    "fields.customfield_10209.value",
                ]
            ]
            # trim to YYYY-MM-DD format
            df["fields.updated"] = df["fields.updated"].apply(lambda x: x[:10])
            full_df = pd.concat([full_df, df])
        tickets_sheet.set_dataframe(full_df, start=(1, 1), extend=True, nan="")

    def update_engrv(self, bucket_dict: dict, hours: int, engrv_url: str):
        """Update rotating buckets for EngRv. Allocation is per week, gets the upcoming month's order"""
        today = datetime.today()
        engineer_list = GCalTools().get_engrv(engrv_url)

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

    def resources_reporting(self):
        """Pull this week's report of resource allocations from BP."""
        pass
