from datetime import datetime
from pprint import pprint

import dns.resolver
import googleapiclient
import pygsheets
from openpyxl.utils.cell import get_column_letter


def open_gsheet(
    sheet_title: str, workbook_title: str, client_json: str
) -> pygsheets.worksheet.Worksheet:
    """Open Google Sheet via pygsheets and return Sheet object."""
    client = pygsheets.authorize(client_secret=client_json)
    return client.open(sheet_title).worksheet_by_title(workbook_title)


def return_column(gsheet, column: int) -> list:
    """Return column from gSheet as list."""
    return gsheet.get_col(column, include_tailing_empty=False)


def get_next_col(gsheet) -> int:
    """Return integer for next free column."""
    return len(gsheet.get_row(1, include_tailing_empty=False)) + 1


def get_a_records(url_list: list) -> list:
    """Using supplied URLs list, return list of A Records for each URL.

    URLs are stored in a gSheet in Col A. This is expected to be run at a regular
    interval, so the header for each A Record return list begins with today's date.

    The return is expected to be pushed to gSheets in one list, so if multiple A
    records exist for one URL, then all A records are joined to one comma-separated
    string.
    """
    resolver = dns.resolver.Resolver(configure=False)
    resolver.timeout = 1
    resolver.nameservers = [
        "8.8.8.8",  # google
        "1.1.1.1",  # cloudflare
        "205.171.3.66",  # lumen
        "199.85.127.30",  # ultradns
        "208.67.222.222",  # opendns
        "8.238.64.14",  # verizon
        "68.94.156.1",  # at&t
        "75.75.75.75",  # comcast
    ]

    # initialize list, giving the first value as today's date for the column header.
    a_records = [datetime.today().strftime("%Y-%m-%d")]  # 2022-05-11
    for url in url_list:
        # trim to just the main url and strip leading/trailing whitespace
        url = url.split("/")[0].strip()

        try:
            output = resolver.resolve(url, "A")

        except dns.exception.DNSException as err:
            print(f"\n{err}")
            url_string = "NO A RECORD"

        else:
            output_list = [i.to_text() for i in output]
            output_list.sort()
            url_string = ", ".join(output_list)

        a_records.append(url_string)
    return a_records


def format_subsequent_list(gsheet, a_records: list) -> list:
    """Update non-initial output lists for conditional formatting.

    A new list is created that contains, for each item in the list, either 'NO CHANGE'
    if the value has not changed since the first run, or the list of A Records if it has.
    """
    first_a_records = return_column(gsheet, 2)
    return [j if i != j else "NO CHANGE" for i, j in zip(first_a_records, a_records)]


def set_conditionals(gsheet, next_col: int, list_len: int) -> None:
    """For any cells (items in list) that do NOT equal 'NO CHANGE', make those cells
    color RED.

    Args:
        next_col (int): for translating numerical column IDs to A1, etc
        list_len (int): length of a_records list for size of conditional formatting
    """
    col_letter = get_column_letter(next_col)
    gsheet.add_conditional_formatting(
        f"{col_letter}2",
        f"{col_letter}{list_len}",
        "TEXT_NOT_CONTAINS",
        {"backgroundColor": {"red": 1}},
        ["NO CHANGE"],
    )


def upload_a_records(gsheet, a_records: list, next_col: int) -> None:
    """Upload A Records list to next empty column."""
    gsheet.update_col(next_col, a_records)


def main() -> None:
    gsheet = open_gsheet("Israel TV Judgement", "Sheet1", "desktop_oauth_gsheet.json")
    urls_list = return_column(gsheet, 1)
    next_col = get_next_col(gsheet)
    initial_run = False if next_col > 2 else True

    # urls_list contains header, strip before passing to function
    a_records = get_a_records(urls_list[1:])
    if not initial_run:
        a_records = format_subsequent_list(gsheet, a_records)

    if len(a_records) == len(urls_list):
        # check if another column needs to be added
        try:
            gsheet.get_col(next_col)

        except googleapiclient.errors.HttpError as err:
            print(f"\n{err}")
            gsheet.add_cols(1)

        finally:
            upload_a_records(gsheet, a_records, next_col)
            if not initial_run:
                set_conditionals(gsheet, next_col, len(a_records))

    else:
        print("\nA Records list not equal to URLs list.\n\nA Records list: \n")
        pprint(a_records)


if __name__ == "__main__":
    main()
