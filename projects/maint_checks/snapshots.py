"""
    argparse to run against one device or one circuit
    attach to ticket automatically

    junos/xr share routes parser

    Check:
        


    transition status:
        ibgp junos/xr: done
        ebgp junos: done
        ebgp xr: done
        static xr
        static junos
        hpr support junos: done
        hpr support xr:
"""


from checks import CircuitChecks
import yaml
import json
import argparse
import time

from pprint import pprint

parser = argparse.ArgumentParser(description='Run snapshots for devices and circuits')
parser.add_argument('-u', '--username', metavar='username', help='MFA username')
parser.add_argument('-d', '--diffs', help='Run diffs, implies an output_pre.json file exists', action='store_true')
args = parser.parse_args()

def main():
    """Initialize checks type. Per-Device or Per-Circuit."""

    with open('data.yaml') as file:
        data = yaml.full_load(file)

    if args.username:
        username = args.username
    else:
        with open ('/Users/jdickman/Git/refactored-couscous/usernames.yml') as file:
            username = yaml.full_load(file)['mfa']

    if data['check_type'] == 'circuit':

        output = {}
        for index, router in enumerate(data['circuit_checks'], 1):

            device_name, device_type = router.split('|')

            start_time = time.time()
            circuits_output = CircuitChecks(username, device_name, device_type, data['circuit_checks'][router]).get_circuit_main()
            elapsed_time = time.time() - start_time

            if int(elapsed_time) < 30 and index != len(data['circuit_checks']):
                print(f'\t... resetting OTP ({int(30 - elapsed_time)} sec)')
                time.sleep(30 - elapsed_time)
                print('\t... done\n\n')

            output[device_name.upper()] = circuits_output

    file = open('output.json', 'w')
    json.dump(output, file, indent=2)
    file.close()

if __name__ == '__main__':
    main()