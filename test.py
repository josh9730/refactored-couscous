import datetime
from pprint import pprint

import pygsheets

import login


def open_gsheet(
    sheet_title: str, workbook_title: str, client_json: str
) -> pygsheets.worksheet.Worksheet:
    """Open Google Sheet via pygsheets and return Sheet object.

    Args:
        sheet_title: [str] This is the literal gSheet title
    """
    client = pygsheets.authorize(client_secret=client_json)
    return client.open(sheet_title).worksheet_by_title(workbook_title)


def main():

    sheet = open_gsheet("Israel TV Judgement", "Sheet1", "desktop_oauth_gsheet.json")

    sheet.id
    a = sheet.get_col(1, include_tailing_empty=False)
    pprint(a)
    print("adsasdasdasd")


if __name__ == "__main__":
    main()
