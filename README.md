## Main Directory

Contains the following:

1. `connect.py`: Login via different methods (telnet, ssh, enable account, CAS). Requires `lp.py` to fetch non-MFA accounts and keyring. See `connect.py -h`.
2. `lp.py`: lastpass api, use positional arg to select what account to retrieve. See `lp.py -h`.
3. `v4tov6.py`: Converts an IPv4 address to an IPv6 address. See `v4tov6.py -h`.
4. `jira_scheduled.py`: Program used for scheduler to run certain functions from `atl_main.py` and `cal_main.py` weekly/daily. Can run functions individually (see `jira_scheduled.py`)

## MOP Directory

Contains various MOP and Change document scripts:

1. `mop.py`: Main program, uses jinja2 and Atlassian APIs to push to Confluence, Jira. Can also create a GCal event.
2. `cd-gen.j2` and `mop-gen.j2`: Jinja2 to generate CDs and MOPs.
3. `mop.yaml`: Create CDs and MOPs here, used by `mop.py`

## Projects Directory

### atl_cal

1. `atl_main.py`: Atlassian main, contains logins plus various methods to retrieve/push info to Confluence/Jira
2. `cal_main.py`: GCal main, contains login plus methods to create/get events

### snapshots

See directory readme for more details. Program to get pre- and post-maintenance outputs from IOS-XR and Junos devices.