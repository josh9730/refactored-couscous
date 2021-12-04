''' General purpose netmiko script'''

import time

from netmiko import ConnectHandler

from tools.utils import get_mfa_keyring


# use '|junos' or '|iosxr' for device_type
xr_bb_devices = [
    'tri-agg2|iosxr',
    # 'sdg-agg4|iosxr',
    # 'sac-agg4|iosxr',
    # 'sfo-agg4|iosxr',
    # 'slo-agg4|iosxr',
    # 'fre-agg4|iosxr',
    # 'frg-agg4|iosxr',
    # 'riv-agg8|iosxr',
    # 'oak-agg8|iosxr',
    # 'svl-agg8|iosxr',
    # 'lax-agg8|iosxr',
    # 'tus-agg8|iosxr'
]

junos_bb_devices = [
    'lax-agg10|junos',
    'svl-agg10|junos',
    'pdc-agg1|junos',
    'cor-agg8|junos',
    'sol-agg4|junos',
    'bak-agg6|junos'
]

misc_devices = [

]

device_list = xr_bb_devices

xr_show_commands = [
    'show int desc | ex "[\.]" | in Hu',
    'show inventory | util egrep -B1 "CPAK|CFP"'
]

junos_show_commands = [
    'show system firmware | match "i40e-NVM',
    'show bgp summary | match "137.164.16.6"'
]

def connect(device_type, device_name, username, passwd):
    connection = ConnectHandler(
        device_type = device_type,
        host = device_name,
        username = username,
        password = passwd,
        fast_cli = False
    )
    return connection

def main():

    for counter, device in enumerate(device_list, 1):
        device_name, device_type = device.split('|')

        if device_type == 'junos':
            device_type = 'juniper_junos'
            commands_list = junos_show_commands

        elif device_type == 'iosxr':
            device_type = 'cisco_xr'
            commands_list = xr_show_commands

        start_time = time.time()
        username, first_factor, otp = get_mfa_keyring('mfa', 'otp')
        connection = connect(device_type, device_name, username, first_factor + otp.now())

        print('\n', '-' * 20, device_name.upper(), '-' * 20, '\n')
        for command in commands_list:
            print(f"COMMAND: '{command}")
            print(connection.send_command(command), '\n\n')

        if counter != len(device):
            if start_time < (abs(time.time() - start_time)):
                time.sleep(30 - (time.time() - start_time))
            else:
                continue


if __name__ == '__main__':
    main()