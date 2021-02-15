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
            self.connection.open()


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
                get_ips.get_ebgp_static_ips(self.device_type, self.connection)
            else:
                get_ips.get_ibgp_ips()

            self.addresses = [ self.circuits_dict[self.circuit]['ipv4_neighbor'], self.circuits_dict[self.circuit]['ipv6_neighbor']]
            output_dict = {}

            self.get_circuit_bgp()

            output_dict = {
                self.circuit: {
                    'Service': self.circuits_dict[self.circuit]['service'],
                    'IPv4 BGP Data': {
                        'IPv4 Neighbor': self.addresses[0],
                        'IPv4 Adv. Count': self.ipv4_circuit_bgp[0],
                        'IPv4 Adv. Default?': self.ipv4_default_bgp,
                        'IPv4 Rx. Count': self.ipv4_circuit_bgp[1],
                        'IPv4 Rx. Prefixes': self.ipv4_circuit_bgp[2]
                    },
                    'IPv6 BGP Data': {
                        'IPv6 Neighbor': self.addresses[1],
                        'IPv6 Adv. Count': self.ipv6_circuit_bgp[0],
                        'IPv6 Adv. Default?': self.ipv6_default_bgp,
                        'IPv6 Rx. Count': self.ipv6_circuit_bgp[1],
                        'IPv6 Rx. Prefixes': self.ipv6_circuit_bgp[2]
                    }
                }
            }
            circuits_output.update(output_dict)

        self.close_connection()
        return circuits_output

    def close_connection(self):

        #pylint: disable=no-member
        if self.device_type == 'iosxr':
            self.connection.close_session()
        elif self.device_type == 'junos':
            self.connection.close()

    def get_circuit_bgp(self):

        if self.device_type == 'iosxr':
            self.get_circuit_bgp_xr()

        elif self.device_type == 'junos':
            self.get_circuit_bgp_junos()


    def get_circuit_bgp_xr(self):

        #pylint: disable=no-member
        if self.addresses[0]:
            ipv4_circuit_raw = self.connection.get((filters.bgp_routes_filter.format(version='ipv4', neighbor=self.addresses[0])))
            ipv4_default_raw = self.connection.get((filters.bgp_default_filter.format(version='ipv4', neighbor=self.addresses[0])))

            self.ipv4_circuit_bgp = ParseData(ipv4_circuit_raw, self.device_type).parse_circuit_bgp_xr(version='ipv4')
            self.ipv4_default_bgp = ParseData(ipv4_default_raw, self.device_type).parse_circuit_default_xr(version='ipv4')
        else:
            self.ipv4_circuit_bgp = [ 'No Peering', 'No Peering', 'No Peering']
            self.ipv4_default_bgp = 'No Peering'

        if self.addresses[1]:
            ipv6_circuit_raw = self.connection.get((filters.bgp_routes_filter.format(version='ipv6', neighbor=self.addresses[1])))
            ipv6_default_raw = self.connection.get((filters.bgp_default_filter.format(version='ipv6', neighbor=self.addresses[1])))

            self.ipv6_circuit_bgp = ParseData(ipv6_circuit_raw, self.device_type).parse_circuit_bgp_xr(version='ipv6')
            self.ipv6_default_bgp = ParseData(ipv6_default_raw, self.device_type).parse_circuit_default_xr(version='ipv6')
        else:
            self.ipv6_circuit_bgp = [ 'No Peering', 'No Peering', 'No Peering']
            self.ipv6_default_bgp = 'No Peering'

    def get_circuit_bgp_junos(self):

        if self.addresses[0]:
            ipv4_counts_raw = self.connection.rpc.get_bgp_neighbor_information(neighbor_address=self.addresses[0])
            v4_adv_count, v4_rx_count, vrf = ParseData(ipv4_counts_raw, self.device_type).parse_circuit_bgp_nei_junos()

            if vrf == 'master':
                vrf = 'inet.0'
            elif vrf == 'hpr':
                vrf = 'hpr.inet.0'

            ipv4_circuit_raw = self.connection.rpc.get_route_information(extensive=True, table=vrf, peer=self.addresses[0], receive_protocol_name='bgp')
            ipv4_default_raw = self.connection.rpc.get_route_information(destination='0.0.0.0/0', exact=True, neighbor=self.addresses[0], advertising_protocol_name='bgp')

            self.ipv4_circuit_bgp = [ v4_adv_count, v4_rx_count, ParseData(ipv4_circuit_raw, self.device_type).parse_circuit_bgp_junos() ]
            self.ipv4_default_bgp = ParseData(ipv4_default_raw, self.device_type).parse_circuit_default_junos(default='0.0.0.0/0')

        else:
            self.ipv4_circuit_bgp = [ 'No Peering', 'No Peering', 'No Peering']
            self.ipv4_default_bgp = 'No Peering'

        if self.addresses[1]:
            ipv6_counts_raw = self.connection.rpc.get_bgp_neighbor_information(neighbor_address=self.addresses[1])
            v6_adv_count, v6_rx_count, vrf = ParseData(ipv6_counts_raw, self.device_type).parse_circuit_bgp_nei_junos()

            if vrf == 'master':
                vrf = 'inet6.0'
            elif vrf == 'hpr':
                vrf = 'hpr.inet6.0'

            ipv6_circuit_raw = self.connection.rpc.get_route_information(extensive=True, table=vrf, peer=self.addresses[1], receive_protocol_name='bgp')
            ipv6_default_raw = self.connection.rpc.get_route_information(destination='::/0', exact=True, neighbor=self.addresses[1], advertising_protocol_name='bgp')

            self.ipv6_circuit_bgp = [ v6_adv_count, v6_rx_count, ParseData(ipv6_circuit_raw, self.device_type).parse_circuit_bgp_junos() ]
            self.ipv6_default_bgp = ParseData(ipv6_default_raw, self.device_type).parse_circuit_default_junos(default='::/0')

        else:
            self.ipv6_circuit_bgp = [ 'No Peering', 'No Peering', 'No Peering']
            self.ipv6_default_bgp = 'No Peering'