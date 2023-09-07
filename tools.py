import re
from datetime import datetime, timedelta
from pathlib import Path

import keyring
import numpy as np
import pandas as pd
import pygsheets
import requests
from atlassian import Confluence, Jira
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

"""
Tools for Jira, Confluence, and Google Calendar.
"""

MILESTONE = "customfield_10209"
START_DATE = "customfield_10410"
END_DATE = "customfield_10411"
JUSTIFICATION = "customfield_11102"
SEGMENT = "customfield_11004"
CREDENTIALS_DIR = Path("~/Google Drive/My Drive/Scripts").expanduser()


def get_last_comment(comments: list) -> str:
    """Try/Except for returning last comment to handle IndexError if no comments."""
    try:
        return comments[-1:][0]["body"]
    except IndexError:
        return ""


def open_gsheet(sheet_title: str, workbook_title: str):
    """Open Google Sheet via pygsheets and return Sheet object."""
    client = pygsheets.authorize(credentials_directory=CREDENTIALS_DIR, local=True)
    return client.open(sheet_title).worksheet_by_title(workbook_title)


class GCalTools:
    def __init__(self):
        # If modifying these scopes, delete the file token.json.
        SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
        creds = None

        if CREDENTIALS_DIR.exists():
            creds = Credentials.from_authorized_user_file(
                CREDENTIALS_DIR.joinpath("gcal_token.json"), SCOPES
            )
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    f"{CREDENTIALS_DIR}/desktop_oauth_gcal.json", SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(f"{CREDENTIALS_DIR}/gcal_token.json", "w") as token:
                token.write(creds.to_json())

        try:
            self.service = build("calendar", "v3", credentials=creds)

        except HttpError as error:
            print("An error occurred: %s" % error)

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
        """Push DF of the previous week's maintenance and Internal Calendar events.

        Args:
            maint_cal_url (str): URL of Maintenance Calendar
            internal_cal_url (str): URL of Internal Change Calendar
        """
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
            lambda x: x[11:-6] if pd.notnull(x) else ""
        )  # trim to hours/minutes only

        df[["start_date", "start_time"]] = df["start.dateTime"].str.split(
            "T", expand=True
        )

        df["start_time"] = df["start_time"].apply(
            lambda x: x[:-6] if pd.notnull(x) else ""
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

        tickets_sheet = open_gsheet(
            "Calendar Checks",
            str(datetime.now().year),
            f"{self.creds_dir}/desktop_oauth_gsheet.json",
        )
        first_row = len(tickets_sheet.get_col(1, include_tailing_empty=False)) + 1
        tickets_sheet.set_dataframe(
            df, start=(first_row, 1), copy_head=False, extend=True, nan=""
        )


class AtlassianBase:
    def __init__(self):
        self.cas_user = keyring.get_password("cas", "user")
        self.cas_pass = keyring.get_password("cas", self.cas_user)
        self.confl_url = keyring.get_password("confluence", "url")
        self.jira_url = keyring.get_password("jira", "url")


class ConflTools(AtlassianBase):
    def __init__(self):
        super().__init__()
        self.confl = Confluence(
            url=self.confl_url, username=self.cas_user, password=self.cas_pass
        )

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


class JiraTools(AtlassianBase):
    def __init__(self):
        super().__init__()
        self.jira = Jira(
            url=self.jira_url, username=self.cas_user, password=self.cas_pass
        )

    def cor_project_updates(self, engineer: list, jql: str) -> None:
        """Return ticket updates, creation, resolution from the COR Jira
        Software project for the past 5 days. To be run each Friday.
        """

        ticket_updates = open_gsheet("Core Tickets", "updates")
        ticket_updates.clear()

        results = self.jira.jql(
            jql, limit=100, fields=["assignee", "key", "summary", "updated", "comment"]
        )

        columns = {
            "key": "ticket",
            "fields.assignee.name": "assignee",
            "fields.summary": "summary",
            "fields.updated": "updated",
            "fields.comment.comments": "last_comment",
        }

        df = pd.json_normalize(results["issues"]).filter(list(columns.keys()))
        df.rename(
            columns,
            axis=1,
            inplace=True,
        )

        # filter for the body of the most recent comment
        df["last_comment"] = df["last_comment"].apply(lambda x: get_last_comment(x))

        # remove rows with BP update comments, based on comment starts with 'Task COR-XXXX moved via...'
        df = df[~df["last_comment"].str.startswith("Task COR-")]

        # create hyperlink for key
        df["ticket"] = df["ticket"].apply(
            lambda x: f'=HYPERLINK("https://servicedesk.cenic.org/browse/{x}", "{x}")'
        )

        # trim updated date to YYYY-MM-DD
        df["updated"] = df["updated"].apply(lambda x: x.split("T")[0])

        ticket_updates.set_dataframe(df, start=(2, 1), extend=True, nan="")

    def events_jira_outputs(self, tickets_list: list):
        """Return several output lists based on input ticket list.
        Used for adding Jira data to gCal weekly reporting.
        """
        assignee_list, reporter_list, ticket_sum_list, comments_list = [], [], [], []
        for ticket in tickets_list:
            if isinstance(ticket, str):
                print(ticket)
                # ticket will be float nan if no ticket is on event
                output = self.jira.issue(ticket)
                try:
                    assignee_list.append(output["fields"]["assignee"]["name"])
                except TypeError:
                    assignee_list.append("Unassigned")
                ticket_sum_list.append(output["fields"]["summary"])

                try:
                    reporter_list.append(output["fields"]["reporter"]["name"])
                except TypeError:  # no reporter
                    reporter_list.append("")

                try:
                    comments_list.append(
                        output["fields"]["comment"]["comments"][-1]["body"]
                    )  # get most recent comment
                except IndexError:  # if no comments
                    comments_list.append("")
            else:
                assignee_list.append("")
                reporter_list.append("")
                ticket_sum_list.append("")
                comments_list.append("")
        return assignee_list, reporter_list, ticket_sum_list, comments_list

    def core_tickets(self, engineer: list, jql_request: str):
        """Get all open tickets for engineers"""
        tickets_sheet = open_gsheet("Core Tickets", "Bulk")
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
                    "labels",
                    "summary",
                    "updated",
                    MILESTONE,
                ],
            )
            df = pd.json_normalize(results["issues"]).filter(
                [
                    "fields.assignee.name",
                    "fields.summary",
                    "key",
                    "fields.status.name",
                    "fields.updated",
                    f"fields.{MILESTONE}.value",
                    "fields.labels",
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
                    START_DATE: (today + timedelta(days=count * 7)).strftime(
                        "%Y-%m-%d"
                    ),
                    END_DATE: (today + timedelta(days=count * 7 + 4)).strftime(
                        "%Y-%m-%d"
                    ),
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
        circuit_sheet = open_gsheet("Core Tickets", "Tables")

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
                    START_DATE: new_start,
                    END_DATE: new_end,
                },
            )

    def resources_reporting(self, engineers: list, jql_request: str):
        """Pull this week's report of resource allocations from BP.

        - get all In Progress tickets by engineer with org_est set
        - start_date of monday, end_date of friday
        - append to sheet
        """
        resources_sheet = open_gsheet("Core Tickets", "resources")
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
                    START_DATE,
                    END_DATE,
                ],
            )
            df = pd.json_normalize(results["issues"]).filter(
                [
                    "fields.assignee.name",
                    "fields.summary",
                    "key",
                    "fields.timetracking.originalEstimateSeconds",
                    f"fields.{START_DATE}",
                    f"fields.{END_DATE}",
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
            start_date_list = list(df[f"fields.{START_DATE}"])
            end_date_list = list(df[f"fields.{END_DATE}"])
            df["weekly_hours"] = (
                org_est_list / np.busday_count(start_date_list, end_date_list) * 5
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

    def get_cpe_tracker_info(self) -> None:
        """Used for the CPE Hardware Tracker, for each active deployment ticket the milestones and
        purchase ticket statuses are updated.

          - Removes tickets that are resolved from Active and places them in the Resolved tab
          - Updates Milestone
          - For CPE, Modem, DF purchase tickets, adds text to indicate delivery status
        """

        def get_milestone(ticket):
            try:
                return self.jira.issue_field_value(ticket, MILESTONE)["value"]
            except (requests.exceptions.HTTPError, TypeError):
                return ""

        def get_delivered(ticket):
            if ticket:
                ticket_data = self.jira.issue(ticket)["fields"]
                status = ticket_data["status"]["name"]
                assignee = ticket_data["assignee"]["name"]
                reporter = ticket_data["reporter"]["name"]
                last_comment = ticket_data["comment"]["comments"][-1]["body"].upper()

                if status == "Withdrawn":
                    return "Withdrawn"
                elif (assignee == reporter) or (status == "Resolved"):
                    return "Delivered"
                elif "PARTIAL" in last_comment:
                    return "Partial Delivery"
                else:
                    return "Not Delivered"
            else:
                return ""

        active_sheet = open_gsheet("CPE Hardware Tracker", "Active")
        resolved_sheet = open_gsheet("CPE Hardware Tracker", "Resolved")
        active_df = active_sheet.get_as_df(start="A2", include_tailing_empty=False)
        resolved_df = resolved_sheet.get_as_df(include_tailing_empty=False)

        # get status and trim resolved; drop unneeded Status
        active_df["Status"] = active_df["Deployment Ticket"].apply(
            lambda x: self.jira.get_issue_status(x)
        )
        new_resolved_df = active_df[active_df["Status"] == "Resolved"]
        active_df = active_df[active_df["Status"] != "Resolved"]
        active_df = active_df.drop("Status", axis=1)
        new_resolved_df = new_resolved_df.drop("Status", axis=1)

        # Get Milestones and hardware delivery data
        active_df["Ticket Milestone"] = active_df["Deployment Ticket"].apply(
            lambda x: get_milestone(x)
        )
        for col in ("CPE", "Modem", "Dark Fiber Equip."):
            active_df[f"{col} Delivered"] = active_df[f"{col} Purchase Ticket"].apply(
                lambda x: get_delivered(x)
            )

        # combine resolved DFs
        resolved_df = pd.concat([resolved_df, new_resolved_df])
        active_sheet.clear(start="A3")
        resolved_sheet.clear(start="A2")
        active_sheet.set_dataframe(
            active_df, start="A3", copy_head=False, extend=True, nan=""
        )
        resolved_sheet.set_dataframe(
            resolved_df, start="A2", copy_head=False, extend=True, nan=""
        )

    def purchases_tracking(self, core: list) -> None:
        """Update Purchase Tracker, run each week.

        - Pulls all active purchase tickets by engineer as df
        - Updates certain columns, including extracting PO
        - Drop unneeded columns and push to sheet
        - Manually consolidate Justification and other fields towards the table on gSheet
        """

        def get_po(comments: list[dict], date: bool = False) -> str:
            """Return either PO number or PO Date.

            Not sure how to run Series.apply() on one column to return two
            new columns, this could be simplified.
            """
            for i in comments:
                po = re.search(r"PO.{0,3}[0-9]{5}", i["body"])
                if po:
                    if date:
                        return i["created"].split("T")[0]
                    else:
                        return re.findall(r"\d+", po.group())[0]
            return "PO not found"

        def check_status(
            comments: list[dict], status: str, assignee: str, reporter: str
        ) -> str:
            """Tries to guess ticket status based on critiera below. Should not
            be viewed as authoritative.
            """
            try:
                last_comment = comments[-1]["body"].upper()
            except IndexError:  # no comments
                return ""
            else:
                if status == "Withdrawn":
                    return "Withdrawn"
                elif (assignee == reporter) or (status == "Resolved"):
                    return "Delivered"
                elif "PARTIAL" in last_comment:
                    return "Partial Delivery"
                else:
                    return "Not Delivered"

        # return in-progress purchases
        jql = f"""project = Purchasing and
            status not in (Resolved, Denied, "Pending Core Approval", "Pending Director Approval", "Pending Finance Approval")
            and reporter in ({", ".join(map(str, core))})
        """

        results = self.jira.jql(
            re.sub(r"\s+", " ", jql),
            limit=200,
            fields=[
                "assignee",
                "reporter",
                "key",
                "summary",
                "status",
                JUSTIFICATION,
                SEGMENT,
                "comment",
            ],
        )

        df = pd.json_normalize(results["issues"]).filter(
            [
                "fields.assignee.name",
                "fields.reporter.name",
                "fields.summary",
                "key",
                "fields.status.name",
                f"fields.{JUSTIFICATION}",
                f"fields.{SEGMENT}.value",
                "fields.comment.comments",
            ]
        )
        df.rename(
            columns={
                "key": "Key",
                "fields.assignee.name": "assignee",
                "fields.reporter.name": "Reporter",
                "fields.summary": "Summary",
                "fields.status.name": "Ticket Status",
                f"fields.{JUSTIFICATION}": "Justification",
                f"fields.{SEGMENT}.value": "Segment",
                "fields.comment.comments": "comments",
            },
            inplace=True,
        )

        df["PO"] = df["comments"].apply(get_po)
        df["PO Date"] = df["comments"].apply(lambda x: get_po(x, date=True))
        df["HW Status"] = df.apply(
            lambda x: check_status(
                x["comments"], x["Ticket Status"], x["assignee"], x["Reporter"]
            ),
            axis=1,
        )

        df = df[
            [
                "Ticket Status",
                "Key",
                "Reporter",
                "Segment",
                "PO",
                "PO Date",
                "HW Status",
                "Summary",
                "Justification",
            ]
        ]

        data_sheet = open_gsheet("Core Purchase Tracking", "data")
        data_sheet.clear(start="A8")
        data_sheet.set_dataframe(df, start=(8, 1), extend=True, nan="")

        # add tickets pending manager approval
        mgr_jql = f"""project = Purchasing and status in
            ("Pending Core Approval") and reporter in ({", ".join(map(str, core))})
        """

        mgr_results = self.jira.jql(
            re.sub(r"\s+", " ", mgr_jql),
            limit=200,
            fields=[
                "key",
                "reporter",
                SEGMENT,
                "summary",
                JUSTIFICATION,
            ],
        )

        mgr_df = pd.json_normalize(mgr_results["issues"]).filter(
            [
                "key",
                "fields.reporter.name",
                f"fields.{SEGMENT}.value",
                "fields.summary",
                f"fields.{JUSTIFICATION}",
            ]
        )

        mgr_df.rename(
            columns={
                "key": "Key",
                "fields.reporter.name": "Reporter",
                "fields.summary": "Summary",
                f"fields.{JUSTIFICATION}": "Justification",
                f"fields.{SEGMENT}.value": "Segment",
            },
            inplace=True,
        )

        data_sheet = open_gsheet("Core Purchase Tracking", "mgr_approval")
        data_sheet.clear()
        data_sheet.set_dataframe(mgr_df, start=(1, 1), extend=True, nan="")

    def la2_migration_status(self):
        tickets_sheet = open_gsheet("LA2 Migration - Deployment Tracker", "Sheet1")
        tickets_list = tickets_sheet.get_col(
            1, include_tailing_empty=False, returnas="cell"
        )
        tickets_list.pop(0)  # remove header

        for ticket in tickets_list:
            ticket_data = self.jira.issue(ticket.value)["fields"]

            comments = ticket_data["comment"]["comments"]
            if len(comments) > 0:
                for i, comment in enumerate(comments):
                    if "moved via" in comment["body"]:
                        comments.pop(i)

            if len(comments) > 0:  # if still comments after removing BP updates
                last_comment = comments[-1:][0]["body"]
                updated = comments[-1:][0]["updated"].split("T")[0]
                author = comments[-1:][0]["author"]["displayName"]
            else:
                last_comment, updated, author = "", "", ""

            update_vals = [
                ticket_data["assignee"]["displayName"],
                ticket_data["status"]["name"],
                ticket_data[END_DATE],
                last_comment,
                updated,
                author,
            ]
            tickets_sheet.update_row(ticket.row, update_vals, col_offset=7)

    def get_ticket_summary(self, ticket: str) -> str:
        return self.jira.get_issue(ticket, fields=["summary"])["fields"]["summary"]

    def create_ticket(
        self,
        master_ticket: str,
        title: str,
        project_key: str = "COR",
        ticket_type: str = "Task",
    ) -> str:
        """Create ticket in Jira.

        JIRA_CORE_ORGANIZATION: [JIRA_CORE_ORGANIZATION_ID],
        """
        new_ticket = self.jira.create_issue(
            fields={
                "summary": title,
                "project": {
                    "key": project_key,
                },
                "issuetype": {
                    "name": ticket_type,
                },
            }
        )["key"]
        self._create_ticket_link(master_ticket, new_ticket)
        return new_ticket

    def _create_ticket_link(self, master_ticket: str, new_ticket: str) -> None:
        """Create Link between master and new ticket."""
        self.jira.create_issue_link(
            data={
                "type": {
                    "name": "Members",
                },
                "inwardIssue": {
                    "key": master_ticket,
                },
                "outwardIssue": {
                    "key": new_ticket,
                },
            }
        )
