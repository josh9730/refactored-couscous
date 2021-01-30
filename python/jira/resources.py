from atlassian import Jira
from datetime import datetime
from datetime import timedelta
import keyring
import gspread

def update_rotating_bucket(jira, bucket, hours):
    """Update rotation buckets (shipping and EngRv)
    Allocation is per week
    """

    last_week = (datetime.today() - timedelta(weeks=1)).strftime('%Y-%m-%d')
    for i in bucket:
        start_date = jira.issue_field_value(i, 'customfield_10410')
        orig_est = {'timetracking': {'originalEstimate': str(hours)+ 'h'}}
        jira.update_issue_field(i, orig_est)

        # Rotates the previous week's bucket to end of rotation
        if start_date == last_week:
            new_start = (datetime.today() + timedelta(weeks=(len(bucket)-1))).strftime('%Y-%m-%d')
            new_end = (datetime.today() + timedelta(weeks=(len(bucket)-1), days=5)).strftime('%Y-%m-%d')

            field_start = {'customfield_10410': new_start}
            field_end = {'customfield_10411': new_end}

            jira.update_issue_field(i, field_start)
            jira.update_issue_field(i, field_end)

def update_circuit(jira, bucket, hours):
    """Update circuit deployment bucket based on # of active circuits
    """

    gc = gspread.oauth()
    sh = gc.open('Core Tickets')
    worksheet = sh.worksheet('Tables')

    eugene = worksheet.get('C2')[0][0]
    nelson = worksheet.get('C3')[0][0]
    tunde = worksheet.get('C4')[0][0]
    mohammed = worksheet.get('C5')[0][0]
    engineer = [ eugene, nelson, tunde, mohammed ]

    new_start = datetime.today().strftime('%Y-%m-%d')
    new_end = (datetime.today() + timedelta(weeks=(len(bucket)-1), days=5)).strftime('%Y-%m-%d')

    # Get time in hours - # of circuits * hours/circuit * 4 (weeks), and update list
    j = 0
    for i in engineer:
        engineer[j] = str(int(i) * hours * 4) + 'h'
        j += 1

    # Update buckets - move start/end ahead one week, update hours
    j = 0
    for i in bucket:
        field_start = {'customfield_10410': new_start}
        field_end = {'customfield_10411': new_end}
        orig_est = {'timetracking': {'originalEstimate': engineer[j]}}

        jira.update_issue_field(i, field_start)
        jira.update_issue_field(i, field_end)
        jira.update_issue_field(i, orig_est)
        j += 1

def main():
    # start-date: customfield_10410
    # end-date: customfield_10411

    username = 'jdickman'
    password = keyring.get_password('cas', username) # encrypted CAS password
    jira = Jira( # connection
        url = 'https://servicedesk.cenic.org',
        username = username,
        password = password)

    """ EngRv order:
    Tunde: COR-1055
    Nelson: COR-1056
    Eugene: COR-1058
    Josh: COR-1054
    Mohammed: COR-1057
    """
    escalation_bucket = [ 'COR-1055', 'COR-1056', 'COR-1058', 'COR-1054', 'COR-1057' ]
    engrv_hours = 4
    update_rotating_bucket(jira, escalation_bucket, engrv_hours)


    """ Shipping Order:
    Nelson: COR-1100
    Eugene: COR-1099
    Tunde: COR-1101
    Mohammed: COR-1102
    """
    shipping_bucket = [ 'COR-1100', 'COR-1099', 'COR-1101', 'COR-1102' ]
    shipping_hours = 5
    update_rotating_bucket(jira, shipping_bucket, shipping_hours)


    """ Circuit Buckets:
    Eugene: COR-732
    Nelson: COR-1059
    Tunde: COR-1060
    Mohammed: COR-1061
    """
    circuit_bucket = [ 'COR-732', 'COR-1059', 'COR-1060', 'COR-1061' ] # MUST BE SAME ORDER AS THE ENGINEER LIST
    circuit_hours = 2
    update_circuit(jira, circuit_bucket, circuit_hours)


if __name__ == '__main__':
    main()