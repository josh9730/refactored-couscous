""" Version =
To Do:
    CircuitChecks:
        determine if HPR
            if Adv.Count > 800k and DC, = 'Full Table', etc
        v6 routes only - does list work?
        check XR static
        static returns 'recorded' for AS Path - send ASN to method?
        per-port checks for CircuitChecks
        diffs/output as another method of CircuitChecks? Formulate data from outputs too?
        IPChecks parent of GetRoutes parent of GetNRLI

    DeviceChecks:
        time between runs for multiple devices?
        second file for multiple runs
        show arp table
        advertised prefix count per neighbor
        check if works on mx204, 9001
        IOSXR needs re-formatting to match junos
        optics, power support

    all outputs should be in same format (support pre on device A and post on Device B)


what does it do ?
"""

from pprint import pprint
import yaml
import json
import jsondiff
import time
from login import Login
from checks import CircuitChecks, DeviceChecks


def main():
    with open('data.yaml') as file: # pull from yaml file
        data = yaml.full_load(file)

    """Initialize checks type. Currently Per-Device or Per-Circuit.
    """

    with open('data.yaml') as file: # pull from yaml file
        data = yaml.full_load(file)

    username = data['username']

    try:
        if data['circuit_checks']:
            global_agg = data['global_agg']
            global_type = data['global_type']
            pre = global_agg + 'pre.json'
            post = global_agg + 'post.json'
            output = CircuitChecks(username, global_agg, global_type, data['circuit_checks']).get_bgp_output_dict()

    except:
        for index, device in enumerate(data['device_checks'], 1):
            start_time = time.time()
            for hostname, device_type in device.items():
                # output_name = f'output_dict_'
                output = DeviceChecks(username, hostname, device_type).get_device_main()

            elapsed_time = time.time() - start_time
            if int(elapsed_time) < 30 and index != len(data['device_checks']):
                print(f'\t... resetting OTP {int(30 - elapsed_time)}')
                time.sleep(30 - elapsed_time)
                print('\t... done')

    # output_dict = CircuitChecks(username, global_agg, global_type, data['circuit_checks']).get_bgp_output_dict()
    # output_dict = DeviceChecks(username, global_agg, global_type).get_device_junos()

    if data['do_diff']:
        file = open(post, 'w') # open json file for writing output
        json.dump(output, file, indent=2)
        file.close()

        with open(pre, 'r') as pre_file:
            pre = json.load(pre_file)
        with open(post, 'r') as post_file:
            post = json.load(post_file)

        diffs = jsondiff.diff(pre, post)
        print('\n\nProgram completed. Diffs below (if any):\n\n')
        print('---------- DIFFS ----------\n')
        pprint(diffs)
        print('\n---------- END DIFFS ----------\n')

    else:
        file = open(pre, 'w') # open json file for writing output
        json.dump(output_dict, file, indent=2)
        file.close()

        print(f'\nProgram completed. Check {pre} for output!\n')


if __name__ == '__main__':
    main()