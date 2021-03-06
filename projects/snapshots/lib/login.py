from napalm.base import get_network_driver
from netmiko import ConnectHandler
from jnpr.junos import Device
from ncclient import manager
from atlassian import Jira
import keyring
import pyotp


class Login:

    def __init__(self, username, hostname, device_type):
        """Connection parameters, initialize with open() & close()

        Args:
            username (str): username for keyring / mfa
            hostname (str): hostname to login to
            device_type (str): device of hostname (junos/iosxr)
        """

        self.username = username
        self.device_type = device_type
        self.hostname = hostname
        self.first_factor = keyring.get_password("mfa", username)
        self.otp = pyotp.TOTP(keyring.get_password("otp", username))

    def jira_login(self):
        """Connects to Jira. Requires CAS password"""

        password = keyring.get_password("cas", self.username)
        jira = Jira(
            url = 'https://servicedesk.cenic.org',
            username = self.username,
            password = password)

        return jira

    def napalm_connect(self):
        """Method for napalm connections. Returns the connection parameters

        Returns:
            connection: Napalm connection. must still be initialized
        """

        driver = get_network_driver(self.device_type)
        connection = driver(
            hostname = self.hostname,
            username = self.username,
            password = self.first_factor + self.otp.now())

        return connection

    def netmiko_connect(self):
        """Method for netmiko connections. Returns the connection parameters

        Returns:
            connection: Netmiko connection. Must still be initialized
        """

        connection = ConnectHandler(
            device_type = self.device_type,
            host = self.hostname,
            username = self.username,
            password = self.first_factor + self.otp.now())

        return connection

    def pyez_connect(self):
        """Method for Junos PyEZ connections. Returns the connection parameters. Junos only.

        Returns:
            connection: PyEZ connection. Must still be initialized
        """

        connection = Device(
            host = self.hostname,
            user = self.username,
            passwd = self.first_factor + self.otp.now())

        return connection

    def ncc_connect(self):
        """Method for NCClient connections. Returns the connection parameters. Currently only used by XR.

        Returns:
            connection: NCClient connection. Must close.
        """

        connection = manager.connect(
            host = self.hostname,
            username = self.username,
            password = self.first_factor + self.otp.now(),
            timeout=120,
            hostkey_verify=False)

        return connection