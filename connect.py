""" Connects via ssh using backdoor account

Args:
    hostname to login to
"""

from sys import argv
from lp import get_lp
from logon import ssh_login

lp_pull = get_lp('enable')
lp_username = lp_pull[0]
lp_password = lp_pull[1]

script, host = argv
ssh_login(lp_username, lp_password, host)