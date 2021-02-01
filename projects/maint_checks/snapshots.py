""" Version = 2.0
To Do:

    CircuitChecks:
        v6 routes only - does list work?
        check XR static
        per-port checks for CircuitChecks

    DeviceChecks:
        advertised prefix count per neighbor
        check if works on mx204, 9001
        IOSXR needs re-formatting to match junos
            optics, power support

    better diffs
    all outputs should be in same format (support pre on device A and post on Device B)


what does it do ?
"""

import yaml
import json
import jsondiff
import time
from pprint import pprint
from checks import CircuitChecks, DeviceChecks
import argparse


parser = argparse.ArgumentParser(description='Run snapshots for devices and circuits')
parser.add_argument('username', metavar='accousernameunt',
                help=f'MFA username')
args = parser.parse_args()

def main(args):
    """Initialize checks type. Currently Per-Device or Per-Circuit.
    """

    with open('data.yaml') as file:
        data = yaml.full_load(file)

    username = args.username
    pre = data['pre_file_path']
    post = data['post_file_path']

    if data['check_type'] == 'circuit':
        print('\n','-' * 10 ,'BEGIN CIRCUIT CHECKS', '-' * 10, '\n')

        global_agg = data['global_agg']
        global_type = 'junos'

        output = CircuitChecks(username, global_agg, global_type, data['circuit_checks']).get_bgp_output_dict()

        print('-' * 10 ,'END CIRCUIT CHECKS', '-' * 10, '\n')

    elif data['check_type'] == 'device':
        print('\n','-' * 10 ,'BEGIN DEVICE CHECKS', '-' * 10, '\n')

        output = DeviceChecks(username, data['device_checks']).get_device_main()

        print('\n','-' * 10 ,'END DEVICE CHECKS', '-' * 10, '\n')

    if data['do_diff']:
        file = open(post, 'w')
        json.dump(output, file, indent=2)
        file.close()

        with open(pre, 'r') as pre_file:
            pre = json.load(pre_file)
        with open(post, 'r') as post_file:
            post = json.load(post_file)

        diffs = jsondiff.diff(pre, post)
        print('\n\nProgram completed. Diffs below (if any):\n\n')
        print('-' * 10, 'DIFFS', '-' * 10, '\n')
        pprint(diffs)
        print('\n', '-' * 10, 'END DIFFS', '-' * 10,)

    else:
        file = open(pre, 'w')
        json.dump(output, file, indent=2)
        file.close()

        print(f'\nProgram completed. Check {pre} for output!\n')


if __name__ == '__main__':
    main(args)