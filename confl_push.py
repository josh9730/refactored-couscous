from atlassian import Confluence, Jira
import sys
import keyring
import yaml

#pylint: disable=import-error
sys.path.append('./projects/atl_cal')
from atl_main import ConfluenceStuff

def conf_login(username):
    password = keyring.get_password('cas', username)
    confluence = Confluence(
        url = 'https://documentation.cenic.org/',
        username = username,
        password = password)
    return confluence

def main():

    with open('usernames.yml') as file:
        usernames = yaml.full_load(file)
    username = usernames['cas']

    confluence = conf_login(username)

    doc = open("doc.txt").read()
    parent_page_id = '8881304'
    page_title = 'MPLS/VPN Configs'

    confluence.update_or_create(parent_page_id, page_title, doc, representation='wiki')

if __name__ == '__main__':
    main()


