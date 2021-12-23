# Description

Program to create, format, and push MOPs and Change Docs to Confluence, Jira, and gCal. The MOP/CD itself is written in the `mop.yaml` or `cd.yaml` file and formatted with Jinja. Managed by Poetry, YAML validation with Cerberus.

Only the `mop.yaml` or `cd.yaml` are editted during MOP/CD creation. No python or other languages are needed. See [HERE](https://www.w3schools.io/file/yaml-introduction/) for YAML tutorials.

### Program Functions
1. Render MOP or CD through a Jinja2 template to Markdown format
2. Push Markdown-formatted MOP/CD to Confluence
3. If requested, link Jira ticket & Confluence page together
4. Move completed YAML to a repo for long term reference
5. If requested, return completed YAML to defaults (keeping user variables)

# How to Install

1. Verify python3.7+ is installed: `python3 --version`
2. On GitHub, click `Code`, and download as zip. Extract to your home directory (or whatever directory you want to work from).
    - You can also clone the repo if you're using Git.
3. From terminal, `cd refactored-couscous-mops/mops/dist/`
3. `ls | grep whl` - copy the filename for the wheel package
4. `pip3 install {{ filename from above }}`

This will install all necessary files and dependencies to your computer.

# How to Use

## User Variables

No passwords, usernames, or urls are stored inside either the script or the YAML files. Some prep work must be done before starting a MOP

### Keyring

The CAS password (for Jira and Confluence) is expected to be stored in keyring, and your CAS username will be supplied to retrieve. To add your CAS password to keyring:

1. Keyring is installed by installing the program in the How to Install section
3. Keyring is accessed via terminal directly:
  - Enter in a terminal window: `keyring set cas {{ CAS USERNAME }}`
  - At the prompt, enter: `{{ CAS PASSWORD }}`

### YAML Variables

Both the `cd.yaml` and `mop.yaml` have variables in the upper sections that should be filled out:
```yaml
mop_repo:

# absolute path to file, ignored if values set below
login_path: 
# locally defined, overrides 'path'
login_vars:
  confluence_url:
  jira_url:
  cas:
```
1. `mop_repo`: This is the directory path that you want the program to move completed MOPs/CDs to once they've been pushed to Confluence. This is for long term reference.
2. `login_path`: This is the directory path for the user variables you see below `path`. This is in case you want these in a separate file than the MOP yaml files (i.e. multiple programs need the usernames).
3. `login_vars`: If the `login_path` variable is not set, you must set the URLs and CAS usernames here.

That's it! No more setup is needed.

### Args

Arguments can be supplied when calling the progrma. See `python3 mops.py -h` for help.

- `-l`: Add Jira Link. Note that this should only be done once, if an edit is pushed do not specify a link as this will create multiple links (can be removed in Jira).
- `-c`: Push to gCal. Note that this does require setting up the Google Drive API (not covered in this guide).
- `-p`: Print the rendered MOP (in Markdown) to screen without pushing to Confluence/Jira.
- `-d`: Create MOP/CD as normal, and **reset** the appropriate yaml file for the next mop. Keeps the YAML Variables mentioned above.
- `-r`: Reset MOP only, keeping YAML Variables.

## Creating MOPs

The `mop.yaml` file is where all editing occurs. This will be formatted in specific ways, then rendered and pushed to Confluence. List of sections:

1. `ticket`: Jira ticket number for the MOP
2. `page_title`: The Confluence page for the new MOP (or an existing page name if you want to overwrite an existing page).
3. `parent_page_id`: ID number of the *parent* Confluence page. You can get this by going to the parent page, clicking the ellipses and navigating to 'Page Information'. The ID will be the at the end of the URL. Example: https://{URL}/pages/viewinfo.action?pageId=9653629 - the ID is 9653629.
6. `summary`: Summary of the CD/MOP, i.e. the scope of work to be performed.
1. `level`: Change Control level (0 - 3)
2. `rh`: Remote hands site(s) required, if applicable. Requires an approval ticket if supplied (below)
3. `exec`: Who is executing the Change (NOC or Core)
4. `approval`: Ticket number in which RH work was approved
5. `impact`: *List* of impacted circuits
6. `escalation`: Who Executor should escalated to if there are issues
7. `p_rollback`: 'Yes' or 'No' if partial rollback is an option
8. `rollback`: List of rollback steps (if different than the reverse order of the MOP)
9. `pm`: Pre-Maintenance needed. This will create a no-format macro.
10. `shipping`: Shipping tickets and tracking numbers
11. `sections`: Bulk of the MOP
    - Each section will be a heading in the MOP
        - Multiple options for formatting at this level:
        - `rh`, `noc`, `core`: Instructions for RH, NOC, CORE
        - `cmd-rh`, `cmd-noc`, `cmd-core`: Instructions for RH, NOC, CORE, with a 'no-format' box. First item is the instructions, second is a multiline string.
          ```yaml
          - {{ INSTRUCTIONS FOR COMMAND }}
          - |-
            Freeform, multi-
            line
            text
          ```
        - `expand-noc`, `expand-core`: Instructions for NOC, Core inside a collapsable `code block`. Useful for long configs. Do not use for RH-specific instructions as they will not see items inside a collapsed box.
          - Same format as `cmd-` but with a collapsable box instead when rendered in Confluence.
        - `jumper`: Jumper formatting inside a `no-format` box (note you could just use `cmd-rh` if you want to 'free-form' the jumper)
          - Each item in list is 'one jumper', example:
            ```yaml
            - {{ INSTRUCTIONS FOR JUMPER RUNS }}
            - acage: # Enter A Cage #
              arack: # Enter A Rack #
              adevice: # Enter A Device
              acid: # Enter A CID
              aport: # Enter A Port
              acable: # Enter A cable type, info
              aterm: # Yes, No if terminate
              label: # Enter label
              zcage: # Enter Z Cage #
              zrack: # Enter Z Rack #
              zdevice: # Enter Z Device
              zcid: # Enter Z CID
              zport: # Enter Z Port
              zcable: # Enter Z cable type, info
              zterm: # Yes, No if terminate
            ```
        - `note`: Adds a bulleted section below the previous line. Example:
          ```yaml
          - rh: Do a thing
          - note: Don't forget about this other thing
          ```

This will then be formatted in Markdown, including Confluence macros, and pushed. Example MOP:

```yaml
---
mop_repo: '/Users/jdickman/Google Drive/My Drive/MOPs/YAML/'

# absolute path to file, ignored if values set below
login_path: /Users/jdickman/Google Drive/My Drive/Scripts/usernames.yml
# locally defined, overrides 'path'
login_vars:
  cas:
  jira_url:
  confluence_url:

page_title: Do some MOP stuff
parent_page_id: 8886246
ticket: NOC-666666

summary:
- Troubleshoot CLR16376
level: 0
exec: NOC
rh: LOSA4, LOSA2
approval: NOC-333444
impact:
- No CENIC circuits will be impacted
escalation: Deploying Engineer

p_rollback: Yes
rollback:
 -
pm:
-
tech_equip:
  - Labeler
  - Cletops
  - Light meter
shipping:
    NOC-123456:
      - '772814370685'

sections:
  'Run some jumpers':
    - rh: Locate Optic X in Rack 1234.
    - note: This optic is blue.
    - jumper:
      - Run the following jumpers
      - acage: 310
        arack: 0401
        adevice: Device 1
        aport: Port 12
        acable: 10m MPO-12
        aterm: 'Yes'
        zcage: 310
        zrack: 0303
        zdevice: Device 2
        zport: 20
        zterm: 'No'
      - acage: 310
        arack: 0401
        adevice: Device 1
        aport: Port 13
        acable: 10m MPO-12
        aterm: 'Yes'
        zcage: 310
        zrack: 0303
        zdevice: Device 2
        zport: 21
        zterm: 'No'

    - cmd-noc:
      - Verify the following optics are recognized
      - |-
        Device 1:
          Optics in port 12,13

        Device 2:
          Optics in port 20,21
    - expand-core:
      - Make config changes
      - |-
        Device 1:
          interface 1
            no shutdown
            switchport vlan access 666

    - noc: Verify that Port 12 comes up.
    - note: DOM not supported on this optic.
    - cmd-rh:
      - Take some pictures of these racks
      - |-
        Rack 1
        Rack 2
        Rack 666
```

See [HERE](https://github.com/josh9730/refactored-couscous/tree/mops/mops/images/MOP.pdf) for a PDF of the completed MOP.

### CD

Change Doc specific items below:

1. `ic_url`: The Internal Change gCal url. Required to push to gCal. This guide will not cover the setup, see [HERE](https://developers.google.com/calendar/api/quickstart/python) for configuration. The IC url can be retrieved from gCal once setup.
2. `start_time`: 'military time' for start date. Used for gCal only
3. `end_time`: 'military time' for end date. Used for gCal only
4. `start_day`: Must be either 'today' or in YYYY-MM-DD format
6. `changes`: List of changes. Each item in the list will be in a separate 'code block' in Confluence

#### Examples

```yaml
---
mop_repo: '/Users/jdickman/Google Drive/My Drive/MOPs/YAML/'

# absolute path to file, ignored if values set below
login_path: /Users/jdickman/Google Drive/My Drive/Scripts/usernames.yml
# locally defined, overrides 'path'
login_vars:
  confluence_url: https://documentation.cenic.org
  jira_url: https://servicedesk.cenic.org
  cas: jdickman

ticket: SYS-670
page_title: ACL updates
parent_page_id: 9662071
summary:
 - ACL updates to svl-agg8

# times must be string, start_day must be either 'today' or in YYYY-MM-DD format
ic_url: 'cenic.org_oggku8rjbli9v7163ocroug09s@group.calendar.google.com'
start_time: 1630
end_time: 1640
start_day: 2021-11-07

changes:
  - svl-agg8:
    - |-
      edit access-lists systems-sunnyvale-ACL
      add - 15 permit ipv4 137.164.58.45 0.0.0.0 137.164.58.181 tcp 6445

      edit access-lists systems-sunnyvale-ACL-ingress
      add - 15 permit 137.164.58.181 0.0.0.0 137.164.58.45 tcp 6445

```

See [HERE](https://github.com/josh9730/refactored-couscous/tree/mops/mops/images/CD.pdf) for the PDF of the completed CD.