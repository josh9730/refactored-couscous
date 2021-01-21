from atlassian import Jira
import pandas as pd
import keyring
from gspread_pandas import Spread
from pprint import pprint

username = 'jdickman'
passw = keyring.get_password('cas', username) # encrypted CAS password

jira = Jira( # connection
    url = 'https://servicedesk.cenic.org',
    username = username,
    password = passw,
)

# jql search criteria
jql_request = 'labels = "RH" and status != Resolved and status != Deleted'

sheet_key = '1dPZE1BZ-i7fY2lRMdpXiUqN9s0euqT0qvN8_e1N36GI' # key of the spreadsheet
name = 'RH_bulk' # worksheet name
gsheet = Spread(sheet_key, name) # define worksheetsheet

results = jira.jql(jql_request, limit=100, fields=['assignee','reporter','key','summary','updated','status'])
df = pd.json_normalize(results['issues'])

FoI = ['fields.assignee.name','fields.reporter.name','key', 'fields.summary','fields.updated','fields.status.name']

gsheet.df_to_sheet(df[FoI], index=False, sheet=name, replace=True)



