import csv
import re

import requests
import keyring
from bs4 import BeautifulSoup


class AMS:
    user = keyring.get_password("cas", "user")
    password = keyring.get_password("cas", "password")
    url = keyring.get_password("ams", "url")
    _auth = (user, password)

    def __init__(self):
        self.soup = None

    def _get_location(self) -> str:
        """Get location field from AMS for given serial number."""

        # ex. Los Angeles (WilTel:LSANCA1W:Los Angeles County)
        location = self.soup.find("strong", text=re.compile(r":"))

        try:
            return location.text.split("(")[0]
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
            return host.find_next_sibling("td").next_element.text
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

    def get_serial_info(
        self,
        serial: str,
        location: bool = True,
        segment: bool = True,
        host: bool = True,
        po: bool = True,
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
