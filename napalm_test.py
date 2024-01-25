import keyring
from napalm import get_network_driver
from rich import print
from rich.prompt import Prompt

"""
- pip3 install keyring
- pip3 install rich
- pip3 install napalm

Keyring config:
- keyring set cas user
    enter USERNAME at prompt
- keyring set cas USERNAME
    - enter CAS password at prompt
    
you can also input the backdoor credentials for the lab-mx204s into keyring (keyring uses Mac keychain, which is encrypted)
and change the get_password() calls accordingly, so you don't have to be prompted.
"""


def get_token() -> str:
    return Prompt.ask(
        "[green]Enter [white]Yubikey[/white] long press, [white]push[/white] (default) or [white]phone[/white].",
        password=True,
        default="push",
    )


def cas_creds() -> tuple[str, str]:
    username = keyring.get_password("cas", "user")
    password = keyring.get_password("cas", username)
    return username, password


def main(devices: list[str]) -> None:
    username, cas_password = cas_creds()

    outputs = []
    driver = get_network_driver("junos")
    for device in devices:
        password = cas_password + "," + get_token()
        with driver(device, username=username, password=password) as napalm_dev:
            outputs.append(napalm_dev.get_facts())

    print(outputs)


if __name__ == "__main__":
    devices = ["lab-mx204-1", "lab-mx204-2"]
    main(devices)
