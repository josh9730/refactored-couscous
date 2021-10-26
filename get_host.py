""" Get Hostname, Interface, description from BGP neighbor
"""

import subprocess

def get_hostname(IP):
    # print('---\nAddress: ', IP,)
    bashCmd = ['host', f'{IP}']
    process = subprocess.Popen(bashCmd, stdout=subprocess.PIPE)
    output, error = process.communicate()
    print(f'{IP.strip()}: ', str(output, 'utf-8').split(' ')[4].split('.')[0])

if __name__ == '__main__':
    with open("ips.txt") as file:
        IPs = [line.strip() for line in file]
    for i in IPs:
        get_hostname(i)