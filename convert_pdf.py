from enum import Enum
from pathlib import Path
from typing import Final

import pandas as pd
import pygsheets
import tabula
import typer
from rich import print, prompt

app = typer.Typer(help="Convert PDFs to CSV and upload to Google Sheets.")

OUTPUT_FILE: Final[str] = "outputs.csv"
DEFAULT_PATH: Final[Path] = Path("~/Downloads/").expanduser()
CREDENTIALS_DIR: Final[Path] = Path("~/Google Drive/My Drive/Scripts").expanduser()
UPLOAD_WKSHEET: Final[str] = "pdf-upload"
EXCEL_NAME: Final[str] = "converted_pdf.xlsx"


class Formats(str, Enum):
    excel = "excel"
    gsheets = "gsheets"


def get_file(filename: str, folder: str) -> Path:
    path = Path(folder).joinpath(filename)
    if not path.exists():
        raise FileNotFoundError
    return path


def convert_file(file_path: Path) -> None:
    """Convert PDF to CSV. Converting directly to a DataFrame sometimes encounters exceptions, so CSV is safer."""
    print("[red]Converting...")
    tabula.convert_into(file_path, OUTPUT_FILE, output_format="csv", pages="all")
    tables = tabula.read_pdf(file_path, pages='all')
    print(tables)
    


def check_wsheet_empty(wsheet: pygsheets.Worksheet) -> None:
    print("[red]Validating...")
    if wsheet.get_value("A1"):
        overwrite = prompt.Confirm.ask("Worksheet is not empty, overwrite?")
        if overwrite:
            wsheet.clear(fields="*")
        else:
            typer.Abort()


def load_csv() -> pd.DataFrame:
    df = pd.read_csv(OUTPUT_FILE)
    return df.fillna("")


def upload_to_gsheets(sheet_name: str, worksheet_name: str) -> None:
    print("[red]Authenticating...")
    client = pygsheets.authorize(client_secret=CREDENTIALS_DIR.joinpath("sheets_secret.json"), local=True)
    ssheet = client.open(sheet_name)

    try:
        wsheet = ssheet.worksheet("title", worksheet_name)
        check_wsheet_empty(wsheet)
    except pygsheets.WorksheetNotFound:
        wsheet = ssheet.add_worksheet(worksheet_name)

    print("[red]Uploading...")
    df = load_csv()
    wsheet.set_dataframe(df, "A1")


def convert_to_excel() -> None:
    print("[red]Converting to Excel...")
    df = load_csv()
    df.to_excel(EXCEL_NAME, index=False)
    print(f"[green]Saved Excel file to: {Path(EXCEL_NAME).absolute()}")


def delete_output() -> None:
    print("[red]Deleting CSV...")
    Path(OUTPUT_FILE).unlink()


@app.command()
def convert_and_upload(
    output_type: Formats = typer.Argument(..., help="Output format"),
    filename: str = typer.Argument(..., help="File name with extension"),
    folder: str = typer.Argument(DEFAULT_PATH, help="Absolute directory path"),
    sheet_name: str = typer.Option(None, "-s", "--ssheet", help="Google Sheet name"),
    worksheet_name: str = typer.Option(UPLOAD_WKSHEET, "-ws", "--wsheet", help="Worksheet Name"),
    delete_csv: bool = typer.Option(True, "-d", "--delete", help="Delete converted PDF output file after upload"),
):
    file_path = get_file(filename, folder)
    convert_file(file_path)

    match output_type:
        case "gsheets":
            if not sheet_name:
                sheet_name = prompt.Prompt.ask("gSheet name not provided, input sheet name")
            upload_to_gsheets(sheet_name, worksheet_name)
        case "excel":
            convert_to_excel()

    if delete_csv:
        delete_output()

    print("[green]Completed.")


if __name__ == "__main__":
    app()
