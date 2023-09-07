import socket
import subprocess

import keyring
import urllib3
from pynautobot import api

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def nb_login():
    nautobot = api(
        url=keyring.get_password("nautobot_stage", "url"),
        token=keyring.get_password(
            "nautobot-stage", keyring.get_password("cas", "user") + "mfa"
        ),
    )
    nautobot.http_session.verify = False
    return nautobot


def get_devicetype(devices: list):
    nautobot = nb_login()
    for i in devices:
        print(f"{i} = ", nautobot.dcim.devices.get(name=i).device_type)


def get_v4(hosts: list):
    # print IPv4 for host
    for i in hosts:
        v4 = socket.gethostbyname(i)
        print(f"neighbor {v4};")


def get_v6(hosts: list):
    # print IPv6 for host
    for i in hosts:
        bashCmd = ["host", i]
        process = subprocess.Popen(bashCmd, stdout=subprocess.PIPE)
        output, error = process.communicate()
        d = output.decode("utf-8")
        v6 = d.split("\n")[1].split()[4]
        print(f"neighbor {v6};")


def get_host(hosts: list):
    # print hostname from IPs
    for i in hosts:
        name = socket.gethostbyaddr(i)
        print(name[0].split(".")[0])
