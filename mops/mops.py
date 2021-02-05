from jinja2 import Environment, FileSystemLoader
from atlassian import Confluence, Jira
from googleapiclient.discovery import build
import yaml
import keyring
import shutil
import sys
import argparse
import pickle

sys.path.append('/Users/jdickman/Git/refactored-couscous/projects/jira')
#pylint: disable=import-error
from atl_main import Logins
from cal_main import CalendarStuff


from pprint import pprint


class CreateMOPs:

    def __init__(self):
        """Create MOP/CD pages, link to Jira and create Calendar event (if applicable)."""

        with open('/Users/jdickman/Git/refactored-couscous/usernames.yml') as file:
            usernames = yaml.full_load(file)
        username = usernames['cas']

        self.jira = Logins(username).jira_login()
        self.confluence = Logins(username).conf_login()

    def main(self, args):
        """Open YAML, launch child methods

        Args:
            args (str): either 'mop' or 'cd'
        """

        with open("mop.yaml") as file2:
            self.mop_file = yaml.full_load(file2)

        if args.mop_type == 'mop':
            self.create_mop()

        elif args.mop_type == 'cd':
            self.create_cd()

    def test_vars(self):
        """Make sure variables are set in YAML."""

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
        self.update_confluence()
        self.update_jira()
        self.move_yaml()

    def create_cd(self):
        """Create CD from Jinja template, launch confluence, jira and calendar methods."""

        env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("cd-gen.j2")
        self.page_body = template.render(self.mop_file)

        self.test_vars()
        self.update_confluence()
        #pylint: disable=no-member
        self.create_calendar_event()
        self.update_jira()

    def update_confluence(self):
        """Create/Update Confluence page based on Title and parent page ID."""

        self.confluence.update_or_create(self.parent_page_id, self.page_title, self.page_body, representation='wiki')

    def update_jira(self):
        """Create Jira links to Confluence page if YAML 'link' entry is true."""

        if self.mop_file['link']:

            link_title = self.page_title.replace(" ", "+")
            page_url = f'https://documentation.cenic.org/display/Core/{link_title}'
            self.jira.create_or_update_issue_remote_links(self.ticket, page_url, self.page_title, relationship='mentioned in')

    def create_calendar_event(self):
        """Create Internal Change event for CD."""

        start_time = self.mop_file['cd']['start_time']
        end_time = self.mop_file['cd']['end_time']
        day = self.mop_file['cd']['start_day']
        title = self.mop_file['ticket'] + ': ' + self.mop_file['page_title']

        CalendarStuff().create_event(start_time, end_time, day, title)

    def move_yaml(self):
        """Copy YAML to repo"""

        shutil.copy('/Users/jdickman/Git/refactored-couscous/mop.yaml', f'/Users/jdickman/Git/1 - Docs/MOPs/YAML/{self.page_title}.yaml')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate MOP and push to Confluence/Jira')
    parser.add_argument('mop_type', metavar='mop_type', choices=['mop', 'cd'], help='Type of document to create')
    parser.add_argument('link', metavar='link', help='Link Confluence page to Jira')
    args = parser.parse_args()

    CreateMOPs().main(args)