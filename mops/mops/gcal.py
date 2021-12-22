from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime, date
import pickle
import os.path
import shutil


class Calendar:
    def __init__(self, utils, username=None):
        # If modifying these scopes, delete the file token.pickle.
        SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

        try:
            file_name = utils.path.split("/")[-1]
            path = utils.path.split(file_name)[0] + "/"
        except:
            path = ""

        if utils.ic_url == None:
            raise KeyError("The gCal Internal Calendar URL must be specified")
        self.ic_url = utils.ic_url

        creds = None
        if os.path.exists(f"{path}token.pickle"):
            with open(
                f"{path}token.pickle",
                "rb",
            ) as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    f"{path}credentials.json",
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)

            with open(
                f"{path}token.pickle",
                "wb",
            ) as token:
                pickle.dump(creds, token)

        self.service = build("calendar", "v3", credentials=creds)

    def create_event(self, start_time, end_time, day, title):
        """Creates Internal Calendar Event
        Args:
            start_time (str): start time (military)
            end_time (str): end time (military)
            day (str): day (can be 'today')
            title (str): title for the event
        """

        if day == "today":
            start_day = date.today()
        else:
            start_day = date.fromisoformat(str(day))

        start_hour = int(start_time[0:2])
        start_min = int(start_time[2:4])
        end_hour = int(end_time[0:2])
        end_min = int(end_time[2:4])

        start_iso = datetime(
            start_day.year, start_day.month, start_day.day, start_hour, start_min
        ).isoformat()
        end_iso = datetime(
            start_day.year, start_day.month, start_day.day, end_hour, end_min
        ).isoformat()

        # Create calendar dict to create event
        body = {
            "summary": title,
            "start": {"timeZone": "America/Los_Angeles", "dateTime": start_iso},
            "end": {"timeZone": "America/Los_Angeles", "dateTime": end_iso},
        }

        self.service.events().insert(
            calendarId=self.ic_url,
            body=body,
        ).execute()
