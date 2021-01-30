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
    jql_request = 'labels = "CC|outage"'

    sheet_key = '1dPZE1BZ-i7fY2lRMdpXiUqN9s0euqT0qvN8_e1N36GI' # key of the spreadsheet
    name = 'outages' # worksheet name
    gsheet = Spread(sheet_key, name) # define worksheet

    results = jira.jql(jql_request, limit=100, fields=['key','summary'])
    df = pd.json_normalize(results['issues'])

    FoI = ['key', 'fields.summary']

    gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True)

if __name__ == '__main__':
    main()