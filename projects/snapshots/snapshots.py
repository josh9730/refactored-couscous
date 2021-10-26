""" Version 3.0

Performs pre-maintenance checks, specifically on agg routers.
If diffs selected, the pre-maintenance file will be diffed and deviations shown.
"""

from lib.checks import CircuitChecks, DeviceChecks
from lib.login import Login
import yaml
import json
import argparse
import time
import jsondiff
import os
from pprint import pprint

parser = argparse.ArgumentParser(description="Run snapshots for devices and circuits")
parser.add_argument("-u", "--username", metavar="username", help="MFA username")
parser.add_argument(
    "-j",
    "--jira",
    help="Upload output files to ticket, requires CAS account in Keyring",
    action="store_true",
)
parser.add_argument(
    "-d",
    "--diffs",
    help="Run diffs, implies an output_pre.json file exists",
    action="store_true",
)
args = parser.parse_args()


def start_checks(username, input_dict, check_type):

    output = {}
    print(
        "\n", "-" * 10, "BEGIN {type} CHECKS".format(type=check_type.upper()), "-" * 10
    )

    for index, router in enumerate(input_dict, 1):

        device_name, device_type = router.split("|")
        start_time = time.time()

        print(f"\n({index}/{len(input_dict)})")
        print(f"{device_name.upper()}: {{")

        if check_type == "circuit":
            checks_output, start_time = CircuitChecks(
                username, device_name, device_type, input_dict[router]
            ).get_circuit_main()

        elif check_type == "device":
            checks_output, start_time = DeviceChecks(
                username, device_name, device_type
            ).get_device_main()

        print("}")
        elapsed_time = time.time() - start_time
        if int(elapsed_time) < 30 and index != len(input_dict):
            print(f"\n--- Resetting OTP ({int(40 - elapsed_time)} sec) ---")
            time.sleep(40 - elapsed_time)

        output[device_name.upper()] = checks_output

    print(
        "\n",
        "-" * 10,
        "END {type} CHECKS".format(type=check_type.upper()),
        "-" * 10,
        "\n",
    )

    return output


def jira_upload(username, ticket, file):

    jira = Login(username.rstrip("mfa"), "", "").jira_login()
    print(f"Uploading {file} to {ticket}")
    jira.add_attachment(ticket, file)


def main():
    """Initialize checks type. Per-Device or Per-Circuit."""

    with open("data.yaml") as file:
        data = yaml.full_load(file)

    pre = data["pre_file_path"]
    post = data["post_file_path"]

    if args.username:
        username = args.username
    else:
        with open("/Users/jdickman/Google Drive/My Drive/Scripts/usernames.yml") as file:
            username = yaml.full_load(file)["mfa"]

    check_type = data["check_type"]
    input_dict = data[check_type]

    final_output = start_checks(username, input_dict, check_type)

    if args.diffs:
        file = open("output_post.json", "w")
        json.dump(final_output, file, indent=2)
        file.close()

        print(f"\nSnapshots completed. Check {post} for output!\n")

        with open(pre, "r") as pre_file:
            pre = json.load(pre_file)
        with open(post, "r") as post_file:
            post = json.load(post_file)

        diff_dict = {}
        diffs = jsondiff.diff(pre, post, syntax="symmetric")
        diff_dict.update(diffs)

        pprint(diff_dict)

        file = open("diffs.json", "w")
        json.dump(diff_dict, file, indent=2)
        file.close()

        if args.jira:
            jira_upload(username, data["ticket"], "output_post.json")
            jira_upload(username, data["ticket"], "diffs.json")

        print("\nCheck diffs.json for diffs (if any). Diffs also printed below:\n\n")
        print("-" * 10, "DIFFS", "-" * 10, "\n")

        pprint(diff_dict)

        print("\n", "-" * 10, "END DIFFS", "-" * 10, "\n")

    else:
        file = open("output_pre.json", "w")
        json.dump(final_output, file, indent=2)
        file.close()

        if args.jira:
            jira_upload(username, data["ticket"], "output_pre.json")

        print(f"\nSnapshots completed. Check {pre} for output!\n")


if __name__ == "__main__":
    main()
