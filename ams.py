import csv
import re

import requests
import keyring
from bs4 import BeautifulSoup
from datetime import datetime


def normalize_datetime(date: str) -> str:
    """Output isoformatted datetime from DD-Month-YYYY

    Ex:
        01-May-2008 -> 2008-05-01
    """
    try:
        return datetime.strptime(date, "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return date


class AMS:
    user = keyring.get_password("cas", "user")
    password = keyring.get_password("cas", "password")
    url = keyring.get_password("ams", "url")
    _auth = (user, password)

    def __init__(self):
        self.soup = None

    def _get_location(self) -> str:
        """Get location field from AMS for given serial number."""
        location = self.soup.find("a", href=re.compile(r"(location)"))

        try:
            return location.next_element.text.split("(")[0].strip()
        except AttributeError:
            return "No Location found"

    def _get_segment(self):
        """Return AMS project from serial."""
        project = self.soup.find("td", text="project")

        try:
            return project.find_next_sibling("td").text
        except AttributeError:
            return "No Segment found"

    def _get_host(self):
        """Return hostname from serial."""
        host = self.soup.find("td", text="host info")

        try:
            return host.find_next_sibling("td").next_element.text.strip()
        except AttributeError:
            return "No Hostname found"

    def _get_po(self):
        """Return Purchase Order from serial."""
        po_elem = self.soup.find("td", text="purchase order")
        po = po_elem.find_next_sibling("td").find("strong")

        try:
            return po.text
        except AttributeError:
            return "No PO found"

    def _get_receive_date(self):
        """Return asset Receive Date from serial."""
        rx_date_elem = self.soup.find("td", text="status")
        rx_date = rx_date_elem.find_next_sibling("td").find("br")

        try:
            rx_date = rx_date.next_element
        except AttributeError:
            return "No Receive Date Found"
        else:
            return normalize_datetime(rx_date.split()[-1])

    def get_serial_info(
        self,
        serial: str,
        location: bool = True,
        segment: bool = True,
        host: bool = True,
        po: bool = True,
        ams: bool = True,
    ) -> list:
        """Return list of data for given serial."""
        serial_info = [serial]

        resp = requests.get(
            self.url,
            auth=self._auth,
            params={"serialnum": serial, "step": "SUBMIT"},
        )
        self.soup = BeautifulSoup(resp.text, "html.parser")

        if location:
            serial_info.append(self._get_location())
        if segment:
            serial_info.append(self._get_segment())
        if host:
            serial_info.append(self._get_host())
        if po:
            serial_info.append(self._get_po())
        if ams:
            serial_info.append(self._get_receive_date())

        return serial_info


def main():
    ams = AMS()
    with open("serials.txt", "r") as f:
        serials = f.read().split("\n")

    with open("serial_loc.csv", "w") as f:
        writer = csv.writer(f)
        for serial in serials:
            writer.writerow(ams.get_serial_info(serial))


if __name__ == "__main__":
    main()
