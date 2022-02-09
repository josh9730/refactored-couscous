import re
import argparse
import pyotp
import keyring
from lastpass import Vault

from tools.utils import get_mfa_keyring


class GetLP:

    _shorthand = {
        "optical": bytes("Optical", "utf-8"),
        "enable": bytes("CENIC Enable Account", "utf-8"),
        "oob": bytes("CENIC Out-of-Band- OOB", "utf-8"),
        "cas": bytes("CAS", "utf-8"),
        "tacacs": bytes("CENIC TACACS Key", "utf-8"),
        "cll1": bytes("Cisco Learning Library #1", "utf-8"),
        "cll2": bytes("Cisco Learning Library #2", "utf-8"),
        "scilo_api": bytes("scilo api", "utf-8"),
    }

    def __init__(self):
        self.username, self.first_factor, self.otp = get_mfa_keyring('lp_pass', 'lp')
        # print(self.username, self.first_factor, self.otp)


    def get_lp(self, account):
        """Connect to Lastpass using API.

        Args:
            account (str): shorthand for the account, ex: 'optical' to reference the Optical account stored as bytes in Lastpass

        Returns:
            list: Username, password, and passthrough (OOB only)
        """

        name = self._shorthand[account]
        vault = Vault.open_remote(self.username, self.first_factor, self.otp.now())

        for i in vault.accounts:
            if i.name == name:

                if i.name == bytes("CENIC Out-of-Band- OOB", "utf-8"):
                    user_re = re.compile(r"Super User:\S+")
                    pass_re = re.compile(r"Password:\S+")
                    passthrough_re = re.compile(r"Passthrough:\S+")

                    lp_logon_url = str(i.url, "utf-8")
                    lp_logon_user = (
                        user_re.search(str(i.notes, "utf-8"))
                        .group()
                        .lstrip("Super User:")
                    )
                    lp_logon_pass = (
                        pass_re.search(str(i.notes, "utf-8"))
                        .group()
                        .lstrip("Password:")
                    )
                    lp_logon_passthrough = (
                        passthrough_re.search(str(i.notes, "utf-8"))
                        .group()
                        .lstrip("Passthrough:")
                    )

                else:
                    lp_logon_url = str(i.url, "utf-8")
                    lp_logon_user = str(i.username, "utf-8")
                    lp_logon_pass = str(i.password, "utf-8")
                    lp_logon_passthrough = ""

        return lp_logon_url, lp_logon_user, lp_logon_pass, lp_logon_passthrough


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve logins from LastPass.")
    parser.add_argument(
        "account",
        metavar="account",
        help=f"Account shortnames: {list(GetLP._shorthand)}",
        choices=list(GetLP._shorthand),
    )

    args = parser.parse_args()
    output = GetLP().get_lp(args.account)

    print("\n\tURL:\t\t", output[0])
    print("\tUsername:\t", output[1])
    print("\tPassword:\t", output[2])
    if output[3]:
        print("\tPassthrough:\t", output[3], "\n")
    else:
        print("\n")
