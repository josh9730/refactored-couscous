from enum import Enum
import re
import pyotp
import keyring
import pexpect
import typer
import time

from netmiko import ConnectHandler
from lastpass import Vault

"""
keyring set cas email
    {{ EMAIL}}
keyring set lp_pass {{ EMAIL }}
    {{ PASSWORD }}
keyring set lp_pass otp
    {{ OTP TOKEN }}

keyring set cas user
    {{ CAS USERNAME }}
mfa_user = cas_user + 'mfa'
keyring set mfa {{ MFA USERNAME }}
    {{ MFA FIRST FACTOR }}
keyring set otp {{ MFA USERNAME }}
    {{ OTP TOKEN }}
"""

logins = typer.Typer(
    add_completion=False,
    help="""
Multi-function login helper. Can return Lastpass accounts,
SSH/Telnet to devices via MFA, Backdoor, or CAS accounts, or
send Netmiko commands to a list of devices.

Requires Keyring:

    - keyring set cas email

    - keyring set lp_pass {{ EMAIL }}

    - keyring set lp_pass otp

    - keyring set cas user

    - mfa_user = cas_user + 'mfa'

    - keyring set mfa {{ MFA USERNAME }}

    - keyring set otp {{ MFA USERNAME }}
""",
)


class LPChoices(str, Enum):
    """Enum choices for return_lp command"""

    optical = "Optical"
    enable = "Enable"
    oob = "OOB"
    cas = "CAS"
    tacacs = "TACACS"


def get_lp(account: str):

    _shorthand = {
        "Optical": bytes("Optical", "utf-8"),
        "Enable": bytes("CENIC Enable Account", "utf-8"),
        "OOB": bytes("CENIC Out-of-Band- OOB", "utf-8"),
        "CAS": bytes("CAS", "utf-8"),
        "TACACS": bytes("CENIC TACACS Key", "utf-8"),
    }

    cas_email = keyring.get_password("cas", "email")
    lp_pass = keyring.get_password("lp_pass", cas_email)
    lp_otp = pyotp.TOTP(keyring.get_password("lp_pass", "otp"))

    name = _shorthand[account]
    vault = Vault.open_remote(cas_email, lp_pass, lp_otp.now())

    for account in vault.accounts:
        if account.name == name:

            if account.name == bytes("CENIC Out-of-Band- OOB", "utf-8"):
                # OOB account stored differently than usual logins
                user_re = re.compile(r"Super User:\S+")
                pass_re = re.compile(r"Password:\S+")
                passthrough_re = re.compile(r"Passthrough:\S+")

                lp_logon_url = str(account.url, "utf-8")
                lp_logon_user = (
                    user_re.search(str(account.notes, "utf-8"))
                    .group()
                    .lstrip("Super User:")
                )
                lp_logon_pass = (
                    pass_re.search(str(account.notes, "utf-8"))
                    .group()
                    .lstrip("Password:")
                )
                lp_logon_passthrough = (
                    passthrough_re.search(str(account.notes, "utf-8"))
                    .group()
                    .lstrip("Passthrough:")
                )

            else:
                lp_logon_url = str(account.url, "utf-8")
                lp_logon_user = str(account.username, "utf-8")
                lp_logon_pass = str(account.password, "utf-8")
                lp_logon_passthrough = ""

    return lp_logon_user, lp_logon_pass, lp_logon_passthrough, lp_logon_url


def netmiko_connect(device_type, device_name):
    mfa_user, first_factor, otp = mfa_default()
    password = first_factor + otp.now()
    connection = ConnectHandler(
        device_type=device_type,
        host=device_name,
        username=mfa_user,
        password=password,
        fast_cli=False,  # disabled for IOS-XRs
    )
    return connection


def mfa_default():
    """Default user, pass, otp for MFA network logins."""
    mfa_user = keyring.get_password("cas", "user") + "mfa"
    first_factor = keyring.get_password("mfa", mfa_user)
    otp = pyotp.TOTP(keyring.get_password("otp", mfa_user))
    return mfa_user, first_factor, otp


def ssh_default(hostname, username, password):
    """Default actions for SSH. Returns CLI prompt."""
    child = pexpect.spawn(
        f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no {username}@{hostname} | ct"'
    )
    child.expect("assword:")
    child.sendline(password)
    child.interact()


def telnet_default(hostname, username, password):
    """Default actions for Telnet. Returns CLI prompt."""
    child = pexpect.spawn(f'/bin/bash -c "telnet -4 {hostname} | ct"')
    child.expect("Username:")
    child.sendline(username)
    child.expect("assword:")
    child.sendline(password)
    child.interact()


@logins.command()
def mfa(hostname: str = typer.Argument(..., help="Device hostname")):
    """Use MFA account to login to network devices with ssh."""
    mfa_user, first_factor, otp = mfa_default()
    ssh_default(hostname, mfa_user, first_factor + otp.now())


@logins.command()
def enable(hostname: str = typer.Argument(..., help="Device hostname")):
    """Use Backdoor account to login to network devices with ssh.

    Account is retrieved via LastPass API.
    """
    username, password, *args = get_lp("Enable")
    ssh_default(hostname, username, password)


@logins.command()
def cas(hostname: str = typer.Argument(..., help="Device hostname")):
    """Use CAS account to login to non-network devices with ssh."""
    username = keyring.get_password("cas", "user")
    password = keyring.get_password("cas", username)

    ssh_default(hostname, username, password)


@logins.command()
def telnet_mfa(hostname: str = typer.Argument(..., help="Device hostname")):
    """Use MFA account to login to network devices with telnet."""
    mfa_user, first_factor, otp = mfa_default()
    telnet_default(hostname, mfa_user, first_factor + otp.now())


@logins.command()
def telnet_enable(hostname: str = typer.Argument(..., help="Device hostname")):
    """Use Backdoor account to login to network devices with telnet.

    Account is retrieved via LastPass API.
    """
    username, password, *args = get_lp("Enable")
    telnet_default(hostname, username, password)


@logins.command()
def lpass(
    account: LPChoices = typer.Argument(..., case_sensitive=False, help="Account")
):
    """Return LastPass username, password, URL, and optionally Passthrough pass from LastPass.

    Account name is case-insensitive.
    """
    account_name = account.value
    output = get_lp(account_name)
    print("\n\tURL:\t\t", output[3])
    print("\tUsername:\t", output[0])
    print("\tPassword:\t", output[1])
    if output[2]:
        print("\tPassthrough:\t", output[2])
    print("\n")


@logins.command()
def netmiko_pull(
    devices: str = typer.Option(..., prompt=True, help="Comma-separated string of devices & device types"),
    command: str = typer.Option(..., prompt=True, help="Single command to send to all devices.")
):
    """Uses Netmiko to send a command to a list of devices. Prompts for list of devices and command,
    no need to use the Options.

    Devices:

        Devices should be input as a comma-separated list of devices. Each device should be formatted
    as {{ device }}|{{ type }}. Ex: router1|iosxr or router2|junos.

    Command:

        This command will be run against all devices. Note that only one command is supported, so
    don't mix device types.
    """
    device_list = devices.split(",")
    for counter, device in enumerate(device_list, 1):
        device.strip()
        device_name, device_type = device.split('|')

        if device_type == 'junos':
            device_type = 'juniper_junos'

        elif device_type == 'iosxr':
            device_type = 'cisco_xr'

        print(device_name, device_type)

        start_time = time.time()
        connection = netmiko_connect(device_type, device_name)

        print('\n', '-' * 20, device_name.upper(), '-' * 20, '\n')
        print(f"COMMAND: '{command}")
        print(connection.send_command(command), '\n\n')

        if counter != len(device):
            if start_time < (abs(time.time() - start_time)):
                time.sleep(30 - (time.time() - start_time))
            else:
                continue


if __name__ == "__main__":
    logins()
