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

    def get_location(self, serial: str) -> str:
        """Get location field from AMS for given serial number."""
        resp = requests.get(
            self.url,
            auth=self._auth,
            params={"serialnum": serial, "step": "SUBMIT"},
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        location = soup.find("strong", text=re.compile(r":"))

        try:
            return location.text
        except AttributeError:
            return "No Location Found"


if __name__ == "__main__":
    ams = AMS()
    with open("serials.txt", "r") as f:
        serials = f.read().split("\n")

    with open("serial_loc.csv", "w") as f:
        writer = csv.writer(f)
        for serial in serials:
            writer.writerow([serial, ams.get_location(serial)])
