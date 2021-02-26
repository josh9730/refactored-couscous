from parse import ParseData
from ipaddress import ip_address, IPv4Address, IPv6Address
import filters
import subprocess
import sys


def get_agg_v4(hostname):

    bashCmd = ['host', f'{hostname}']
    process = subprocess.Popen(bashCmd, stdout=subprocess.PIPE)
    output, error = process.communicate()

    if error: print(error)
    ipv4_nei = str(output,'utf-8').split('\n')[0].split()[3] # split string and select only the IPv4 address

    return ipv4_nei

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
                    print(f'\t\t\t* WARNING: No AAAA record for {self.hostname}.\n\t\t\tEnter manually if v6 Peering exists and re-run.')

            if not self.circuit['ipv4_neighbor']: self.circuit['ipv4_neighbor'] = ipv4_nei
            if not self.circuit['ipv6_neighbor']: self.circuit['ipv6_neighbor'] = ipv6_nei

    def get_ebgp_static_ips(self, device_type, connection):
        """Uses napalm to get assume neighbor IP from port configs. Typical standard is +1/+16 for peer.

        Args:
            connection: PyEZ or ncclient
        """

        if (not self.circuit['ipv4_neighbor'] or not self.circuit['ipv6_neighbor']) and self.circuit['port']:

            if device_type == 'junos':
                junos_parse = ParseData(device_type)

                arp = connection.rpc.get_arp_table_information(interface=self.circuit['port'])
                nd = connection.rpc.get_ipv6_nd_information(interface=self.circuit['port'])

                ipv4 = junos_parse.parse_circuit_arp_junos(arp)
                ipv6 = junos_parse.parse_circuit_nd_junos(nd)

            elif device_type == 'iosxr':
                xr_parse = ParseData(device_type)

                arp = connection.get((filters.arp.format(interface=self.circuit['port'])))
                nd = connection.get((filters.nd.format(interface=self.circuit['port'])))

                ipv4 = xr_parse.parse_circuit_arp_xr(arp)
                ipv6 = xr_parse.parse_circuit_nd_xr(nd)

            if not self.circuit['ipv4_neighbor']: self.circuit['ipv4_neighbor'] = ipv4
            if not self.circuit['ipv6_neighbor']: self.circuit['ipv6_neighbor'] = ipv6