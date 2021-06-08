from napalm.base import get_network_driver
import json
from pprint import pprint
import keyring
import pyotp


ips = [
    # '137.164.16.4',
    # '137.164.16.21',
    # '137.164.16.7',
    # '137.164.16.12',
    '137.164.16.16',
    # '137.164.16.30',
    # '137.164.16.104',
    # '137.164.16.35',
    # '137.164.16.31',
    # '137.164.16.20',
    # '137.164.16.85',
    # '137.164.16.32',
    # '137.164.16.34',
    # '137.164.16.27',
    # '137.164.16.28',
    '137.164.16.29',
    '137.164.16.37',
    '137.164.16.6'
]



def napalm_connect(hostname, username, password, device_type):
    driver = get_network_driver(device_type)
    connection = driver(
        hostname = hostname,
        username = username,
        password = password)

    return connection

first_factor = keyring.get_password("mfa",'jdickmanmfa')
otp_secret = keyring.get_password("otp",'jdickmanmfa')
otp = pyotp.TOTP(otp_secret)

output = {}

for i in ips:

    # username='jdickmanmfa'
    # password=first_factor + otp.now()
    username = 'M4u7oN7CcKMb'
    password = 'bj66F7wod*F4=W*-'

    if i in ('137.164.16.6', '137.164.16.16', '137.164.16.32', '137.164.16.34', '137.164.16.37', '137.164.16.85'):
        device_type = 'junos'
    else:
        device_type = 'iosxr'
    print(device_type)
    print(i)
    dev = napalm_connect(i, username, password, device_type)
    dev.open()

    print(dev.is_alive())

    # for j in ips:
    #     output.update(dev.traceroute(j))

    dev.close()
    pprint(output)

file = open('traceroute.json', 'w')
json.dump(output, file, indent=2)
file.close()