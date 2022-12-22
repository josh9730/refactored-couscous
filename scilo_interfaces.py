import os
import time

import keyring
import pandas as pd
import pygsheets
import requests


def open_gsheet(sheet_title: str, workbook_title: str, client_json: str):
    """Open Google Sheet via pygsheets and return Sheet object."""
    client = pygsheets.authorize(client_secret=client_json)
    return client.open(sheet_title).worksheet_by_title(workbook_title)


def call_scilo():
    user = keyring.get_password("scilo_api", "user")
    passw = keyring.get_password("scilo_api", user)
    url = keyring.get_password("scilo_api", "url")

    parameters = {
        "hide_filterinfo": "1",
        "limit": "99999",
        "filter.state": "1",
        "filter.alias.not": "null",
        "link_disp_field": "alias",
    }

    port_tag = requests.get(
        f"{url}interface/",
        params=parameters,
        auth=requests.auth.HTTPBasicAuth(user, passw),
    ).json()

    time.sleep(10)

    parameters["link_disp_field"] = "device/name"
    device = requests.get(
        f"{url}interface/",
        params=parameters,
        auth=requests.auth.HTTPBasicAuth(user, passw),
    ).json()

    time.sleep(10)

    parameters["link_disp_field"] = "ifDescr"
    port = requests.get(
        f"{url}interface/",
        params=parameters,
        auth=requests.auth.HTTPBasicAuth(user, passw),
    ).json()

    return port_tag, device, port


def main():

    port_tag, device, port = call_scilo()

    # create DFs for each of the outputs
    df = pd.DataFrame.from_dict(port_tag)
    df.rename(columns={"description": "current_tag"}, inplace=True)
    df1 = pd.DataFrame.from_dict(device)
    df1.rename(columns={"description": "device"}, inplace=True)
    df2 = pd.DataFrame.from_dict(port)
    df2.rename(columns={"description": "port"}, inplace=True)

    # filter and drop certain tags
    df = df[df["current_tag"].str.contains("(dc:)")]
    df = df[df["current_tag"].str.contains("(core)|(edge)|(infra)")]
    df = df[~df["current_tag"].str.contains("(l2agg)|(bb-)")]

    # merge, on URI on port_tag DF
    df = pd.merge(df, df1)
    df = pd.merge(df, df2)

    # update URI, device columns to remove unnecessary data
    df["URI"] = df["URI"].apply(lambda x: x.split("/")[-1])
    df.dropna(subset=["device"], inplace=True)
    df["device"] = df["device"].apply(lambda x: x.split(".cenic")[0])
    df["new_tag"] = ""
    df["new_tag + current_tag"] = ""

    df = df[
        [
            "URI",
            "device",
            "port",
            "current_tag",
            "new_tag",
            "new_tag + current_tag",
        ]
    ]

    # output to gSheets as DF
    creds_dir = os.getenv("HOME") + "/Google Drive/My Drive/Scripts"
    tags_sheet = open_gsheet(
        "NOC Port Tag Updates", "Sheet1", f"{creds_dir}/desktop_oauth_gsheet.json"
    )
    tags_sheet.clear()
    tags_sheet.set_dataframe(df, start=(1, 1), copy_head=True, extend=True, nan="")


if __name__ == "__main__":
    main()
