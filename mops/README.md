# MOP Program

Program to create, format, and push MOPs and Change Docs to Confluence & GCal. The MOP/CD itself is written in the `mop.yaml` file and formatted with jinja.

## Creation

The python script uses jinja templates to format the MOP input from the `mop.yaml` file. Pushes to Confluence automatically.

### Args

See `python3 mop.py -h` for help.

- `-u {{ CAS USERNAME }}`: Your CAS username is required for logging into Jira/Confluence. This must either be supplied via this arg or in a username file (see next section)
- `-l`: Add Jira Link. Note that this should only be done once, if an edit is pushed do not specify a link as this will create multiple links (can be removed in Jira)

### Keyring

The CAS password is expected to be stored in keyring, and your CAS username will be supplied to retrieve. To add your CAS password to keyring:

1. First, python3.6+ must be installed.
2. If you have not already installed the `requirements.txt`, do so: `pip3 install -r requirements.txt`.
3. Keyring is accessed via terminal directly:
  - Enter in a terminal window: `keyring set cas {{ CAS USERNAME }}`
    - At the prompt, enter: `{{ CAS PASSWORD }}`

### YAML Keys for Both MOP & Change Document

1. `username_file_path`: Directory in which the usernames file lives. This can be skipped if you supply the `-u {{ CAS USERNAME }}` when running.
2. `mop_directory`: This is the folder in which `mop.yaml` lives. This is used for the copy feature, see below.
3. `mop_repo`: This is where the `mop.yaml` file will be copied to after the program runs for long term reference. The title of the file will become the `page_title`.
4. `ticket`: Ticket number related to the change. Should be full ticket, ie `COR-123` not just `123`.
5. `page_title`: Title of the MOP/CD Confluence page
6. `parent_page_id`: ID number of the *parent* Confluence page. You can get this by going to the parent page, clicking the ellipses and navigating to 'Page Information'. The ID will be the at the end of the URL. Example: https://documentation.cenic.org/pages/viewinfo.action?pageId=9653629 - the ID is 9653629.
7. `summary`: Summary of the CD/MOP

#### Examples

```yaml
---
username_file_path: /Users/jdickman/Git/refactored-couscous/usernames.yml
mop_directory: '/Users/jdickman/Git/refactored-couscous/mops/mop.yaml'
mop_repo: '/Users/jdickman/Git/1 - Docs/MOPs/YAML/'

ticket: NOC-633101
page_title: UCB cutover 10G DC to 100G DC
parent_page_id: 8881603
summary:
 - Cut over UCB service from CLR-8040 to CLR-16569
```

### MOP

Uses the `mop-gen.j2` template. MOP specific items below:

1. `level`: Change Control level
2. `rh`: Remote hands site(s) required, if applicable
3. `exec`: Who is executing the Change (NOC or Core)
4. `approval`: Ticket number in which RH work was approved
5. `impact`: List of impacted circuits
6. `escalation`: Who NOC should escalated to if there are issues
7. `p_rollback`: 'Yes' or 'No' if partial rollback is an option
8. `rollback`: List of rollback steps (if different than the reverse order of the MOP)
9. `pm`: Pre-Maintenance needed. This is done similar to the `cmd-*` options (see below)
    - {{ INSTRUCTIONS FOR COMMAND }}
      - pre-maintenance items
    - Example:
    ```
    - |-
      lax-agg10:
        show interface desc
    - |-
      riv-agg8:
        show interface description
    ```
10. `shipping`: Shipping tickets and tracking numbers
11. `sections`: Bulk of the MOP
    - Each section will be a heading in the MOP
        - Multiple options for formatting at this level:
        - `rh`, `noc`, `core`: Instructions for RH, NOC, CORE
        - `cmd-rh`, `cmd-noc`, `cmd-core`: Instructions for RH, NOC, CORE, with a 'no-format' box. First item is the instructions, second is a multiline string.
            - {{ INSTRUCTIONS FOR COMMAND }}
            - The second is a multiline string (start with `|-`)
        - `jumper`: Jumper formatting inside a 'no-format' box (note you could just use `cmd-rh` if you want to 'free-form' the jumper)
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
        - `expand-noc`, `expand-core`: Instructions for NOC, Core inside a collapsable `code block`. Useful for long configs. Do not use for RH-specific instructions as they will not see items inside a collapsed box.
            - Same format as `cmd-` but with a collapsable box instead

#### Examples

```yaml
  level:
    - 0
  rh:
    - CORN1
  exec:
    - NOC
  approval:
    - NOC-628538
  impact:
    - None
  escalation:
    -
  p_rollback:
    -
  rollback:
    - Rollback is reverse of MOP
  pm:
    - |-
      lax-agg10:
        show interface desc
    - |-
      riv-agg8:
        show interface description
  shipping:
    NOC-639281:
      - Pending
  sections:
    'Do Some Stuff':
      - rh: Go check this rack
      - cmd-noc:
          - Login to these devices
          - |-
              cor-dis-sw-1
              cor-agg3
              cor-agg-sw-1
              cor-agg4
              cor-agg2
              NLR 15808
      - cmd-noc:
        - Do these configs
        - |-
            oak-agg8
            conf
            int HundredGigE0/1/0/17
            no shut
            show comm ch d
            commit
      - jumper:
        - Run the following jumpers
        - acage: 310
          arack: 0401
          adevice: LOSA1CA52T
          aport: Shelf 1 Slot 14 Port 1 (CPAK)
          acable: 10m MPO-12
          zcage: 310
          zrack: 0303
          zdevice: CP:0303:1023270
          zport: 20 Front (Equinix cross connect to Cage 180 in back)
        - acage: 310
          arack: 0401
          adevice: LOSA1CA52T
          aport: Shelf 1 Slot 14 Port 2 (trunk)
          acable: 10m LC-LC SMF (verify with trace)
          zcage: 310
          zrack: From fiber trace step
          zdevice: From fiber trace step
          zport: From fiber trace step
      - expand-core:
        - Configure riv-agg8
        - |-
          riv-agg8:
            address-family ipv4 unicast
            address-family ipv4 multicast
            address-family ipv6 unicast
            address-family ipv4 multicast
            address-family vpnv4 unicast
            address-family vpnv4 multicast
            address-family vpnv6 unicast
            address-family vpnv6 multicast
            address-family ipv4 mvpn
            address-family ipv6 mvpn
            address-family ipv4 rt-filter
            address-family l2vpn evpn
      - noc: Verify services
      - rh: Provide billable time.
```

See ticket NOC-641508 for example output.

### CD

Uses the `cd-gen.j2` template. Change Doc specific items below:

1. `cd:` All items for Change Docs are under this key
2. `start_time`: 'military time' for start date. Used for GCal only
3. `end_time`: 'military time' for end date. Used for GCal only
4. `start_day`: Must be either 'today' or in YYYY-MM-DD format
5. `calendar`: **true** or **false**, depending on if you want to create a GCal entry (you must have authenticated to Google and have a `token.pickle` in the directory)
6. `changes`: List of changes. Each item in the list will be in a separate 'code block' in Confluence

#### Examples

```yaml
  cd: # times must be string, start_day must be either 'today' or in YYYY-MM-DD format
    start_time: 1800
    end_time: 2000
    start_day: 2021-03-12
    calendar: false
    changes:
      - tus-agg8-sw-1:
        - |
            vlan id 2040
            !
            interface e1/12
              switchport trunk allowed vlan add 2040
            !
            interface e1/49/1
              switchport trunk allowed vlan add 2040
            !
      - LAM-GW-1:
        - |
            vrf definition ent
              rd auto
              address-family ipv4
              exit-address-family
            !
```

Example Page: https://documentation.cenic.org/display/Core/Tustin+VPN+Configs