from atlassian import Jira, ServiceDesk
import json
import keyring

username = 'jdickman'
passw = keyring.get_password('cas', username) # encrypted CAS password

jira = Jira( # connection
    url = 'https://servicedesk.cenic.org',
    username = username,
    password = passw,
)

# Update issue
# jira.issue_update(issue_key, fields)

ticket_list = [
    853,
865,
876,
1014,
1051,
1052,
1053,
1067,
1082,
1078,
1079,
1080,
1083,
1085,
1119,
1120,
1121,
1122,
1123
]

for ticket in ticket_list:
    ticket = 'COR-'+str(ticket)
    jira.issue_update(ticket, { 'labels' : [ 'CoreMgd' ] })
    # jira.issue_update(ticket, { 'status' : { 'statusCategory' : { 'name' : 'In Progress' }}})


# {'customfield_10411': new_end}

