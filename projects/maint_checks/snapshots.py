"""
    argparse to run against one device or one circuit
    attach to ticket automatically
    multiple HPR in same XR agg for circuits?

    --- XR HPR REQUIRES PORT

    Check:

    transition status:

        diffs

        Circuit:

            static xr
            static junos
            list of routes in yaml
"""


from checks import CircuitChecks, DeviceChecks
import yaml
import json
import argparse
import time
from pprint import pprint

parser = argparse.ArgumentParser(description='Run snapshots for devices and circuits')
parser.add_argument('-u', '--username', metavar='username', help='MFA username')
parser.add_argument('-d', '--diffs', help='Run diffs, implies an output_pre.json file exists', action='store_true')
args = parser.parse_args()

def start_checks(username, input_dict, check_type):

    output = {}
    print('\n','-' * 10 ,'BEGIN {type} CHECKS'.format(type=check_type.upper()), '-' * 10)

    for index, router in enumerate(input_dict, 1):

        device_name, device_type = router.split('|')
        start_time = time.time()

        print(f'\n({index}/{len(input_dict)})')
        print(f'{device_name.upper()}: {{')

        if check_type == 'circuit':
            checks_output, start_time = CircuitChecks(username, device_name, device_type, input_dict[router]).get_circuit_main()

        elif check_type == 'device':
            checks_output, start_time = DeviceChecks(username, device_name, device_type).get_device_main()

        print('}')
        elapsed_time = time.time() - start_time
        if int(elapsed_time) < 30 and index != len(input_dict):
            print(f'\n--- Resetting OTP ({int(30 - elapsed_time)} sec) ---')
            time.sleep(30 - elapsed_time)

        output[device_name.upper()] = checks_output

    print('\n','-' * 10 ,'END {type} CHECKS'.format(type=check_type.upper()), '-' * 10, '\n')

    return output

def main():
    """Initialize checks type. Per-Device or Per-Circuit."""

    with open('data.yaml') as file:
        data = yaml.full_load(file)

    if args.username:
        username = args.username
    else:
        with open ('/Users/jdickman/Git/refactored-couscous/usernames.yml') as file:
            username = yaml.full_load(file)['mfa']

    check_type = data['check_type']
    input_dict = data[check_type]

    final_output = start_checks(username, input_dict, check_type)

    file = open('output.json', 'w')
    json.dump(final_output, file, indent=2)
    file.close()

if __name__ == '__main__':
    main()