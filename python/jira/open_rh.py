from atlassian import Jira
import pandas as pd
import keyring
from gspread_pandas import Spread

username = 'jdickman'
password = keyring.get_password('cas', username)

def main():

    jira = Jira( # connection
        url = 'https://servicedesk.cenic.org',
        username = username,
        password = password)

    # jql search criteria
    jql_request = 'labels = "RH" and status != Resolved and status != Deleted'

    sheet_key = '1dPZE1BZ-i7fY2lRMdpXiUqN9s0euqT0qvN8_e1N36GI'
    name = 'RH_bulk'
    gsheet = Spread(sheet_key, name) # define worksheetsheet

    results = jira.jql(jql_request, limit=100, fields=['assignee','reporter','key','summary','updated','status'])
    df = pd.json_normalize(results['issues'])
    FoI = ['fields.assignee.name','fields.reporter.name','key', 'fields.summary','fields.updated','fields.status.name']
    gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True)

if __name__ == '__main__':
    main()