import paramiko

from lp import GetLP
from tools.utils import get_user_vars


def main():

    data = get_user_vars()

    username = data['cas']
    cas_pass = GetLP().get_lp('cas')[1]
    hostname = 'syslog'
    password = cas_pass

    engineers = data['core']

    command = 'zgrep {username} /var/syslog/logs/old/cisco.log.1.gz | zgrep -Ev "137.164.41.140|137.164.41.164|tus-fw-1|lam-fw-1|svl-fw-1|exit|login|logout|AUTH|TTY|LOGIN|LOGOUT|SSH|IDLE|show|ping|traceroute|configure|file"'

    client = paramiko.SSHClient()
    # add to known hosts
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=hostname, username=username, password=password)
    except:
        print("[!] Cannot connect to the SSH Server")
        exit()

    for engineer in engineers:
        print('\n', '='*50, engineer, '='*50, '\n')
        stdin, stdout, stderr = client.exec_command(command.format(username=engineer))
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print(err)

if __name__ == '__main__':
    main()