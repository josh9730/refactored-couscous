import yaml
import keyring
import pyotp
import sys

from atlassian import Confluence, Jira

"""
keyring setup:
keyring set mfa [ mfa user ]  [ first factor ]
keyring set otp [ mfa user ] [ the secret from the URI ]
"""


def get_user_vars(*args):
    outfile = open("/Users/jdickman/Google Drive/My Drive/Scripts/usernames.yml", "r")
    data = yaml.safe_load(outfile)
    if args:
        output = []
        for i in args:
            output.append(data[i])
    else:
        output = data
    return output


def get_keyring(account, username):
    return keyring.get_password(account, username)


def get_mfa_keyring(user_keyring, mfa_keyring):
    mfa_user = get_user_vars(user_keyring)[0]

    first = get_keyring(user_keyring, mfa_user)
    otp_secret = get_keyring(mfa_keyring, mfa_user)

    otp = pyotp.TOTP(otp_secret)
    return mfa_user, first, otp


def conf_login():
    confluence_url, username = get_user_vars("confluence_url", "cas")

    password = keyring.get_password("cas", username)
    confluence = Confluence(url=confluence_url, username=username, password=password)
    return confluence

def jira_login():
    jira_url, username = get_user_vars("jira_url", "cas")

    password = keyring.get_password("cas", username)
    jira = Jira(url=jira_url, username=username, password=password)
    return jira