''' General purpose netmiko script'''

from netmiko import ConnectHandler
import pyotp
import keyring
import time
import yaml
import os

script_dir = os.path.dirname(__file__)
with open(os.path.join(script_dir, 'usernames.yml')) as file:
    data = yaml.full_load(file)

user = data['mfa']
first_factor = keyring.get_password('mfa',user)
otp_secret = keyring.get_password('otp',user)
otp = pyotp.TOTP(otp_secret)

xr_bb_devices = [
    'sac-agg4',
    'tri-agg2',
    'sfo-agg4',
    'oak-agg8',
    'svl-agg8',
    'lax-agg8',
    'tus-agg8',
    'sdg-agg4',
    'riv-agg8',
    'slo-agg4',
    'fre-agg4',
    'frg-agg4'
]

junos_bb_devices = [
    'lax-agg10',
    'svl-agg10',
    'pdc-agg1',
    'cor-agg8',
    'sol-agg4',
    'bak-agg6'
]

# use '|junos' or '|iosxr' for device_type
device_list = [
    'pdc-agg1|junos',
    'cor-agg8|junos',
    'sol-agg4|junos',
    'bak-agg6|junos'
]

xr_show_commands = [
    # 'show bgp ipv6 unicast sum | utility egrep -B1 "Active|Connect"',
    'show run interface lo0'
]

junos_show_commands = [
    'show system firmware | match "i40e-NVM',
    'show bgp summary | match "137.164.16.6"'
]

def connect(device_type, device_name, user, passwd):
    connection = ConnectHandler(
        device_type = device_type,
        host = device_name,
        username = user,
        password = passwd
    )

    return connection

def main():

    for device in device_list:
        device_name, device_type = device.split('|')

        if device_type == 'junos':
            device_type = 'juniper_junos'
            commands_list = junos_show_commands

        elif device_type == 'iosxr':
            device_type = 'cisco_xr'
            commands_list = xr_show_commands

        start_time = time.time()
        connection = connect(device_type, device_name, user, first_factor + otp.now())

        print('\n', '=' * 20, device_name.upper(), '=' * 20, '\n')
        for command in commands_list:
            print(f"COMMAND: '{command}")
            print(connection.send_command(command), '\n\n')

        time.sleep(30 - (time.time() - start_time))


if __name__ == '__main__':
    main()