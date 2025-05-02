"""
Tool to scrape important data for a given serial number. Input is a text file, outputs as csv.
"""

import csv
import re
import time
from datetime import datetime

import keyring
import requests
from bs4 import BeautifulSoup


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
        self.po_elem = None

    def _get_model(self) -> str:
        """Get model type from AMS for given serial."""
        model = self.soup.find("a", href=re.compile(r"(field=part)"))

        if model:
            return model.find("strong").text
        return "No Model Found"

    def _get_location(self) -> str:
        """Get location field from AMS for given serial number."""
        location = self.soup.find("a", href=re.compile(r"(location)"))

        if location:
            return location.next_element.text.split("(")[0].strip()
        return "No Location found"

    def _get_segment(self) -> str:
        """Return AMS project from serial."""
        project = self.soup.find("td", string="project")

        if project:
            return project.find_next_sibling("td").text
        return "No Segment found"

    def _get_host(self) -> str:
        """Return hostname from serial."""
        host = self.soup.find("td", string="host info")

        if host:
            return host.find_next_sibling("td").next_element.text.strip()
        return "No Hostname found"

    def _get_po(self) -> str:
        """Return Purchase Order from serial."""
        self.po_elem = self.soup.find("td", string="purchase order")
        po = self.po_elem.find_next_sibling("td").find("strong")

        if po:
            return po.text
        return "No PO found"

    def _get_ticket(self) -> str:
        """Return Purchase Ticket if present."""
        next_element = self.po_elem.find_next_sibling("td")
        ticket_elem = next_element.find("a", href=re.compile(r"(servicedesk)"))

        if ticket_elem:
            ticket = ticket_elem.text.split()[-1]
            if ticket[0].isdigit():
                ticket = "NOC-" + ticket
            return ticket
        return "No Ticket Found"

    def _get_receive_date(self) -> str:
        """Return asset Receive Date from serial."""
        rx_date_elem = self.soup.find("td", string="status")
        rx_date = rx_date_elem.find_next_sibling("td").find("br")

        if rx_date_elem:
            rx_date = rx_date.next_element
            return normalize_datetime(rx_date.split()[-1])
        return "No Receive Date Found"

    def _get_status(self) -> str:
        """Return In-Service Date if present, else return status."""
        status_elem = self.soup.find("td", string="status")
        if status_elem:
            status = status_elem.find_next_sibling("td").find("strong").text.strip()

            if status == "IN-SERVICE":
                in_service_date = (
                    status_elem.find_next_sibling("td").find("br").next_element.next_element.text.split()[-1]
                )
                return normalize_datetime(in_service_date)
            return status
        return ""

    def get_serial_info(
        self,
        serial: str,
        model: bool = True,
        location: bool = True,
        segment: bool = True,
        host: bool = True,
        po: bool = True,
        po_ticket: bool = True,
        rx_date: bool = True,
        status: bool = True,
    ) -> list:
        """Return list of data for given serial."""
        serial_info = [serial]

        resp = requests.get(
            self.url,
            auth=self._auth,
            params={"serialnum": serial, "step": "SUBMIT"},
            timeout=30,
        )
        self.soup = BeautifulSoup(resp.text, "html.parser")

        print(self.soup)

        # if serial number not found, skip
        if self.soup.find(string=" No matching assets found "):
            return serial_info

        if model:
            serial_info.append(self._get_model())
        if location:
            serial_info.append(self._get_location())
        if segment:
            serial_info.append(self._get_segment())
        if host:
            serial_info.append(self._get_host())
        if po:
            serial_info.append(self._get_po())
        if po_ticket:
            serial_info.append(self._get_ticket())
        if rx_date:
            serial_info.append(self._get_receive_date())
        if status:
            serial_info.append(self._get_status())

        return serial_info

    @staticmethod
    def make_header() -> list[str]:
        return [
            "SERIAL",
            "MODEL",
            "LOCATION",
            "SEGMENT",
            "HOSTNAME",
            "CENIC PO",
            "PO TICKET",
            "RECEIVE DATE",
            "IN-SERVICE STATUS",
        ]


def main(input_file: str = "serials.txt"):
    """Expects input_file to be single serial per-line text file, ex:
        1234
        5678

    Ouputs csv with the following by default:
        serial, location, segment, hostname, purchase_order, rx_date
    """
    ams = AMS()
    with open(input_file, "r", encoding="UTF-8") as f:
        serials = f.read().splitlines()

    with open("serial_loc.csv", "w", encoding="UTF-8") as f:
        writer = csv.writer(f)
        writer.writerow(ams.make_header())
        for serial in serials:
            writer.writerow(ams.get_serial_info(serial))
            time.sleep(1)


if __name__ == "__main__":
    main()
