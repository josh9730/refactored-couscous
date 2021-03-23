from jinja2 import Environment, FileSystemLoader
from atlassian import Confluence, Jira
from googleapiclient.discovery import build
import yaml
import keyring
import shutil
import sys
import argparse
import pickle

#pylint: disable=import-error
sys.path.append('../projects/atl_cal')
from atl_main import JiraStuff, ConfluenceStuff
from cal_main import CalendarStuff


class CreateMOPs:

    def __init__(self, args):
        """Create MOP/CD pages, link to Jira and create Calendar event (if applicable)."""

        with open("mop.yaml") as file:
            self.mop_file = yaml.full_load(file)

        if args.username:
            username = args.username
        else:
            with open(self.mop_file['username_file_path']) as file2:
                usernames = yaml.full_load(file2)
            username = usernames['cas']

        self.args = args
        self.jira = JiraStuff(username)
        self.confluence = ConfluenceStuff(username)

    def test_vars(self):
        """Make sure variables are set in YAML"""

        if not self.mop_file['page_title']:
            print('\n\tEnter Title\n')
            sys.exit(1)
        else:
            self.page_title = self.mop_file['page_title']

        if not self.mop_file['parent_page_id']:
            print('\n\tEnter Parent Page ID\n')
            sys.exit(1)
        else:
            self.parent_page_id = self.mop_file['parent_page_id']

        if not self.mop_file['ticket']:
            print('\n\tEnter Ticket\n')
            sys.exit(1)
        else:
            self.ticket = self.mop_file['ticket']

    def create_mop(self):
        """Create MOP from Jinja template, launch confluence & jira methods."""

        env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("mop-gen.j2")
        self.page_body = template.render(self.mop_file)

        self.test_vars()
        print(f'\n\tCreating MOP:\n\n\t\tTitle: {self.page_title}\n\t\tTicket: {self.ticket}\n\t\tJira Link: {self.args.link}\n')

        self.update_confluence()
        self.update_jira()
        self.move_yaml()

    def create_cd(self):
        """Create CD from Jinja template, launch confluence, jira and calendar methods."""

        env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("cd-gen.j2")
        self.page_body = template.render(self.mop_file)

        self.test_vars()
        print(f'\n\tCreating Change Doc:\n\n\t\tTitle: {self.page_title}\n\t\tTicket: {self.ticket}\n\t\tJira Link: {self.mop_file["link"]}\n')

        self.update_confluence()
        #pylint: disable=no-member
        self.create_calendar_event()
        self.update_jira()
        self.move_yaml()

    def update_confluence(self):
        """Create/Update Confluence page based on Title and parent page ID."""

        print(f'\tPushing to Confluence page: {self.page_title}\n')
        f = open("test.txt", "w")
        f.write(self.page_body)
        f.close()
        self.confluence.page_update_wiki_format(self.parent_page_id, self.page_title, self.page_body)

    def update_jira(self):
        """Create Jira links to Confluence page if YAML 'link' entry is true."""

        if self.args.link:

            print(f'\tAdding link to {self.ticket}')
            self.jira.update_jira_link(self.ticket, self.page_title)

    def create_calendar_event(self):
        """Create Internal Change event for CD."""

        if self.mop_file['cd']['calendar']:

            start_time = str(self.mop_file['cd']['start_time'])
            end_time = str(self.mop_file['cd']['end_time'])
            day = self.mop_file['cd']['start_day']
            title = self.mop_file['ticket'] + ': ' + self.mop_file['page_title']

            print(f'\tCreating Internal Change entry:\n\n\t\tDay: {day}\n\t\tStart: {start_time}\n\t\tEnd: {end_time}\n')
            CalendarStuff().create_event(start_time, end_time, day, title)

    def move_yaml(self):
        """Copy YAML to repo"""

        print(f'\tMoving YAML to storage: {self.mop_file["mop_repo"]}')
        shutil.copy(self.mop_file['mop_directory'], self.mop_file['mop_repo'] +  self.page_title + '.yaml')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate MOP and push to Confluence/Jira')
    parser.add_argument('mop_type', metavar='mop_type', choices=['mop', 'cd'], help='Type of document to create. Allowed values are \'mop\' and \'cd\'')
    parser.add_argument('-u', '--username', metavar='username', help='CAS username')
    parser.add_argument("-l", "--link", help="Create Jira Link", action="store_true")
    args = parser.parse_args()

    mops = CreateMOPs(args)

    if args.mop_type == 'mop':
        mops.create_mop()

    elif args.mop_type == 'cd':
        mops.create_cd()