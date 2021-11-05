from atlassian import Jira
from utils import jira_login

tickets = [
    "NOC-647144|eho",
    "NOC-647138|tsanda",
    "NOC-647139|tsanda",
    "NOC-647146|tsanda",
    "NOC-654444|eho",
    "NOC-647463|eho",
    "NOC-649007|tsanda",
    "NOC-661261|tsanda",
    "NOC-647150|tsanda",
    "NOC-647145|myunus",
    "NOC-647135|myunus",
]

description = "Please complete pre-deployment activities as described [HERE|https://documentation.cenic.org/display/Core/Core+Tail+Circuit+Deployment+Process#CoreTailCircuitDeploymentProcess-predeployment]"


def main():
    jira = jira_login()

    for i in tickets:
        ticket = i.split("|")[0]
        assignee = i.split("|")[1]
        ticket_name = jira.issue_field_value(ticket, "summary")
        child_name = ticket_name.split("Deployment")[0] + "PreDeployment"

        # Update milestone to M2
        fields = {"customfield_10209": {"id": "10024"}}
        jira.issue_update(ticket, fields)

        # create predeployment ticket
        fields = {
            "summary": child_name,
            "description": description,
            "project": {"key": "NOC"},
            "issuetype": {"name": "CENIC Request"},
            "assignee": {"name": assignee},
            "customfield_10002": [8],
        }
        jira.issue_create(fields=fields)

        # get predeployment ticket key and create parent/child links
        jql_request = (
            'project = "CENIC Service Desk"  and creator = jdickman and created >=  -1m'
        )
        child_key = jira.jql(jql_request, limit=1, fields=["key"])["issues"][0]["key"]
        links = {
            "type": {"name": "Members", "inward": "child of", "outward": "parent of"},
            "inwardIssue": {"key": ticket},
            "outwardIssue": {"key": child_key},
        }
        jira.create_issue_link(data=links)


if __name__ == "__main__":
    main()

