from parse import ParseData, etree_to_dict
from login import Login
from ipchecks import GetNeighborIPs
from xr_hpr import XRGetHPR
import filters
import time
import sys


class Device:

    def __init__(self, username, device_name, device_type):

        self.username = username
        self.device_name = device_name
        self.device_type = device_type
        creds = Login(username, device_name, device_type)

        if device_type == 'iosxr':
            self.connection = creds.ncc_connect()

        elif device_type == 'junos':
            self.connection = creds.pyez_connect()
            self.connection.open()

        self.start_time = time.time()


class CircuitChecks(Device):

    def __init__(self, username, device_name, device_type, circuits_dict):
        super().__init__(username, device_name, device_type)
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
            self.adv_counts([ self.ipv4_circuit_data[1], self.ipv6_circuit_data[1] ])

            output_dict = {
                self.circuit: {
                    'Service': self.circuits_dict[self.circuit]['service'],
                    'IPv4 BGP Data': {
                        'IPv4 Neighbor': self.addresses[0],
                        'IPv4 Adv. Count': self.ipv4_adv_count,
                        'IPv4 Adv. Default?': self.ipv4_circuit_data[3],
                        'IPv4 Rx. Count': self.ipv4_circuit_data[2],
                        'IPv4 Rx. Prefixes': self.ipv4_circuit_data[0]
                    },
                    'IPv6 BGP Data': {
                        'IPv6 Neighbor': self.addresses[1],
                        'IPv6 Adv. Count': self.ipv6_adv_count,
                        'IPv6 Adv. Default?': self.ipv6_circuit_data[3],
                        'IPv6 Rx. Count': self.ipv6_circuit_data[2],
                        'IPv6 Rx. Prefixes': self.ipv6_circuit_data[0]
                    }
                }
            }
            circuits_output.update(output_dict)

        self.close_connections()

        return circuits_output, self.start_time

    def adv_counts(self, adv_counts):
        """Convert adv_count int to string for diffs - adv. counts fluctuate.

        Args:
            adv_counts (list): list of v4, v6 adv_count ints
        """

        for index, adv_count in enumerate(adv_counts):

            if not adv_count:
                if index == 0: self.ipv4_adv_count = 'No Adv. Routes'
                elif index == 1: self.ipv6_adv_count = 'No Adv. Routes'

            elif self.vrf == 'hpr':
                if adv_count > 20000:
                    if index == 0: self.ipv4_adv_count = 'Full HPR IPv4 Table'
                    elif index == 1: self.ipv6_adv_count = 'Full HPR IPv6 Table'
                elif adv_count > 0:
                    if index == 0: self.ipv4_adv_count = adv_count
                    elif index == 1: self.ipv6_adv_count = adv_count
                elif adv_count == 0:
                    if index == 0: self.ipv4_adv_count = 'No Adv. Routes'
                    elif index == 1: self.ipv6_adv_count = 'No Adv. Routes'

            elif self.vrf == 'default' or 'master':
                if adv_count > 800000 and index == 0: self.ipv4_adv_count = 'Full DC IPv4 Table'
                elif adv_count > 100000 and index == 1: self.ipv6_adv_count = 'Full DC IPv6 Table'
                elif adv_count > 0:
                    if index == 0: self.ipv4_adv_count = adv_count
                    elif index == 1: self.ipv6_adv_count = adv_count
                elif adv_count == 0:
                    if index == 0: self.ipv4_adv_count = 'No Adv. Routes'
                    elif index == 1: self.ipv6_adv_count = 'No Adv. Routes'

    def close_connections(self):

        #pylint: disable=no-member
        if self.device_type == 'iosxr':
            self.connection.close_session()

        elif self.device_type == 'junos':
            self.connection.close()

    def get_circuit_bgp(self):

        if self.device_type == 'iosxr':
            self.check_hpr_xr()
            self.get_circuit_bgp_xr()

        elif self.device_type == 'junos':
            self.get_circuit_bgp_junos()

    def check_hpr_xr(self):

        # pylint: disable=no-member
        self.vrf = 'default'
        try:
            xr_parse = ParseData(self.device_type)

            self.port = self.circuits_dict[self.circuit]['port']
            vrf = self.connection.get((filters.xr_vrf))
            self.vrf_iface_list = xr_parse.parse_vrf_iface_xr(vrf)

            for iface in self.vrf_iface_list:
                if str(iface) == str(self.port):
                    self.vrf = 'hpr'

        except: pass

    def get_circuit_bgp_xr(self):

        if self.vrf == 'hpr':
            elapsed_time = int(time.time() - self.start_time)
            self.ipv4_circuit_data,  self.ipv6_circuit_data, self.start_time = XRGetHPR(elapsed_time, self.username, self.device_name, self.addresses).get_xr_bgp_main()

        else:
            if self.addresses[0]: self.ipv4_circuit_data = self.circuit_bgp_xr(self.addresses[0])
            else: self.ipv4_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

            if self.addresses[1]: self.ipv6_circuit_data = self.circuit_bgp_xr(self.addresses[1])
            else: self.ipv6_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

    def circuit_bgp_xr(self, address):

        # pylint: disable=no-member
        if address == self.addresses[0]: version = 'ipv4'
        else: version = 'ipv6'

        xr_parse = ParseData(self.device_type)

        circuit_raw = self.connection.get((filters.bgp_routes_filter.format(version=version, neighbor=address)))
        default_raw = self.connection.get((filters.bgp_default_filter.format(version=version, neighbor=address)))

        circuit_bgp = xr_parse.parse_circuit_bgp_xr(circuit_raw)
        default = xr_parse.parse_circuit_default_xr(default_raw)

        return circuit_bgp[0], circuit_bgp[1], circuit_bgp[2], default

    def get_circuit_bgp_junos(self):

        if self.addresses[0]: self.ipv4_circuit_data = self.circuit_bgp_junos(self.addresses[0])
        else: self.ipv4_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

        if self.addresses[1]: self.ipv6_circuit_data = self.circuit_bgp_junos(self.addresses[1])
        else: self.ipv6_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

    def circuit_bgp_junos(self, address):

        junos_parse = ParseData(self.device_type)
        counts_raw = self.connection.rpc.get_bgp_neighbor_information(neighbor_address=address)
        adv_count, rx_count, self.vrf = junos_parse.parse_circuit_bgp_nei_junos(counts_raw)

        if address == self.addresses[0]:
            default = '0.0.0.0/0'
            if self.vrf == 'master': table = 'inet.0'
            elif self.vrf == 'hpr': table = 'hpr.inet.0'
        else:
            default = '::/0'
            if self.vrf == 'master': table = 'inet6.0'
            elif self.vrf == 'hpr': table = 'hpr.inet6.0'

        circuit_raw = self.connection.rpc.get_route_information(brief=True, table=table, peer=address, receive_protocol_name='bgp')
        routes_list = junos_parse.parse_circuit_bgp_junos_brief(circuit_raw)
        rx_routes = {}
        for route in routes_list:
            route_data = self.connection.rpc.get_route_information(destination=route, table=table, exact=True, detail=True, source_gateway=address)
            rx_routes.update(junos_parse.parse_circuit_bgp_junos(route_data))

        default_raw = self.connection.rpc.get_route_information(destination=default, exact=True, neighbor=address, advertising_protocol_name='bgp')
        default = junos_parse.parse_circuit_default_junos(default_raw)

        return rx_routes, adv_count, rx_count, default


class DeviceChecks(Device):

    def __init__(self, username, device_name, device_type):
        super().__init__(username, device_name, device_type)

    def get_device_main(self):
        """Main function call.

        Returns:
            dict: output dictionary
        """

        if self.device_type == 'junos':

            output_dict = self.get_device_junos()

        return output_dict

    def get_device_junos(self):
        """Use PyEZ to pull from Junos. Called from main class method

        Returns:
            dict: output dict
        """
        from pprint import pprint

        junos_parse = ParseData(self.device_type)

        software = etree_to_dict(self.connection.rpc.get_software_information())['software-information']['junos-version']
        power_raw = self.connection.rpc.get_power_usage_information_detail()
        bgp_raw = self.connection.rpc.get_bgp_summary_information()
        isis_raw = self.connection.rpc.get_isis_adjacency_information()
        msdp_raw = self.connection.rpc.get_msdp_information()
        pim_raw = self.connection.rpc.get_pim_neighbors_information()
        optics_raw = self.connection.rpc.get_interface_optics_diagnostics_information()
        iface_raw = self.connection.rpc.get_interface_information(detail=True, statistics=True)

        power = junos_parse.device_power_junos(power_raw)
        bgp = junos_parse.device_bgp_junos(bgp_raw)
        isis = junos_parse.device_isis_junos(isis_raw)
        msdp = junos_parse.device_msdp_junos(msdp_raw)
        pim = junos_parse.device_pim_junos(pim_raw)
        junos_parse.device_optics_junos(optics_raw)
        iface = junos_parse.device_iface_junos(iface_raw)

        vrfs = etree_to_dict(self.connection.rpc.get_instance_information(brief=True))
        vrf = None
        for i in vrfs['instance-information']['instance-core']:
            if i['instance-name'] == 'hpr':
                vrf = 'hpr'
                break

        if vrf == 'hpr':
            isis_hpr_raw = self.connection.rpc.get_isis_adjacency_information(instance='hpr')
            isis_hpr = junos_parse.device_isis_junos(isis_hpr_raw)
            isis.update(isis_hpr)

            msdp_hpr_raw = self.connection.rpc.get_msdp_information(instance='hpr')
            msdp_hpr = junos_parse.device_msdp_junos(msdp_hpr_raw)
            msdp.update(msdp_hpr)

            pim_hpr_raw = self.connection.rpc.get_pim_neighbors_information(instance='hpr')
            pim_hpr = junos_parse.device_pim_junos(pim_hpr_raw)
            pim.update(pim_hpr)

        self.connection.close()

        output_dict = {
            'Software': software,
            'Power': power,
            'IS-IS': isis,
            'PIM Enabled Ports': pim,
            'Established MSDP Neighbors': msdp,
            'Interfaces': iface,
            'Established BGP Neighbors': bgp
        }

        return output_dict