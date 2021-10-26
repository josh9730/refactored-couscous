''' Pending weekly re-sync with active ports..

    - Gets start/end dates for pull
    - first_report() gets all active interfaces with edge tag
    - weekly_report() uses existing DF and gets latest traffic report
    - DF is updated & pushed to sheet
    - need to extend to append new interfaces to DF
'''

from datetime import datetime, timedelta
from gspread_pandas import Spread
import pandas as pd
import requests
import json
import time
import gspread
import yaml
import os
from pprint import pprint

with open('/Users/jdickman/Google Drive/My Drive/Scripts/usernames.yml') as file:
    data = yaml.full_load(file)['scilo_api']

user = data['username']
passw = data['pass']
sheet_key = data['zoom_sheet']
sheet_name = 'Data'

def normalize_hourly(data):
    # highest 10 values, takes second highest (95th percentile)

    data_list = []
    for i in list(data.values()):
        data_list.append(round(float(i) * 8 / 60) )

    data_list.sort(reverse=True)

    return data_list[1]

def get_times():

    # get today's date, find previous week's start/end with timedelta and strip only Y/M/D, split to list and convert each item to int
    today = datetime.now()
    week_start_list = [ int(i) for i in (today - timedelta(days=7)).strftime('%Y-%m-%d').split('-')]
    week_end_list = [ int(i) for i in (today.strftime('%Y-%m-%d').split('-'))]
    # week_end_list = [ int(i) for i in (today - timedelta(days=4)).strftime('%Y-%m-%d').split('-')]

    # create datetime object from list created above, and convert to timestamp format
    week_start_datetime = datetime(week_start_list[0], week_start_list[1], week_start_list[2])
    week_end_datetime = datetime(week_end_list[0], week_end_list[1], week_end_list[2])
    week_start = int(week_start_datetime.timestamp())
    week_end = int(week_end_datetime.timestamp())
    week_number = datetime.date(week_start_datetime).isocalendar()[1]

    return week_start, week_end, week_number

def get_traffic(week_start, week_end, port_id, user, passw):

    port_traffic = requests.get(f'https://scilo.tus.cenic.org{port_id}/interface_data/normalized_hourly?hide_filterinfo=1&beginstamp={week_start}&endstamp={week_end}',
                                       auth=requests.auth.HTTPBasicAuth(user, passw)).json()

    ingress_max_norm = normalize_hourly(port_traffic['data']['d_octets_in']['max'])
    egress_max_norm = normalize_hourly(port_traffic['data']['d_octets_out']['max'])
    max_norm = max([ ingress_max_norm, egress_max_norm ])

    return max_norm

def get_ports_full(user, passw):
    edge_ports_full = requests.get('https://scilo.tus.cenic.org/api/interface/?hide_filterinfo=1&limit=999&filter.state=1&filter.alias.contains=dc%3Aedge&extended_fetch=1&filter.device.not=%2Fapi%2Fdevice%2F0',
                              auth=requests.auth.HTTPBasicAuth(user, passw)).json()

    return edge_ports_full

def get_ports(user, passw):
    edge_ports = requests.get('https://scilo.tus.cenic.org/api/interface/?hide_filterinfo=1&limit=999&filter.state=1&filter.alias.contains=dc%3Aedge&filter.device.not=%2Fapi%2Fdevice%2F0',
                              auth=requests.auth.HTTPBasicAuth(user, passw)).json()

    edge_ports_list = []
    for i in edge_ports:
        edge_ports_list.append(i['URI'].split('/')[3])

    return edge_ports_list

def get_site_codes():

    site_code_sheet = 'Sheet1'
    gc = gspread.oauth()
    sh = gc.open('Site Codes')
    worksheet = sh.worksheet(site_code_sheet)
    sites_name = worksheet.col_values(1)[2:]
    sites_code = worksheet.col_values(2)[2:]

    return dict(zip(sites_code, sites_name))

def main(user, passw, first_report=False):

    week_start, week_end, week_number = get_times()

    if first_report:

        edge_ports_full = get_ports_full(user, passw)
        site_names_dict = get_site_codes()

        port_id, site_list, segment_list, speed_list, max_norm_list, util_list = ([],[],[],[],[],[])

        for counter, i in enumerate(edge_ports_full, 1):

            try:
                site_code = re.search("dc:site-[a-z1-9]+", edge_ports_full[i]['alias']).group().split('-')[1]
                site_name = site_names_dict[site_code]
            except:
                site_name = 'unknown'
            try:
                segment_code = re.search("[a-z]+:(?!ext|edge|site-)([a-z1-2]+)", edge_ports_full[i]['alias']).group().split(':')[1]
            except:
                segment_code = 'unknown'
            site_list.append(site_name)
            segment_list.append(segment_code)
            speed_list.append(edge_ports_full[i]['ifHighSpeed'])
            port_id.append(i.split('/')[3])
            try:
                max_norm = get_traffic(week_start, week_end, i, user, passw)
                max_norm_list.append(max_norm)
                util = round(max_norm / (int(edge_ports_full[i]['ifHighSpeed']) * 10000), 2)
                util_list.append(util)
            except:
                max_norm_list.append(0)
                util_list.append(0)
            if (counter/50).is_integer():
                time.sleep(5)

        data_df = {
            'Site': pd.Series(site_list, index=port_id),
            'Segment': pd.Series(segment_list, index=port_id),
            'Speed (Mbps)': pd.Series(speed_list, index=port_id),
            'Week' + str(week_number) + ' Max (bps)': pd.Series(max_norm_list, index=port_id),
            'Week' + str(week_number) + ' Util %': pd.Series(util_list, index=port_id)
        }
        data_df = pd.DataFrame(data_df)

    else:
        data_df = pd.read_json('zoom.json')
        id_list = data_df.index.tolist()

        max_norm_list, util_list, wow_list = ([],[],[])

        for counter, i in enumerate(id_list, 1):

            try:
                port_id = f'/api/interface/{i}'
                max_norm = get_traffic(week_start, week_end, port_id, user, passw)
                max_norm_list.append(max_norm)

                util_list.append(round(max_norm / (int(data_df.at[i, 'Speed (Mbps)']) * 10000), 2))
                prev_max = data_df.at[i, ('Week' + str(week_number - 1) + ' Max (bps)')]
                wow_list.append(round((max_norm - prev_max) / ((prev_max + max_norm) / 2) * 100, 2))

            except:
                max_norm_list.append(0)
                util_list.append(0)
                wow_list.append(0)

            if (counter/50).is_integer():
                time.sleep(5)

        data_df = data_df.join(pd.Series(max_norm_list, index=id_list, name=('Week' + str(week_number) + ' Max (bps)')))
        data_df = data_df.join(pd.Series(util_list, index=id_list, name=('Week' + str(week_number) + ' Util %')))
        data_df = data_df.join(pd.Series(wow_list, index=id_list, name=('Week' + str(week_number) + ' WoW %')))

    return data_df


def first_report():

    site_code_sheet = 'Sheet1'
    gc = gspread.oauth()
    sh = gc.open('Site Codes')
    worksheet = sh.worksheet(site_code_sheet)
    sites_name = worksheet.col_values(1)[2:]
    sites_code = worksheet.col_values(2)[2:]
    site_names_dict = dict(zip(sites_code, sites_name))

    week_start, week_end, week_number = get_times()

    edge_ports = requests.get('https://scilo.tus.cenic.org/api/interface/?hide_filterinfo=1&limit=999&filter.state=1&filter.alias.contains=dc%3Aedge&extended_fetch=1',
                              auth=requests.auth.HTTPBasicAuth(user, passw)).json()

    port_id, site_list, segment_list, speed_list, max_norm_list, util_list = ([],[],[],[],[],[])
    for counter, i in enumerate(edge_ports, 1):
        if edge_ports[i]['device'] != '/api/device/0':

            try:
                site_code = re.search("dc:site-[a-z1-9]+", edge_ports[i]['alias']).group().split('-')[1]
                site_name = site_names_dict[site_code]
            except:
                site_name = 'unknown'

            try:
                segment_code = re.search("[a-z]+:(?!ext|edge|site-)([a-z1-2]+)", edge_ports[i]['alias']).group().split(':')[1]
            except:
                segment_code = 'unknown'

            site_list.append(site_name)
            segment_list.append(segment_code)
            speed_list.append(edge_ports[i]['ifHighSpeed'])
            port_id.append(i.split('/')[3])

            try:

                max_norm = get_traffic(week_start, week_end, i, user, passw)
                max_norm_list.append(max_norm)

                util = round(max_norm / (int(edge_ports[i]['ifHighSpeed']) * 10000), 2)
                util_list.append(util)

            except:
                max_norm_list.append(0)
                util_list.append(0)

            if (counter/50).is_integer():
                time.sleep(5)

    data_df = {
        'Site': pd.Series(site_list, index=port_id),
        'Segment': pd.Series(segment_list, index=port_id),
        'Speed (Mbps)': pd.Series(speed_list, index=port_id),
        'Week' + str(week_number) + ' Max (bps)': pd.Series(max_norm_list, index=port_id),
        'Week' + str(week_number) + ' Util %': pd.Series(util_list, index=port_id)
    }

    return pd.DataFrame(data_df)

def weekly_report():

    week_start, week_end, week_number = get_times()

    data_df = pd.read_json('zoom.json')
    id_list = data_df.index.tolist()

    max_norm_list, util_list, wow_list = ([],[],[])
    for counter, i in enumerate(id_list, 1):

        try:
            port_id = f'/api/interface/{i}'
            max_norm = get_traffic(week_start, week_end, port_id, user, passw)
            max_norm_list.append(max_norm)

            util_list.append(round(max_norm / (int(data_df.at[i, 'Speed (Mbps)']) * 10000), 2))
            prev_max = data_df.at[i, ('Week' + str(week_number - 1) + ' Max (bps)')]
            wow_list.append(round((max_norm - prev_max) / ((prev_max + max_norm) / 2) * 100, 2))

        except:
            max_norm_list.append(0)
            util_list.append(0)
            wow_list.append(0)

        if (counter/50).is_integer():
            time.sleep(5)

    data_df = data_df.join(pd.Series(max_norm_list, index=id_list, name=('Week' + str(week_number) + ' Max (bps)')))
    data_df = data_df.join(pd.Series(util_list, index=id_list, name=('Week' + str(week_number) + ' Util %')))
    data_df = data_df.join(pd.Series(wow_list, index=id_list, name=('Week' + str(week_number) + ' WoW %')))

    return data_df

if __name__ == "__main__":

    script_dir = os.path.dirname(__file__)
    with open(os.path.join(script_dir, 'usernames.yml')) as file:
        data = yaml.full_load(file)['scilo_api']

    user = data['username']
    passw = data['pass']
    sheet_key = data['zoom_sheet']
    sheet_name = 'Data'

    # data_df = first_report()
    data_df = weekly_report()

    # data_df = main(user, passw, first_report=True)
    # get_ports(user, passw)

    data_df.to_json('zoom.json', indent=2)
    gsheet = Spread(sheet_key, sheet_name)
    gsheet.df_to_sheet(data_df, replace=True, index=False, sheet=sheet_name, start='A1')



# left = pd.DataFrame({'A': ['A0', 'A1', 'A2', 'A3'],
#                     'B': ['B0', 'B1', 'B2', 'B3']},
#                     index = ['K0', 'K1', 'K2', 'K3'])
  
# right = pd.DataFrame({'C': ['C0'],
#                       'D': ['D0']},
#                       index = ['K4'])

# a = left.append(right)
# print(a)