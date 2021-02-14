"""
    argparse to run against one device or one circuit
    attach to ticket automatically

    Check:
        default checks on XR
        HPR checks (vrf)
"""


from checks import CircuitChecks
import yaml
import json
import argparse

from pprint import pprint

parser = argparse.ArgumentParser(description='Run snapshots for devices and circuits')
parser.add_argument('-u', '--username', metavar='username', help='MFA username')
parser.add_argument('-d', '--diffs', help='Run diffs, implies an output_pre.json file exists', action='store_true')
args = parser.parse_args()

def main():
    """Initialize checks type. Currently Per-Device or Per-Circuit."""

    with open('data.yaml') as file:
        data = yaml.full_load(file)

    if args.username:
        username = args.username
    else:
        with open ('/Users/jdickman/Git/refactored-couscous/usernames.yml') as file:
            username = yaml.full_load(file)['mfa']

    if data['check_type'] == 'circuit':

        output = {}
        for router in data['circuit_checks']:

            device_name, device_type = router.split('|')
            circuits_dict = data['circuit_checks'][router]
            circuits_output = CircuitChecks(username, device_name, device_type, circuits_dict).get_circuit_main()

            output[device_name.upper()] = circuits_output

    file = open('output.json', 'w')
    json.dump(output, file, indent=2)
    file.close()

if __name__ == '__main__':
    main()