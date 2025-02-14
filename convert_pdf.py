from pathlib import Path
from typing import Final

import pandas as pd
import pygsheets
import tabula
import typer
from rich import print
from rich.prompt import Confirm

app = typer.Typer(help="Convert PDFs to Excel format and upload to Google Sheets.")

OUTPUT_FILE: Final[str] = "outputs.csv"
DEFAULT_PATH: Final[Path] = Path("~/Downloads/").expanduser()
CREDENTIALS_DIR: Final[Path] = Path("~/Google Drive/My Drive/Scripts").expanduser()
UPLOAD_WKSHEET: Final[str] = "pdf_upload"


def get_file(filename: str, folder: str) -> Path:
    path = Path(folder).joinpath(filename)
    if not path.exists():
        raise FileNotFoundError
    return path


def convert_file(file_path: Path) -> None:
    print("[red]Converting...")
    tabula.convert_into(file_path, OUTPUT_FILE, output_format="csv", pages="all")


def check_wsheet_empty(wsheet: pygsheets.Worksheet) -> None:
    print("[red]Validating...")
    a1_val = wsheet.get_value("A1")

    if a1_val:
        overwrite = Confirm.ask("Worksheet is not empty, overwrite?")
        if overwrite:
            wsheet.clear(fields="*")
        else:
            typer.Abort()


def upload_file(sheet_name: str, worksheet_name: str) -> None:
    print("[red]Authenticating...")
    client = pygsheets.authorize(client_secret=CREDENTIALS_DIR.joinpath("sheets_secret.json"), local=True)
    ssheet = client.open(sheet_name)

    try:
        wsheet = ssheet.worksheet("title", worksheet_name)
    except pygsheets.WorksheetNotFound:
        wsheet = ssheet.add_worksheet(worksheet_name)

    check_wsheet_empty(wsheet)

    print("[red]Uploading...")
    df = pd.read_csv(OUTPUT_FILE)
    df = df.fillna("")
    wsheet.set_dataframe(df, "A1")


def delete_output() -> None:
    print("[red]Deleting CSV...")
    Path(OUTPUT_FILE).unlink()


@app.command()
def convert_and_upload(
    sheet_name: str = typer.Argument(..., help="Google Sheet name"),
    filename: str = typer.Argument(..., help="File name with extension"),
    folder: str = typer.Argument(DEFAULT_PATH, help="Absolute directory path"),
    worksheet_name: str = typer.Argument(UPLOAD_WKSHEET, help='Worksheet Name'),
    delete_csv: bool = typer.Argument(True, help="Delete converted PDF output file after upload"),
):
    file_path = get_file(filename, folder)
    convert_file(file_path)
    upload_file(sheet_name, worksheet_name)
    if delete_csv:
        delete_output()

    print("[green]Completed.")


if __name__ == "__main__":
    app()

