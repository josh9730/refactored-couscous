from parse import ParseData
from login import Login
from ipchecks import GetNeighborIPs
import filters


class Device:

    def __init__(self, username, device_name, device_type):


        creds = Login(username, device_name, device_type)

        if device_type == 'iosxr':
            self.connection = creds.ncc_connect()

        elif device_type == 'junos':
            self.connection = creds.pyez_connect()


class CircuitChecks(Device):

    def __init__(self, username, device_name, device_type, circuits_dict):
        self.device_type = device_type
        self.device_name = device_name
        super().__init__(username, self.device_name, self.device_type)

        self.circuits_dict = circuits_dict

    def get_circuit_main(self):

        circuits_output = {}
        for self.circuit in self.circuits_dict:

            get_ips = GetNeighborIPs(self.circuits_dict[self.circuit], self.circuit)

            if self.circuits_dict[self.circuit]['service'] == ('ebgp' or 'static'):
                get_ips.get_ebgp_static_ips(self.connection)
            else:
                get_ips.get_ibgp_ips()

            self.addresses = [ self.circuits_dict[self.circuit]['ipv4_neighbor'], self.circuits_dict[self.circuit]['ipv6_neighbor']]

            output_dict = {}

            self.get_circuit_bgp_nlri()

            output_dict = {
                self.circuit: {
                    'Service': self.circuits_dict[self.circuit]['service'],
                    'IPv4 Neighbor': self.addresses[0],
                    'IPv6 Neighbor': self.addresses[1],
                    'IPv4 Adv. Count': self.ipv4_circuit_bgp[0],
                    'IPv4 Adv. Default?': self.ipv4_default_bgp,
                    'IPv6 Adv. Count': self.ipv6_circuit_bgp[0],
                    'IPv6 Adv. Default?': self.ipv6_default_bgp,
                    'IPv4 Prefixes': self.ipv4_circuit_bgp[1],
                    'IPv6 Prefixes': self.ipv6_circuit_bgp[1]
                }
            }
            circuits_output.update(output_dict)

        return circuits_output

    def get_circuit_bgp_nlri(self):

        if self.device_type == 'iosxr':
            output_raw = self.get_circuit_bgp_nlri_xr()

            self.ipv4_circuit_bgp = ParseData(output_raw[0], self.device_type).parse_circuit_bgp_xr(version='ipv4')
            self.ipv4_default_bgp = ParseData(output_raw[1], self.device_type).parse_circuit_default_xr(version='ipv4')

            self.ipv6_circuit_bgp = ParseData(output_raw[2], self.device_type).parse_circuit_bgp_xr(version='ipv6')
            self.ipv6_default_bgp = ParseData(output_raw[3], self.device_type).parse_circuit_default_xr(version='ipv6')

        # elif self.device_type == 'junos':


    def get_circuit_bgp_nlri_xr(self):

        #pylint: disable=no-member
        ipv4_circuit_raw = self.connection.get((filters.bgp_routes_filter.format(version='ipv4', neighbor=self.addresses[0])))
        ipv4_default_raw = self.connection.get((filters.bgp_default_filter.format(version='ipv4', neighbor=self.addresses[0])))

        ipv6_circuit_raw = self.connection.get((filters.bgp_routes_filter.format(version='ipv6', neighbor=self.addresses[1])))
        ipv6_default_raw = self.connection.get((filters.bgp_default_filter.format(version='ipv6', neighbor=self.addresses[1])))

        return ipv4_circuit_raw, ipv4_default_raw, ipv6_circuit_raw, ipv6_default_raw
