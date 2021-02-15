from parse import etree_to_dict
from ipaddress import ip_address
import subprocess
import sys

class IPChecks:

    def __init__(self, circuit):
        """Checks if manually input IPs are valid. Create IPv4/IPv6 Neighbor key/values pairs if not present.

        Args:
            circuit (dict): Contains IPs, device types, service, port strings.
        """

        self.circuit = circuit

        try:
            if self.circuit['ipv4_neighbor']:
                ipv4_nei = self.circuit['ipv4_neighbor']
                try:
                    ip_address(ipv4_nei)
                except:
                    print(f'\nERROR: {ipv4_nei} is invalid. Enter a valid IPv4 address and re-run.')
                    sys.exit(1)
        except:
            self.circuit['ipv4_neighbor'] = None

        try:
            if self.circuit['ipv6_neighbor']:
                ipv6_nei = self.circuit['ipv6_neighbor']
                try:
                    ip_address(ipv6_nei)
                except:
                    print(f'\nERROR: {ipv6_nei} is invalid. Enter a valid IPv6 address and re-run.')
                    sys.exit(1)
        except:
            self.circuit['ipv6_neighbor'] = None


class GetNeighborIPs(IPChecks):
    """
    Args:
        IPChecks (class): Checks manually input addresses are valid. Creates ipv4-ipv6 key/value pairs if not present.
    """

    def __init__(self, circuit, hostname):
        """Get Neighbor IPs - Loopbacks if iBGP or neighbor IPs from port configs if eBGP.
        Args:
            circuit (dict): Contains IPs, device types, service, port strings.
            hostname (str): Hostname to return errors
        """

        super().__init__(circuit)
        self.ipv4_nei = self.circuit['ipv4_neighbor']
        self.ipv6_nei = self.circuit['ipv6_neighbor']
        self.hostname = hostname
        print(f'Getting {self.hostname} neighbor IPs...')

    def get_ibgp_ips(self):
        """Use DNS to retrieve loopback IPs. Prints error if no IPv6.
        """

        if not self.circuit['ipv4_neighbor'] or not self.circuit['ipv6_neighbor']:

            bashCmd = ['host', f'{self.hostname}'] # run 'host {{ DNS name }}
            process = subprocess.Popen(bashCmd, stdout=subprocess.PIPE)
            output, error = process.communicate()

            if error: print(error)
            ipv4_nei = str(output,'utf-8').split('\n')[0].split()[3] # split string and select only the IPv4 address
            try:
                self.circuit['ipv6_neighbor'] = str(output,'utf-8').split('\n')[1].split()[4] # split string and select only the IPv6 address
            except:
                ipv6_nei = None
                if not self.circuit['ipv6_neighbor']:
                    print(f'* WARNING: No AAAA record for {self.hostname}. Enter manually if v6 Peering exists and re-run.')

            if not self.circuit['ipv4_neighbor']: self.circuit['ipv4_neighbor'] = ipv4_nei
            if not self.circuit['ipv6_neighbor']: self.circuit['ipv6_neighbor'] = ipv6_nei

    def get_ebgp_static_ips(self, device_type, connection):
        """Uses napalm to get assume neighbor IP from port configs. Typical standard is +1/+16 for peer.

        Args:
            connection: napalm
        """

        if (not self.circuit['ipv4_neighbor'] or not self.circuit['ipv6_neighbor']) and self.circuit['port']:
            from pprint import pprint
            if device_type == 'junos':
                arp = etree_to_dict(connection.rpc.get_arp_table_information(interface=self.circuit['port']))
                nd = etree_to_dict(connection.rpc.get_ipv6_nd_information(interface=self.circuit['port']))

                addresses = self.parse_circuit_iface_junos(arp, nd)

            if not self.circuit['ipv4_neighbor']: self.circuit['ipv4_neighbor'] = addresses[0]
            if not self.circuit['ipv6_neighbor']: self.circuit['ipv6_neighbor'] = addresses[1]

    def parse_circuit_iface_junos(self, arp, nd):

        try:
            ipv4 = arp['arp-table-information']['arp-table-entry']['ip-address']
        except:
            ipv4 = None

        try:
            ipv6 = nd['ipv6-nd-information']['ipv6-nd-entry'][0]['ipv6-nd-neighbor-address']
        except:
            ipv6 = None

        return ipv4, ipv6