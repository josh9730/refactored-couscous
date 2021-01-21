""" Gets username & password from LastPass.

Args:
    optical
    enable
    oob
    cas
    tacacs
"""

import pyotp
from lastpass import Vault
import keyring
from sys import argv
import re

def get_lp(lp_account):
# name is stored as 'bytes' in lastpass. Uses argv input and converts to bytes

    lp_user = 'jdickman@cenic.org' # lastpass username
    lp_pass = keyring.get_password('lp_pass','jdickman') # first factor password
    otp_secret = keyring.get_password('lp',lp_user) # grab base32 secret for lastpass
    otp_gen = pyotp.TOTP(otp_secret) # input base32 into pyotp
    otp = otp_gen.now() # use pyotp to generate the 6-digit OTP

    if lp_account == 'optical':
        name = bytes('Optical', 'utf-8')
    elif lp_account == 'enable':
        name = bytes('CENIC Enable Account', 'utf-8')
    elif lp_account == 'oob':
        name = bytes('CENIC Out-of-Band- OOB', 'utf-8')
    elif lp_account == 'cas':
        name = bytes('CAS', 'utf-8')
    elif lp_account == 'tacacs':
        name = bytes('CENIC TACACS Key', 'utf-8')

    vault = Vault.open_remote(lp_user, lp_pass, otp) # connect to lastpass

    for i in vault.accounts:
        if i.name == name: # if name matches the bytes name generated above
            # OOB is stored as a custom entry, needs regex
            if i.name != bytes('CENIC Out-of-Band- OOB', 'utf-8'):
                lp_logon_user = str(i.username, 'utf-8')
                lp_logon_pass = str(i.password, 'utf-8')
                lp_logon_passthrough = ''
            elif i.name == bytes('CENIC Out-of-Band- OOB', 'utf-8'):
                user_re = re.compile(r'Super User:\S+')
                pass_re = re.compile(r'Password:\S+')
                passthrough_re = re.compile(r'Passthrough:\S+')

                lp_logon_user = user_re.search(str(i.notes, 'utf-8')).group().lstrip('Super User:')
                lp_logon_pass = pass_re.search(str(i.notes, 'utf-8')).group().lstrip('Password:')
                lp_logon_passthrough = passthrough_re.search(str(i.notes, 'utf-8')).group().lstrip('Passthrough:')

    return lp_logon_user, lp_logon_pass, lp_logon_passthrough

if __name__ == '__main__':
    script, lp_account = argv
    output = get_lp(lp_account)
    print('\n\tUsername:\t', output[0])
    print('\tPassword:\t', output[1])
    if output[2] != '':
        print('\tPassthrough:\t', output[2])
    print('\n')