from jinja2 import Environment, FileSystemLoader
from atlassian import Confluence, Jira
import yaml
import keyring
import shutil
import sys

sys.path.append('/Users/jdickman/Git/refactored-couscous/projects/jira')
from atl_main import Logins

def main():
    env = Environment(loader=FileSystemLoader('.'), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("mop-gen.j2")

    with open('/Users/jdickman/Git/refactored-couscous/usernames.yml') as file:
        usernames = yaml.full_load(file)
    username = usernames['cas']

    with open("mop.yaml") as file2:
        mop_file = yaml.full_load(file2)

    if not mop_file['page_title']:
        print('\n\tEnter Title\n')
        sys.exit(1)
    else:
        page_title = mop_file['page_title']

    if not mop_file['parent_page_id']:
        print('\n\tEnter Parent Page ID\n')
        sys.exit(1)
    else:
        parent_page_id = mop_file['parent_page_id']

    if not mop_file['ticket']:
        print('\n\tEnter Ticket\n')
        sys.exit(1)
    else:
        ticket = mop_file['ticket']

    page_body = template.render(mop_file)
    confluence = Logins(username).conf_login()
    confluence.update_or_create(parent_page_id, page_title, page_body, representation='wiki')

    if mop_file['link'] == True:
        jira = Logins(username).jira_login()

        jira = Logins(username).jira_login()

        link_title = page_title.replace(" ", "+")
        page_url = f'https://documentation.cenic.org/display/Core/{link_title}'
        jira.create_or_update_issue_remote_links(ticket, page_url, page_title, relationship='mentioned in')

    shutil.copy('/Users/jdickman/Git/refactored-couscous/mop.yaml', f'/Users/jdickman/Git/1 - Docs/MOPs/YAML/{page_title}.yaml')

if __name__ == '__main__':
    main()