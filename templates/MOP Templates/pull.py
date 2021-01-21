from netmiko import ConnectHandler
from netmiko.ssh_autodetect import SSHDetect
import pyotp
import re 
import yaml
import keyring
import time

user = 'jdickmanmfa'
first_factor = keyring.get_password("mfa",user)
otp_secret = keyring.get_password("otp",user)
otp = pyotp.TOTP(otp_secret)

regexp = re.compile(r"\w\w\d/\d/\d/\d") # regexp to match IOS-XR interfaces

with open('migration_yaml/wave3.yaml') as file:
    migration_list = yaml.full_load(file)

open('output.txt', 'w').close() # overwrite file
file = open('output.txt', 'a') # open file in append mode

ios_commands = [
    'show ver | include physical memory'
    'show ip bgp sum | b Nei'
    'show bgp ipv6 un sum | b Nei'
    'show run | sec peer-group'
    'show ip route | in 0.0.0.0/0'
    'show ipv6 route | in ::0/0'
]

xr_commands = [
    'show bgp sum | b Nei'
    'show bgp ipv6 un sum | b Nei'
    'show run router bgp 2152 | in neighbor-group'
    'show route 0.0.0.0/0'
    'show route ipv6 ::0/0'
    'show run router bgp'
]

junos_commands = [
    'show bgp summary | match Establ'
    'show route 0.0.0.0/0 exact'
    'show route ::0/0 exact'
    'show configuration protocols bgp'
]
asr_ports = [
    'show run interface {}'
    'show arp {}'
    'show run router isis 2152 interace {}'
]
asr_bgp = [
    'show bgp sum | in {}'
    'show run router bgp 2152 nei {}'
]


def connect(type, host, passwd):    # connect to device using guessed type
    connection = ConnectHandler(
    device_type = type,
    host = host,
    username = user, 
    password = passwd)
    return connection

def run_commands(device, connection, formats, command_list): # cycle through commands and format
    device_result = [f"\n\n\n{'='*20} {device} {'='*20}"] #header
    for commands in command_list: # loop through commands
        command_result = connection.send_command(commands.format(formats)) # send commands
        device_result.append(f"\n{'='*3} {commands} {'='*3}\n") # mini-header for the command input
        device_result.append(command_result) # append output after each command
    connection.disconnect()
    return device_result


hub_router = migration_list['global']['L3_old']
print(hub_router)
start_time = time.time()

j = [] # open list for len
k = 1 # start loop index

for i in migration_list['data']:
    j.append(i['name']) # create list of items in yaml for len

# for i in migration_list['data']:
#     password = first_factor + otp.now() # generate new password
#     if i.['cpe-port'].startswith('et') or i.['cpe-port'].startswith('xe'):
#         connection = connect('juniper_junos', i.['cpe'], password) # run connection function
#         device_result_list = run_commands(i.['cpe'], connection, i.['cpe_port'], junos_commands) # run command function
#     elif regexp.match(i.['cpe_port']): #match XR
#         connection = connect('cisco_xr', i.['cpe'], password) # run connection function
#         device_result_list = run_commands(i.['cpe'], connection, i.['cpe_port'], xr_commands) # run command function
#     else: #match IOS, by default
#         connection = connect('cisco_ios', i.['cpe'], password) # run connection function
#         device_result_list = run_commands(i.['cpe'], connection, i.['cpe_port'], ios_commands) # run command function

IPs = []
hub_ports = []
for i in migration_list['data']:
    hub_ports.append(i['old_L3'])
    if i['bgp_ipv4']:
        IPs.append(i['bgp_ipv4'])
        if i['bgp_ipv6']:
            IPs.append(i['bgp_ipv6'])
for i in IPs: 
    password = first_factor + otp.now() # generate new password
    connection = connect('cisco_xr', hub_router, password)
    device_result_list = run_commands(hub_router, connection, hub_ports, asr_ports) # run command function
    device_result_list = run_commands(hub_router, connection, IPs, asr_bgp) # run command function




# for i in migration_list['data']:
#     password = first_factor + otp.now() # generate new password
#     if i['device_type'] != 'N/A' and i['device_type'] != 'switch':
#         if str(i['device_type']).startswith('1001'):
#             connection = connect('cisco_ios', i['cpe'], password) # run connection function
#             device_result_list = run_commands(i['cpe'], connection, commands_list['ios_show_commands']) # run command function
#         elif str(i['device_type']) == '9001':
#             connection = connect('cisco_xr', i['cpe'], password) # run connection function
#             device_result_list = run_commands(i['cpe'], connection, commands_list['xr_show_commands']) # run command function
#         elif str(i['device_type']) == 'mx204':
#             connection = connect('juniper_junos', i['cpe'], password) # run connection function
#             device_result_list = run_commands(i['cpe'], connection, commands_list['junos_show_commands']) # run command function
#         output = ('\n'.join(device_result_list))
#         file.write(output) # write output to file
#         if k < len(j): # if there are more devices in list, reset otp
#             time.sleep(30)
#     else: 
#         pass 
#     k += 1

file.close() # close file once all devices are done

elapsed_time = time.time() - start_time
print(f'{elapsed_time:.2f} seconds')
