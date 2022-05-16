from datetime import datetime
from pprint import pprint

import dns.resolver
import pygsheets


def open_gsheet(
    sheet_title: str, workbook_title: str, client_json: str
) -> pygsheets.worksheet.Worksheet:
    """Open Google Sheet via pygsheets and return Sheet object."""
    client = pygsheets.authorize(client_secret=client_json)
    return client.open(sheet_title).worksheet_by_title(workbook_title)


def return_urls_list(urls_sheet: pygsheets.worksheet.Worksheet, column: int) -> list:
    """Return list of urls from gSheet."""
    return urls_sheet.get_col(column, include_tailing_empty=False)


def get_next_col(urls_sheet: pygsheets.worksheet.Worksheet) -> int:
    """Return integer for next free column."""
    return len(urls_sheet.get_row(1, include_tailing_empty=False)) + 1


def get_a_records(url_list: list) -> list:
    """Using supplied URLs list, return list of A Records for each URL.

    URLs are stored in a gSheet in Col A. This is expected to be run at a regular
    interval, so the header for each A Record return list begins with today's date.

    The return is expected to be pushed to gSheets in one list, so if multiple A
    records exist for one URL, then all A records are joined to one comma-separated
    string.
    """
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [
        "8.8.8.8",  # google
        "1.1.1.1",  # cloudflare
        "205.171.3.66",  # lumen
        "199.85.127.30",  # ultradns
        "208.67.222.222",  # opendns
    ]

    # initialize list, giving the first value as today's date for the column header.
    # a_records = [datetime.today().strftime("%Y-%m-%d")]  # 2022-05-11
    a_records = ['2022-05-12 INITIAL']
    for url in url_list:
        # trim to just the main url and strip leading/trailing whitespace
        url = url.split("/")[0].strip()

        try:
            output = resolver.resolve(url, "A")
            output_list = [i.to_text() for i in output]
            output_list.sort()
            url_string = ", ".join([i for i in output_list])

        except dns.exception.DNSException as err:
            print(err)
            url_string = "NO A RECORD"

        a_records.append(url_string)
    return a_records


def upload_a_records(
    urls_sheet: pygsheets.worksheet.Worksheet, a_records: list, next_col: int
) -> None:
    """Upload A Records list to next empty column."""
    urls_sheet.update_col(next_col, a_records)


def main() -> None:
    urls_sheet = open_gsheet(
        "Israel TV Judgement", "Sheet1", "desktop_oauth_gsheet.json"
    )
    urls_list = return_urls_list(urls_sheet, 1)
    next_col = get_next_col(urls_sheet)

    # check if initial run
    # return previous week's A Records list if not initial
    if next_col > 2:
        previous_a_records = return_urls_list(urls_sheet, next_col - 1)

    # urls_list contains header, strip before passing to function
    a_records = get_a_records(urls_list[1:])

    # only upload to gSheets if lengths match, otherwise only print A Records
    if len(a_records) == len(urls_list):
        upload_a_records(urls_sheet, a_records, next_col)
    else:
        print("\nA Records list not equal to URLs list.\n\nA Records list: \n")
        pprint(a_records)


if __name__ == "__main__":
    main()
