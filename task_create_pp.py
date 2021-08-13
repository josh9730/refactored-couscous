'''
Input ticket number of Story to be assigned.
Creates the 6 ticket buckets and links them to the Story. Includes the description for Design.
Adds 'CoreMgd' label and Epic Link to Design Task.
'''

from atlassian import Jira
import yaml
import sys
import os
import argparse

#pylint: disable=import-error
script_dir = os.path.dirname(__file__)
sys.path.append(os.path.join(script_dir, 'projects/atl_cal'))
from atl_main import Logins

parser = argparse.ArgumentParser(description='Create tickets for Story per Planning Process')
parser.add_argument('story_ticket', metavar='story_ticket',
                    help='Story ticket number, e.g. COR-1234')
parser.add_argument('epic_ticket', metavar='epic_ticket',
                    help='Epic ticket number, e.g. COR-1234')
args = parser.parse_args()

with open(os.path.join(script_dir, 'usernames.yml')) as file:
    data = yaml.full_load(file)

design_desc = '''
* *Hardware/Software* (necessary components that are on-hand/available and/or must be procured)
** On-hand/Available
** Must Be Procured
** Identify hardware power requirements
** Optical

* *Facilities* (site-specific facility components that need to be considered)
** Rack space
** Cross connects
** Patch panels
** Rack power
** PDU
** Power cables

* *Design* (initial plan for design)
** Circuit Installation / Migration Table
** Layer 1 Design:
** Layer 2 Design:
** Layer 3 Design:
** Commodity or Associate Peering changes:
'''

tasks = {
    'Design': design_desc,
    'Solutions': 'Ticket for Solutions Page requirements. May not be needed.',
    'Supporting Activities': 'Bucket for tickets that require NOC, PMO and/or external participant involvement and NOT Changes',
    'Preparation': 'Bucket for all non-service impacting changes.',
    'Changes': 'Bucket for all service impacting changes.',
    'Shipping': 'Bucket for all shipping activities.'
}

def main():

    jira = Logins(data['cas']).jira_login()

    story_name = jira.issue_field_value(args.story_ticket, 'summary')

    # create tasks
    for i, j in tasks.items():
        fields = {
            'summary': story_name + ' - {task_name}'.format(task_name=i),
            'description': j,
            'project': { 'key': 'COR' },
            'issuetype': { 'name': 'Task' }
        }
        jira.issue_create(fields=fields)

    # find tickets recently created, expect 6
    jql_request = 'project = "CENIC Core Projects"  and creator = jdickman and created >=  -1m order by created ASC'
    issues = jira.jql(jql_request, limit=6, fields=['key'])

    # for each new ticket, link to Story
    for i in range(6):
        links = {
            'type': {'name': 'DependsOn' },
            'inwardIssue': { 'key': args.story_ticket},
            'outwardIssue': {'key': issues['issues'][i]['key']},
        }
        jira.create_issue_link(data=links)
        if i == 0:
            jira.issue_update(issues['issues'][i]['key'], {
                'labels': [ 'CoreMgd' ],
                'customfield_10401': args.epic_ticket
            })


if __name__ == '__main__':
    main()