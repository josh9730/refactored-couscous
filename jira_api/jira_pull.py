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

jql_request = 'issue = COR-968'
results = jira.jql(jql_request, limit=1)

file = open('ticket.json', 'w')
json.dump(results, file, indent=2)
file.close()