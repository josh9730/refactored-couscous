from atlassian import Confluence
from pprint import pprint
import keyring

passw = keyring.get_password('cas', 'jdickman') # encrypted CAS password
confluence = Confluence(
    url='https://documentation.cenic.org/',
    username='jdickman',
    password=passw)

a = confluence.get_page_by_id(9653976,expand='body.wiki')
pprint(a)


# def rest_page_update(space,page_id,title):
#  content = confluence.get_page_by_id(page_id,expand='body.storage').get('body').get('storage').get('value')
#  body = re.sub('{group3}','', content, flags = re.M)
#  confluence.update_page(None, page_id, title, body, type='page') .get('body').get('storage').get('value')



a = """h1. === NOC Section ===

h3. SUMMARY
* Migrate circuits off patch panel in Fergus

h3. CHANGE LEVEL
Level 3

h3. REMOTE HANDS REQUIRED
FERG1

h3. EXECUTION:
NOC

h3. REMOTE HANDS APPROVAL
None

h3. CLRs IMPACTED
6526
6705
6380
16246
6827
6494
6840

h3. ESCALATION
None

h3. PARTIAL ROLLBACK
Yes

h3. ROLLBACK STEPS:
Rollback is reverse of MOP

h3. === PRE-MAINTENANCE ===
{noformat}
fre-agg-sw-3:
    show interface {{ }}

frg-agg4:
    show isis neighbor systemid {{ }}
{noformat}

h1. === MOP START ===

h4. SHIPPING
NOC-638631
- Fedex #Pending


h4. Please call 714-220-3494 before starting and reference None

h2. Section 1 - Run new jumpers
# *&#91;RH]* Run the following LC-LC SMF jumpers:
{noformat}
Jumper #1:
    A Location:
        Rack: 410.09
        Device: PP-RR.410.09:A
        Port: 11 Front
        Label: CLR6526
        Terminate: Yes

    Z Location:
        Rack: 410.11
        Device: CPT50 panel
        CID: CVIN-00052-S9D2-GE
        Port: FOG36 Port 19
        Label: CLR6526
        Terminate: Yes

Jumper #2:
    A Location:
        Rack: 410.09
        Device: PP-RR.410.09:A
        Port: 12 Front
        Label: CLR6705
        Terminate: Yes

    Z Location:
        Rack: 410.11
        Device: CPT50 panel
        CID: CVIN-00054-S10D2-GE
        Port: 24
        Label: CLR6705
        Terminate: Yes

Jumper #3:
    A Location:
        Rack: 410.09
        Device: PP-RR.410.09:A
        Port: 13 Front
        Label: CLR6380
        Terminate: Yes

    Z Location:
        Rack: 410.11
        Device: CPT50 panel
        CID: CVIN-00092-B4D2-GE
        Port: 25
        Label: CLR6380
        Terminate: Yes

Jumper #4:
    A Location:
        Rack: 410.09
        Device: PP-RR.410.09:A
        Port: 14 Front
        Label: CLR16246
        Terminate: Yes

    Z Location:
        Rack: 410.11
        Device: CPT50 panel
        CID: ?? Possibly S80109
        Port: FOG36 Port 22
        Label: CLR16246
        Terminate: Yes
{noformat}

h2. Section 2 - Migrate Circuits
# *&#91;RH]* Terminate jumper labeled CLR6526 Z End
# *&#91;RH]* Migrate the jumper from PP-RR.401.10:A Port 1 Front to PP-RR-410.09B Port 11 Back
# *&#91;NOC]* Configure as:
{noformat}
cor-agg8
  no shut
{noformat}
# *&#91;RH]* Terminate jumper labeled CLR6705 Z End

h2. Cleanup
# *&#91;RH]* Dispose of any remaining packaging materials in the racks.
# *&#91;RH]* Remove and dispose of any and all un-terminated jumpers.
# *&#91;RH]* Provide billable time.
"""

confluence.update_page(9656769, 'test', a, parent_id=None, type='page', representation='wiki', minor_edit=False)
# confluence.update_or_create(parent_id, title, body, representation='storage')