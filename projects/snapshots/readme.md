# What is Snapshots

The Snapshots program is designed to automate pre- and post-maintenance checks for Junos & IOS-XR devices. NO Python knowledge is required, and only a YAML file is needed for definitions.

Optionally, diffs (pre- vs post-) and automatically pushing the .json outputs to a specified ticket are supported. See help for details.

Currently, two 'modes' are supported, as follows:
1. Device Checks
    1. Uses PyEZ (Junos) or ncclient/napalm (IOSXR)
    2. Grabs the following from the device:
      - Software version
      - Power (Junos only)
      - IS-IS Neighbors
      - PIM Neigbors
      - MSDP Neighbors
      - Interface stats
      - BGP Neighbors & Accepted Prefixes
    3. Outputs as a JSON file, for readability and diffs
2. Circuit Checks
    1. Supports iBGP, eBGP, and Static connections
    2. Uses PyEZ (Junos) or ncclient/napalm (IOSXR)
    3. Gets the following (eBGP, iBGP):
      1. BGP:
        - Recieved Routes & Path Attributes *after* ingress policies:
          - Next-Hop
          - Local Preference
          - AS Path
          - MED
          - Community list
        - Advertised, Accepted Counts
        - Checks if Default Advertised
      2. Interface stats
        - Including optics PMs (Junos only)
      3. IS-IS Adjacency
    4. If static, only the Recieved Routes & Path Attributes are checked.

### Example Outputs

#### Device Checks
```json
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
#### Circuit Checks
```json
{
  "LAX-AGG10": {
    "oxnr-pub-lib-1": {
      "Service": "ibgp",
      "Interface": {
        "et-6/1/0.211": {
          "Description": "[dc:infra][dc:lib] 1G to oxnr-pub-lib-1 Gi0/0/0 CLR7961",
          "Output Rate": "314040 bps",
          "Input Rate": "66544 bps",
          "Stats": "Logical Interface",
          "Optics": "Logical Interface"
        }
      },
      "IS-IS": {
        "et-6/1/0.211": {
          "State": "Up",
          "IPv4 Metric": "9999",
          "IPv6 Metric": "9999"
        }
      },
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
- Requires kerying for MFA and CAS (only needed if you want to push to Jira). See documentation for setup.

## Run program

- Use `python3 snapshots.py {{ MFA USERNAME }}`. See help also with `python3 snapshots.py -h`.
- Optionally, a YAML file containing the MFA Username may be provided so you do not have to enter the username each run:
  - Create a file named `usernames.yml` with the mfa username like so:
    - `mfa: {{ MFA USERNAME }}`
  - The `snapshots.py` file will need to be edited to have the full path to the file. Search for a line containing `usernames.yml`, and edit this directory string to match the directory of your local file.
  - If applicable, be sure to add the `.yml` file to your `.gitignore`.
- Diffs and Jira push can also be selected through the switches (`-d` and `-j` respectively)

## Usage

### YAML

The 'data.yaml' file contains the instructions for the snapshots program. This contains the variables that you want to run the Checks on. Example below:

Note that as this is YAML, the indentation is important!

```yaml
---
ticket: NOC-600000
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
      port: et-6/1/0.211
    lb-csu-2:
      service: ibgp
      port: et-6/5/0
      ipv4_neighbor: 137.164.0.4
      ipv6_neighbor: 2607:f380::118:9a40:41
  lax-agg8|iosxr:
    CLR-6304:
      service: static
      ipv4_routes:
        - 209.129.86.0/23
```

1. `ticket`: Full ticket number of the maintenance ticket, for pushing outputs to Jira as an attachment.
2. `pre_file_path`: The name of pre-maintenance file (either the name of the file to write pre- output to, or the name for diffs to reference).
3. `post_file_path`: Name of the post- file (both the pre_ and post_ file locations default to the same directory as the program).
4. `check_type`: `device` for Device Checks, or `circuit` for Circuit Checks.
5. `device`: List of devices to run Device Checks on. Format is `device_name|device_type` where device type is either `junos` or `iosxr`.
6. `circuit`: See below for more details. This details what circuits to run Circuit Checks on. Intention is to ONLY need info available from the circuit record.

By default, the output file will be `output_pre.json`, which will be used (and overwritten) if diffs are NOT selected. If diffs are requested, the default output file is `output_post.json` and the diffs will be written to `diffs.json`.

#### Circuit Checks structure:
```yaml
circuit:
  lax-agg10|junos:
    lb-csu-2:
      service: ibgp
      port: et-6/5/0
      ipv4_neighbor: 137.164.0.4
      ipv6_neighbor: 2607:f380::118:9a40:41
```

| YAML | Description |
| --- | --- |
| `circuit` | Starts the block for Circuit Checks |
| `lax-agg10\|junos` | Device name & type concactenation |
| `lb-csu-2` | - For iBGP, the **hostname** is required (for DNS lookup to get iBGP peering IP). For eBGP/Static, any name is fine (ie CLR Name) |
| `service` | iBGP/eBGP/static |
| `port` | Port facing the customer, physical or subinterface - required for iBGP/eBGP |
| `ipv4_neighbor`, `ipv6_neighbor` | **NOT** required. This is in case the IP assignments do not follow the standards |
| `ipv4_routes`, `ipv6_routes` | In list form, required for static |

### Running the program

IOS-XR at 6.3.3 has some issues with the supported YANG models, notably HPR and optics are not checkable for Circuit BGP Checks and MSDP and a few others are not checkable for Device. You may see NAPALM connections when these are needed (causing additional OTP resets).

The program will print out an output to the terminal window showing the status:

```
 ---------- BEGIN CIRCUIT CHECKS ----------

(1/2)
RIV-AGG8: {
        CLR-7620: {
                1) Neighbor IPs
                2) BGP Routes
                3) Interface
                4) IS-IS
        }
}

--- Resetting OTP (27 sec) ---

(2/2)
LAX-AGG10: {
        OXNR-PUB-LIB-1: {
                1) Neighbor IPs
                2) BGP Routes
                3) Interface
                4) IS-IS
        }
        BUMT-LIB-1: {
                1) Neighbor IPs
                        * WARNING: No AAAA record for bumt-lib-1.
                        Enter manually if v6 Peering exists and re-run.
                2) BGP Routes
                3) Interface
                4) IS-IS
        }
        CLR7608: {
                1) Neighbor IPs
                2) BGP Routes
                3) Interface
                4) IS-IS
        }
}

 ---------- END CIRCUIT CHECKS ----------
```

Once the program completes, if `do_diff` is **True**, a 'diffs' section will be printed at the end.

### Diffs

Diffs can be requested by the `-d` option, ie `python3 snapshots.py -d`. This assumes a pre-maintenance file exists, and is specified in the `data.yaml` file. Diffs will be output to `diffs.json` as well as printed to the terminal.

If any values have changed, the json file will show the path, and a `list` of the changes. The first value is the original, and the second is the new value (in the post-maintenance file).

Note that the diffs will output a change if something trivial such as traffic rate changes and will not give you any direction as to 'why', so it is up to you to determine if the diffs are relevant or not.

```json
{
  "LAX-AGG10": {
    "oxnr-pub-lib-1": {
      "Interface": {
        "et-6/1/0.211": {
          "Output Rate": [
            "108632 bps",
            "125960 bps"
          ],
          "Input Rate": [
            "339336 bps",
            "276784 bps"
          ]
        }
      }
    },
    "bumt-lib-1": {
      "Interface": {
        "et-6/1/0.309": {
          "Output Rate": [
            "4888 bps",
            "71160 bps"
          ],
          "Input Rate": [
            "4776 bps",
            "15464 bps"
          ]
        }
      }
    }
  }
}
```

### Jira

If desired, the program can push the outputs to a Jira ticket (specified in `data.yaml`) by using the `-j` switch, ie `python3 snapshots.py -j`. The output files will be pushed as an attachment.
