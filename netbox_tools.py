import csv

import keyring
import pynetbox
import requests


def get_auth():
    url = keyring.get_password("netbox", "url")
    api_key = keyring.get_password("netbox", "api")
    return url, api_key


def get_pynb():
    url, api_key = get_auth()
    return pynetbox.api(url, token=api_key)


def post_asns():
    url, api_key = get_auth()
    url = url + "/api/"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }

    with open("asns.csv", "r") as f:
        """Import list of ASNs to NetBox and add to Site.

        - pynetbox does not support adding individual ASNs, used requests instead
        - NetBox does not allow adding sites during a CSV import
        asns: asn in col1, list of sites in col2
        """
        asns = csv.reader(f)
        for asn in asns:
            try:
                # post ASN
                asn_data = {"asn": asn[0], "rir": 1}
                asn_response = requests.post(url + "ipam/asns/", json=asn_data, headers=headers)
                asn_response.raise_for_status()
                asn_id = asn_response.json()["id"]

                # iterate over sites and add ASN to the Site object
                for site in asn[1].split(", "):
                    get_site = requests.get(url + f"dcim/sites/?slug={site.lower()}", headers=headers)
                    get_site.raise_for_status()
                    site_id = get_site.json()["results"][0]["id"]

                    site_data = {"asns": [asn_id]}
                    site_response = requests.patch(url + f"dcim/sites/{site_id}/", json=site_data, headers=headers)
                    site_response.raise_for_status()

            except (requests.HTTPError, IndexError):
                print("failed: ", asn[0])


if __name__ == "__main__":
    post_asns()
