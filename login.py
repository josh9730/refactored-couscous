import re
import socket
import time
from enum import Enum
from typing import cast

import keyring
import pexpect
import pyotp
import pyperclip
import typer
from lastpass import Vault
from netmiko import ConnectHandler

logins = typer.Typer(
    help="""
Multi-function login helper. Can return Lastpass accounts,
SSH/Telnet to devices via MFA, Backdoor, or CAS accounts, or
send Netmiko commands to a list of devices.

\b
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
    def __new__(cls, value, full_name):
        """Enum value is used for Typer options, but LastPass names are too
        inconvenient to type. Added a full_name attribute here."""
        obj = str.__new__(cls, [value])
        obj._value_ = value
        obj.full_name = full_name
        return obj

    # optical = ("optical", "Optical")  # no longer used, Duo
    enable = ("enable", "CENIC Enable Account")
    oob = ("oob", "CENIC Out-of-Band- OOB")
    tacacs = ("tacacs", "CENIC TACACS Key")
    snmp = ("snmp", "ScienceLogic SNMP Credentials")
    core_eng = ("core-eng", "lists.cenic.org - core-eng Admin")
    core_ext = ("core-ext", "lists.cenic.org - core-ext Admin")
    eve_ng = ("eve-ng", "EVE-NG Admin")
    duo_optical = ("optical", "CENIC Optical user/PW - Duo Migration ")
    duo_optical_tacacs = ("duo-optical-tacacs", "CENIC Optical TACACS Key")


def get_lp(account: Enum, passthrough: bool = False):
    """Return account info for supplied LastPass account name.

    Additional accounts can be added by updating LPChoices Enum.

    passthrough: account will be passed-through to a login script
                 rather than printed to screen. Strips formatting
                 and returns only the username and password.
    """

    cas_email = cast(str, keyring.get_password("cas", "email"))
    lp_pass = cast(str, keyring.get_password("lp_pass", cas_email))
    lp_otp = pyotp.TOTP(cast(str, keyring.get_password("lp_pass", "otp")))

    name = bytes(account.full_name, "utf-8")  # type: ignore -- custom __new__ for Enum

    vault = Vault.open_remote(cas_email, lp_pass, lp_otp.now())

    for lp_account in vault.accounts:
        # print(lp_account.name)
        if lp_account.name == name:
            if account.value == "snmp" or account.value == "oob":
                if account.value == "snmp":
                    user_re = re.compile(r"Username: \S+").search(
                        str(lp_account.notes, "utf-8")
                    )
                    auth_re = re.compile(r"Auth Password: \S+").search(
                        str(lp_account.notes, "utf-8")
                    )
                    priv_re = re.compile(r"Priv Password: \S+").search(
                        str(lp_account.notes, "utf-8")
                    )
                else:
                    user_re = re.compile(r"Super User: \S+").search(
                        str(lp_account.notes, "utf-8")
                    )
                    auth_re = re.compile(r"Password: \S+").search(
                        str(lp_account.notes, "utf-8")
                    )
                    priv_re = re.compile(r"Passthrough: \S+").search(
                        str(lp_account.notes, "utf-8")
                    )

                # can't use all() to suppress mypy
                assert user_re
                assert auth_re
                assert priv_re

                lp_username = user_re.group()
                lp_password = auth_re.group()
                lp_password2 = priv_re.group()

            else:
                password = str(lp_account.password, "utf-8")
                username = str(lp_account.username, "utf-8")
                if passthrough:
                    return username, password
                else:
                    pyperclip.copy(password)
                    lp_username = f"Username: {username}"
                    lp_password = f"Password: {password} -- sent to clipboard"
                    lp_password2 = ""

    return lp_username, lp_password, lp_password2


def netmiko_connect(device_type: str, device_name: str):
    mfa_user, first_factor, otp = mfa_default()
    return ConnectHandler(
        device_type=device_type,
        ip=socket.gethostbyname(device_name),
        username=mfa_user,
        password=first_factor + otp.now(),
    )


def mfa_default():
    """Default user, pass, otp for MFA network logins."""
    mfa_user = keyring.get_password("cas", "user") + "mfa"
    first_factor = keyring.get_password("mfa", mfa_user)
    otp = pyotp.TOTP(keyring.get_password("otp", mfa_user))
    return mfa_user, first_factor, otp


def ssh_default(hostname: str, username: str, password: str):
    """Default actions for SSH. Returns CLI prompt."""
    child = pexpect.spawn(
        f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no {username}@{hostname} | ct"'
    )
    child.expect(["assword:", "Local password:"])
    child.sendline(password)
    child.interact()


def telnet_default(hostname: str, username: str, password: str):
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
    username, password, *args = get_lp(LPChoices("enable"), passthrough=True)
    ssh_default(hostname, username, password)


@logins.command()
def cas(hostname: str = typer.Argument(..., help="Device hostname")):
    """Use CAS account to login to non-network devices with ssh."""
    username = cast(str, keyring.get_password("cas", "user"))
    password = cast(str, keyring.get_password("cas", username))
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
    username, password, *args = get_lp(LPChoices("enable"), passthrough=True)
    telnet_default(hostname, username, password)


@logins.command()
def get_mfa():
    mfa_user, password, otp = mfa_default()
    pyperclip.copy(password + otp.now())
    print_account(
        [
            f"Username: {mfa_user}",
            f"Password: {password+otp.now()} -- sent to clipboard\n",
        ]
    )


@logins.command()
def get_cas():
    user = keyring.get_password("cas", "user")
    password = keyring.get_password("cas", "password")
    pyperclip.copy(password)
    print_account(
        [
            f"Username: {user}",
            f"Password: {password} -- sent to clipboard\n",
        ]
    )


def print_account(args: list):
    for i in args:
        print(f"\t{i}")


@logins.command()
def lpass(
    account: LPChoices = typer.Argument(..., case_sensitive=False, help="Account")
):
    """Return LastPass username, password, URL, and optionally Passthrough pass from LastPass.

    Account name is case-insensitive.
    """
    print_account(get_lp(account))


@logins.command()
def netmiko_pull(
    devices: str = typer.Option(
        ..., prompt=True, help="Comma-separated string of devices & device types"
    ),
    command: str = typer.Option(
        ..., prompt=True, help="Single command to send to all devices."
    ),
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

        device = device.strip()
        device_name, device_type = device.split("|")

        if device_type == "junos":
            device_type = "juniper_junos"

        elif device_type == "iosxr":
            device_type = "cisco_xr"

        start_time = time.time()
        connection = netmiko_connect(device_type, device_name)

        print("\n", "-" * 20, device_name.upper(), "-" * 20, "\n")
        print(f"COMMAND: '{command}")
        print(connection.send_command(command), "\n\n")

        if counter != len(device_list):
            now = time.time()
            if 30 > now - start_time:
                sleep_time = 30 - (int(now - start_time))
                print(f"Resetting OTP, sleep for {sleep_time}s.")
                time.sleep(sleep_time)


if __name__ == "__main__":
    logins()
