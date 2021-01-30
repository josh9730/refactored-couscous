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

    engineer = [
        'jdickman',
        'nlo',
        'eho',
        'tsanda',
        'myunus',
        'sbellamine'
    ]

    sheet_key = '1dPZE1BZ-i7fY2lRMdpXiUqN9s0euqT0qvN8_e1N36GI' # key of the spreadsheet
    name = 'Bulk' # worksheet name
    gsheet = Spread(sheet_key, name) # define worksheet

    j = 65 # counter for cell
    for i in engineer:

        jql_request = f'assignee={i} and status not in (Resolved, Deleted, Done)' # jql search criteria
        results = jira.jql(jql_request, limit=500, fields=['assignee','key','summary','customfield_10209','updated']) # pull from Jira using the jql above, customfield_10209 = 'milestones'
        df = pd.json_normalize(results['issues']) # format with pandas
        k = chr(j) # convert integer to ascii (uppercase letter)

        if i != 'sbellamine':
            FoI = ['fields.assignee.name','key', 'fields.summary','fields.customfield_10209.value','fields.updated'] # 'Fields of Interest'
            if j == 65:
                gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True, start=f'{k}1') # clear and push to sheet
            else:
                gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=False, start=f'{k}1') # push to sheet

        else: # sana has no milestones
            FoI = ['fields.assignee.name','key', 'fields.summary', 'fields.updated'] # 'Fields of Interest'
            gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=False, start=f'{k}1') # push to sheet

        j += 5 # increment for cell

if __name__ == '__main__':
    main()