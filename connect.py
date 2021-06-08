import pexpect
import pyotp
import keyring
import argparse
import time
import yaml
import os
from lp import GetLP


class LoginInteract:

    def __init__(self, args=None):

        script_dir = os.path.dirname(__file__)
        with open(os.path.join(script_dir, 'usernames.yml')) as file:
            usernames = yaml.full_load(file)
        self.username = usernames['mfa']

        self.first_factor = keyring.get_password("mfa", self.username)
        otp_secret = keyring.get_password("otp", self.username)
        self.otp = pyotp.TOTP(otp_secret)
        self.hostname = args.hostname

        if args.enable:
            print(f'\nConnecting to {self.hostname} with SSH/Enable...\n')
            self.enable_login()

        elif args.telnet:
            print(f'\nConnecting to {self.hostname} with Telnet/MFA...\n')
            self.telnet_login()

        elif args.telnet_enable:
            print(f'\nConnecting to {self.hostname} with Telnet/Enable...\n')
            self.telnet_enable()

        elif args.cas:
            print(f'\nConnecting to {self.hostname} with SSH/CAS...\n')
            self.cas_login()

        else:
            print(f'\nConnecting to {self.hostname} with SSH/MFA...\n')
            self.ssh_login()

    def ssh_login(self):
        """SSH with MFA account.
        """

        child = pexpect.spawn(f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no {self.username}@{self.hostname} | ct"')
        child.expect('Password:')
        child.sendline(self.first_factor + self.otp.now())
        child.interact()

    def telnet_login(self):
        """Telnet with MFA account
        """

        child = pexpect.spawn(f'/bin/bash -c "telnet -4 {self.hostname} | ct"')
        child.expect('Username:')
        child.sendline(self.username)
        child.expect('Password:')
        child.sendline(self.first_factor + self.otp.now())
        child.interact()

    def telnet_enable(self):
        """Telnet with MFA account
        """

        enable_account = GetLP().get_lp('enable')

        child = pexpect.spawn(f'/bin/bash -c "telnet -4 {self.hostname} | ct"')
        child.expect('Username:')
        child.sendline(enable_account[0])
        child.expect('Password:')
        child.sendline(enable_account[1])
        child.interact()

    def enable_login(self):
        """Retrieve enable account from lastpass script and SSH with enable account.
        """

        enable_account = GetLP().get_lp('enable')

        child = pexpect.spawn(f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no {enable_account[0]}@{self.hostname} | ct"')
        child.expect('Password:')
        child.sendline(enable_account[1])
        child.interact()

    def cas_login(self):
        """Retrieve CAS account from lastpass script and ssh
        """

        cas_account = GetLP().get_lp('cas')

        child = pexpect.spawn(f'/bin/bash -c "ssh {self.username[:-3]}@{self.hostname} | ct"')
        child.expect('assword:')
        child.sendline(cas_account[1])
        child.interact()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Login to device and return control.')
    parser.add_argument('hostname', metavar='hostname', help='Device name or IP address to login to. Defaults to MFA via ssh.')
    parser.add_argument("-t", "--telnet", help="Telnet with MFA account", action="store_true")
    parser.add_argument("-te", "--telnet_enable", help="Telnet with enable account", action="store_true")
    parser.add_argument("-e", "--enable", help="SSH with enable account", action="store_true")
    parser.add_argument("-c", "--cas", help="SSH with CAS account", action="store_true")
    args = parser.parse_args()

    LoginInteract(args)



# keyring setup:
# keyring set mfa [ mfa user ]  [ first factor ]
# keyring set otp [ mfa user ] [ the secret from the URI ]