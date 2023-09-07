from typing import cast

import keyring
import pexpect
import pyotp
import pyperclip
import typer
from rich.prompt import Prompt

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


def print_account(args: tuple):
    for i in args:
        print(f"\t{i}")


def mfa_default():
    """Default user, pass, otp for MFA network logins."""
    mfa_user = keyring.get_password("cas", "user") + "mfa"
    first_factor = keyring.get_password("mfa", mfa_user)
    otp = pyotp.TOTP(keyring.get_password("otp", mfa_user))
    return mfa_user, first_factor, otp


def cas_creds() -> tuple[str, str]:
    username = cast(str, keyring.get_password("cas", "user"))
    password = cast(str, keyring.get_password("cas", username))
    return username, password


def get_yubikey() -> str:
    return Prompt.ask(
        "[green]Enter [white]Yubikey[/white] long press, [white]push[/white] (default) or [white]phone[/white]",
        password=True,
        default="push",
    )


def shell_login(
    username: str, first_factor: str, second_factor: pyotp.TOTP
) -> pexpect.spawn:
    shell_url = keyring.get_password("shell", "url")
    child = pexpect.spawn(
        f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no -p 22222 {username}@{shell_url}"'
    )

    child.expect("First Factor: ")
    child.sendline(first_factor)
    child.expect("Second Factor: ")
    child.sendline(second_factor.now())

    return child


@logins.command()
def coreadmin():
    password = keyring.get_password("desktop", "coreadmin")
    pyperclip.copy(password)
    print_account(
        (
            "Username: coreadmin",
            f"Password: {password} -- sent to clipboard\n",
        )
    )


@logins.command()
def get_mfa():
    mfa_user, password, otp = mfa_default()
    pyperclip.copy(password + otp.now())
    print_account(
        (
            f"Username: {mfa_user}",
            f"Password: {password + otp.now()} -- sent to clipboard\n",
        )
    )


@logins.command()
def get_cas():
    user, password = cas_creds()
    pyperclip.copy(password)
    print_account(
        (
            f"Username: {user}",
            f"Password: {password} -- sent to clipboard\n",
        )
    )


@logins.command()
def telnet(hostname: str = typer.Argument(..., help="Device hostname")):
    mfa_user, first_factor, otp = mfa_default()
    child = shell_login(mfa_user, first_factor, otp)

    username, cas_password = cas_creds()

    child.expect_exact(f"[{mfa_user}@shell ~]$")
    child.sendline(f"telnet {hostname}")
    child.expect("Username:")
    child.sendline(username)
    child.expect("assword:")
    child.sendline(cas_password + "," + get_yubikey())
    child.interact()


@logins.command()
def ssh(hostname: str = typer.Argument(..., help="Device hostname")):
    username, cas_password = cas_creds()

    child = pexpect.spawn(
        f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no {username}@{hostname}"'
    )
    child.expect([".*assword:.*", "Local password:"])
    child.sendline(cas_password + "," + get_yubikey())
    child.interact()


@logins.command()
def ssh_prompt(
    hostname: str = typer.Argument(..., help="Device hostname"),
    username: str = typer.Argument(..., help="Device Username"),
    password: str = typer.Argument(..., help="Device Password"),
):
    child = pexpect.spawn(
        f'/bin/bash -c "ssh -4 -o stricthostkeychecking=no {username}@{hostname}"'
    )
    child.expect([".*assword:.*", "Local password:"])
    child.sendline(password)
    child.interact()


if __name__ == "__main__":
    logins()
