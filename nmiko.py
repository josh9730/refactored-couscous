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

xr_devices = [
    # 'sac-agg4',
    # 'tri-agg2',
    # 'sfo-agg4',
    # 'oak-agg8',
    # 'svl-agg8',
    # 'lax-agg8',
    # 'tus-agg8',
    # 'sdg-agg4',
    # 'riv-agg8',
    # 'slo-agg4',
    # 'fre-agg4',
    'frg-agg4'
]

junos_devices = [
    'lax-agg10',
    'svl-agg10',
    'pdc-agg1',
    'cor-agg8',
    'sol-agg4',
    'bak-agg6'
]

xr_show_commands = [
    # 'show bgp ipv6 unicast sum | utility egrep -B1 "Active|Connect"',
    'show run interface lo0'
]

junos_show_commands = [
    'show bgp summary | match "Active|Connect"'
]


def connect(type, host, user, passwd):
    connection = ConnectHandler(
    device_type = type,
    host = host,
    username = user,
    password = passwd)
    return connection

def run_commands(device, connection, commands):
    device_result = [f"\n\n\n{'='*20} {device} {'='*20}"] #header
    command_result = connection.send_command(commands)
    device_result.append(f"\n{'='*3} {commands} {'='*3}\n") # mini-header for the command input
    device_result.append(command_result)

    return device_result

def main():

    for i in xr_devices:
        connection = connect('cisco_xr', i, user, first_factor + otp.now())
        print(f'\t\t{i}')
        for j in xr_show_commands:
            a = connection.send_command(j)

            print(f'''
            =======================================
            |                                     |
            |                                     |
            |          {a}                        |
            |                                     |
            |                                     |
            =======================================
            '''
            )

        connection.disconnect()

if __name__ == '__main__':
    main()