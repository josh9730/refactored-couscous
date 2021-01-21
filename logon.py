# logon to device and return prompt
#
# Args:
#   device you want to login to

import pexpect
import pyotp
import keyring
from sys import argv

def ssh_login(username, password, host):
    # connect to device given to argv & interact
    child = pexpect.spawn (f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no {username}@{host} | ct"')
    child.expect ('Password:')
    child.sendline (password)
    child.interact()

if __name__ == '__main__':
    script, host = argv
    mfa_user = 'jdickmanmfa' # mfa username
    first_factor = keyring.get_password("mfa",mfa_user) # get mfa first factor
    otp_secret = keyring.get_password("otp",mfa_user) # get mfa base32
    otp = pyotp.TOTP(otp_secret) # pass base32 to pyotp
    mfa_password = first_factor + otp.now() # generate OTP
    ssh_login(mfa_user, mfa_password, host)


# keyring setup:
# keyring set mfa [ mfa user ]  [ first factor ]
# keyring set otp [ mfa user ] [ the secret from the URI ]

# python3 get-pip.py
# pip3 install pexpect
# pip3 install pyotp
# pip3 install keyring