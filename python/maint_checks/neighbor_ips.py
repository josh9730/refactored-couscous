from ipaddress import ip_address, IPv4Address, IPv6Address
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
                    print(f'\n{ipv4_nei} is invalid. Enter a valid IPv4 address.\n')
                    sys.exit(1)
        except:
            self.circuit['ipv4_neighbor'] = None

        try:
            if self.circuit['ipv6_neighbor']:
                ipv6_nei = self.circuit['ipv6_neighbor']
                try:
                    ip_address(ipv6_nei)
                except:
                    print(f'\n{ipv6_nei} is invalid. Enter a valid IPv6 address.\n')
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
        print(f'Fetching {self.hostname} neighbor IPs...')

    def get_ibgp_ips(self):
        """Use DNS to retrieve loopback IPs. Prints error if no IPv6.
        """

        bashCmd = ['host', f'{self.hostname}'] # run 'host {{ DNS name }}
        process = subprocess.Popen(bashCmd, stdout=subprocess.PIPE)
        output, error = process.communicate()

        if error: print(error)
        ipv4_nei = str(output,'utf-8').split('\n')[0].split()[3] # split string and select only the IPv4 address
        try:
            self.circuit['ipv6_neighbor'] = str(output,'utf-8').split('\n')[1].split()[4] # split string and select only the IPv6 address
        except:
            ipv6_nei = None
            print(f'=== No AAAA record for {self.hostname}. Check if an IPv6 iBGP peering and enter manually. ===')

        print('finished with IPs')

        if not self.circuit['ipv4_neighbor']: self.circuit['ipv4_neighbor'] = ipv4_nei
        if not self.circuit['ipv6_neighbor']: self.circuit['ipv6_neighbor'] = ipv6_nei

    def get_ebgp_ips(self, connection):
        """Uses napalm to get assume neighbor IP from port configs. Typical standard is +1/+16 for peer.

        Args:
            connection: napalm
        """

        self.connection = connection

        if not self.ipv4_nei and not self.ipv6_nei:
            try:
                self.port = self.circuit['port']
            except:
                print(f'=== Provide either Port or IPv4/v6 information for {self.hostname}. ===')
                sys.exit(1)

        ips = self.connection.get_interfaces_ip()[self.port]

        for i in ips['ipv4']:
            ipv4_nei = str(IPv4Address(i) + 1) # adds 1 to v4 address to get neighbor IP, converts to string

        try:
            ipv6 = next(iter(ips['ipv6'])) # select global unicast, not link local
            ipv6_nei = str(IPv6Address(ipv6) + 16) # adds 16 to v6 address to get neighbor IP, converts to string
        except:
            ipv6_nei = None
            print(f'=== No IPv6 address configured on {self.port} ===')

        print('finished with IPs')

        if not self.circuit['ipv4_neighbor']: self.circuit['ipv4_neighbor'] = ipv4_nei
        if not self.circuit['ipv6_neighbor']: self.circuit['ipv6_neighbor'] = ipv6_nei