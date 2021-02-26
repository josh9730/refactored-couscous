# What is Snapshots

The Snapshots program is designed to automate pre- and post-maintenance checks for Junos & IOS-XR devices. NO Python knowledge is required, and only a YAML file is needed for definitions.

Currently, two 'modes' are supported, as follows:

- Device Checks: Retrieves data for a device-specific maintenance
  - Output example (abbreviated)
```
{
  "LAX-AGG10": {
    "Software": "19.3R2.9",
    "Power": {
      "PEM 0": {
        "Status": "Online",
        "Input Status": "OK",
        "Capacity": "2500"
      },
    "IS-IS": {
      "lax-agg8": {
        "Port": "ae11.2302",
        "State": "Up"
      },
    "PIM Enabled Ports": {
      "et-6/1/0.201": {
        "Neighbor": "137.164.7.207"
      },
    "Established MSDP Neighbors": {
      "137.164.16.2": {
        "Local Address": "137.164.16.6",
        "State": "Established",
        "Group": "infra"
      },
    "Interfaces": {
      "et-6/0/0": {
        "Description": "100G to lax-agg8 Hu0/0/0/20",
        "Errors": {
          "Rx Errors": "0",
          "Rx Drops": "0",
          "Tx Errors": "0",
          "Tx Drops": "0"
        },
        "Optics PMs": {
          "Lane 0": {
            "Rx Power": "0.91dBm",
            "Tx Power": "-4.54dBm"
          },
          "Lane 1": {
            "Rx Power": "1.58dBm",
            "Tx Power": "-1.83dBm"
          },
          "Lane 2": {
            "Rx Power": "1.73dBm",
            "Tx Power": "-2.02dBm"
          },
          "Lane 3": {
            "Rx Power": "1.81dBm",
            "Tx Power": "-2.98dBm"
          }
        }
      },
```
- Circuit Checks: Retrieves data for a circuit-specific maintenance
  - Output example (abbreviated)
```
  },
  "LAX-AGG10": {
    "oxnr-pub-lib-1": {
      "Service": "ibgp",
      "IPv4 BGP Data": {
        "IPv4 Neighbor": "137.164.2.156",
        "IPv4 Adv. Count": "Full DC IPv4 Table",
        "IPv4 Adv. Default?": "No",
        "IPv4 Rx. Count": "2",
        "IPv4 Rx. Prefixes": {
          "205.154.245.0/28": {
            "Next-Hop": "137.164.7.73",
            "Local Preference": "100",
            "AS-Path": "64919",
            "MED": "0",
            "Community": [
              "2152:65439",
              "2152:65506",
              "2152:65535"
            ]
          },
```

# How to use the Snapshots program

**NOTE**: Because this uses MFA, transitions between devices will require an OTP reset (30 seconds).

## Setup

- Clone repository
- Requires python 3.6+
- `pip install -r requirements.txt`
- Requires MFA login with keyring. See documentation for setup.

## Run program

- Use `python3 snapshots.py {{ MFA USERNAME }}`. See help also with `python3 snapshots.py -h`.
- Optionally, a YAML file containing the MFA Username may be provided so you do not have to enter the username each run.
  - Create a file named `usernames.yml` with the mfa username like so:
    - `mfa: {{ MFA USERNAME }}`
  - The `snapshots.py` file will need to be edited to have the full path to the file. Search for a line containing `usernames.yml`, and edit this directory string to match the directory of your local file.

## Usage

### YAML

The 'data.yaml' file contains the instructions for the snapshots program. This contains the variables that you want to run the Checks on. Example below:
```yaml
---
do_diff: false
pre_file_path: 'output_pre.json'
post_file_path: 'output_post.json'
check_type: circuit
device:
  - lax-agg10|junos
circuit:
  riv-agg8|iosxr:
    CLR-7620:
      service: ebgp
      port: TenGigE0/0/0/8/3.340
    CLR-7621:
      service: ebgp
      port: HundredGigE0/0/0/2.341
  lax-agg10|junos:
    oxnr-pub-lib-1:
      service: ibgp
    lb-csu-2:
      service: ibgp
      ipv4_neighbor: 137.164.0.4
      ipv6_neighbor: 2607:f380::118:9a40:41
```
Note that as this is YAML, the indentation is important!

1. `do_diff`: true/false depending on if you want a diff at the end (ie pre- vs post-maintenance)
2. `pre_file_path`: The name of pre-maintenance file (either the name of the file to write pre- output to, or the name for diffs to reference)
3. `post_file_path`: Name of the post- file (both the pre_ and post_ file locations default to the same directory as the program)
4. `check_type`: 'device' for Device Checks, or 'circuit' for Circuit Checks
5. `device`: List of devices to run Device Checks on. Format is 'device_name|device_type' where device type is either 'junos' or 'iosxr'
6. `circuit`: See below for more details. This details what circuits to run Circuit Checks on. Intention is to ONLY need info available from the circuit record.

#### Circuit Checks structure:
- The first line is the agg router. This needs to be in the same format as in Device Checks: `device_name|device_type` where device type is either `junos` or `iosxr`.
- Line 2 is the `name`. The name ONLY used for iBGP and must be the hostname. For eBGP, the circuit name is fine (not actually used).
- The third line is the `service`. This can be either `ibgp` or `ebgp` and primarily determines how the program finds the Neighbor IPs.
- Next is the `port` lines. The port is required, and should be written in the same format as the port appears in `show run`, ie `TenGigE` and not `Te`, etc.
  - The program 'guesses' the neighbor IPs from either the port (eBGP) or the hostname (iBGP).
  - eBGP guesser assumes that the neighbor addresses are +1 from the port address (IPv4) or +16 (for IPv6).
- The `ipv4_neighbor` & `ipv6_neighbor` lines are used in case the neighbor IPs do not follow the standard above.

### Running the program

IOS-XR at 6.3.3 has some issues with the supported YANG models for RPCs, notably HPR and optics are not checkable for Circuit BGP Checks and MSDP and a few others are not checkable for Device. You may see NAPALM connections when these are needed (causing additional OTP resets).
The program will print out an output to the terminal window showing the status:

```
 ---------- BEGIN CIRCUIT CHECKS ----------

(1/2)
RIV-AGG8: {
        CLR-7620: {
                1) Getting Neighbor IPs
                2) Getting BGP Routes
        }
}

--- Resetting OTP (28 sec) ---

(2/2)
LAX-AGG10: {
        OXNR-PUB-LIB-1: {
                1) Getting Neighbor IPs
                2) Getting BGP Routes
        }
        CYP-CC-3: {
                1) Getting Neighbor IPs
                2) Getting BGP Routes
        }
        CLR-7073: {
                1) Getting Neighbor IPs
                2) Getting BGP Routes
        }
}

 ---------- END CIRCUIT CHECKS ----------
```

Once the program completes, if `do_diff` is **True**, a 'diffs' section will be printed at the end.