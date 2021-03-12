## MOP Program

Program to create, format, and push MOPs and Change Docs to Confluence & GCal. The MOP/CD itself is written in the `mop.yaml` file and formatted with jinja.

## Creation

The python script uses jinja templates to format the MOP input from the `mop.yaml` file. Pushes to Confluence automatically.

## YAML Keys for Both

1. `'ticket`: Ticket number related to the change. Should be full ticket, ie `COR-123` not just `123`.
2. `page_title`: Title of the MOP/CD Confluence page
3. `parent_page_id`: ID number of the *parent* Confluence page. You can get this by going to the parent page, clicking the ellipses and navigating to 'Page Information'. The ID will be the at the end of the URL. Example: https://documentation.cenic.org/pages/viewinfo.action?pageId=9653629 - the ID is 9653629.
4. `mop_directory`: This is the folder in which `mop.yaml` lives. This is used for the copy feature, see below.
5. `mop_repo`: This is where the `mop.yaml` file will be copied to after the program runs for long term reference. The title of the file will become the `page_title`.
6. `link`: **true** or **false**, depending on if you want a link between the Jira ticket and the Confluence page. Note that each time you run this, it will create a *new* link in Jira. If you run a second time (for instance, to edit the MOP), mark this as false for the second run.
7. `summary`: Summary of the CD/MOP

### Examples

```
---
  ticket: COR-1303
  page_title: Tustin VPN Configs
  parent_page_id: 9653629
  mop_directory: '/Users/jdickman/Git/refactored-couscous/mop.yaml'
  mop_repo: '/Users/jdickman/Git/1 - Docs/MOPs/YAML/'
  link: false
  summary:
    - Configure Enterprise IPVPN setup at Tustin
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
9. `pm`: Pre-Maintenance needed
10. `shipping`: Shipping tickets and tracking numbers
11. `sections`: Bulk of the MOP
    - Each section will be a heading in the MOP
        - Multiple options for formatting at this level:
        - `rh`, `noc`, `core`: Instructions for RH, NOC, CORE
        - `cmd-rh`, `cmd-noc`, `cmd-core`: Instructions for RH, NOC, CORE, with a 'no-format' box
            - The first item is the 'title'
            - The second is a multiline string (start with `|-`)
        - `jumper`: Jumper formatting inside a 'no-format' box (note you could just use `cmd-rh` if you want to 'free-form' the jumper)
            - Each item in list is 'one jumper', example:
                ```
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

```
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
  shipping:
    NOC-639281:
      - Pending
  sections:
    'Power Down Devices':
      - rh: All equipment in Racks 006 & 007 need to be removed. The Cisco 7204 from Rack 008 and the Cisco 4506 from Rack 004 are being removed as well.
      - cmd:
          - These are the following devices
          - |-
              cor-dis-sw-1
              cor-agg3
              cor-agg-sw-1
              cor-agg4
              cor-agg2
              NLR 15808
      - rh: Power down all 6 devices if not already done. Remove and dispose of the power cabling.
      - rh: Disconnect and dispose of all fiber/copper jumpers to the 6 devices.
      - rh: Unrack and palletize all 6 onto the shipped pallets and shrink-wrap/secure them as needed for freight shipment.
      - rh: Disconnect the PDUs in Racks 006,007 from the power feeds. Remove the PDUs and palletize them as well.
      - rh: Migrate PP-RR.006-SC panel from 006 as well if not already done.
      - rh: Dispose of any remaining cables, boxes, trash, etc from Racks 006 & 007.
      - rh: Verify that both racks are COMPLETELY empty. Send pictures of the racks to oper@cenic.org.
      - rh: If any devices cannot be palletized for some reason, please rack in racks 004, 005, 008, and inform NOC of the Rack # and RU.
      - rh: Provide dimensions of the pallets with the equipment, along with the approximate weight. This is needed for the Fedex freight pickup. Another window will be scheduled once the freight pickup is confirmed.
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

```
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