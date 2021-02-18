from parse import ParseData
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
        creds = Login(username, device_name, device_type)

        if device_type == 'iosxr':
            self.connection = creds.ncc_connect()

        elif device_type == 'junos':
            self.connection = creds.pyez_connect()
            self.connection.open()

        self.start_time = time.time()


class CircuitChecks(Device):

    def __init__(self, username, device_name, device_type, circuits_dict):

        self.device_type = device_type
        self.device_name = device_name
        self.circuits_dict = circuits_dict
        super().__init__(username, self.device_name, self.device_type)

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
            self.port = self.circuits_dict[self.circuit]['port']
            vrf = self.connection.get((filters.xr_vrf))
            self.vrf_iface_list = ParseData(vrf, self.device_type).parse_vrf_iface_xr()

            for iface in self.vrf_iface_list:
                if str(iface) == str(self.port):
                    self.vrf = 'hpr'

        except: pass

    def get_circuit_bgp_xr(self):

        if self.vrf == 'hpr':
            elapsed_time = int(time.time() - self.start_time)
            self.ipv4_circuit_data,  self.ipv6_circuit_data, self.start_time = XRGetHPR(elapsed_time, self.username, self.device_name, self.addresses).get_xr_bgp_main()

        else:
            if self.addresses[0]:
                self.ipv4_circuit_data = self.circuit_bgp_xr(self.addresses[0])
            else:
                self.ipv4_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

            if self.addresses[1]:
                self.ipv6_circuit_data = self.circuit_bgp_xr(self.addresses[1])
            else:
                self.ipv6_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

    def circuit_bgp_xr(self, address):

        # pylint: disable=no-member
        if address == self.addresses[0]: version = 'ipv4'
        else: version = 'ipv6'

        circuit_raw = self.connection.get((filters.bgp_routes_filter.format(version=version, neighbor=address)))
        default_raw = self.connection.get((filters.bgp_default_filter.format(version=version, neighbor=address)))

        circuit_bgp = ParseData(circuit_raw, self.device_type).parse_circuit_bgp_xr(version=version)
        default = ParseData(default_raw, self.device_type).parse_circuit_default_xr(version=version)

        return circuit_bgp[0], circuit_bgp[1], circuit_bgp[2], default

    def get_circuit_bgp_junos(self):

        if self.addresses[0]:
            self.ipv4_circuit_data = self.circuit_bgp_junos(self.addresses[0])
        else:
            self.ipv4_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

        if self.addresses[1]:
            self.ipv6_circuit_data = self.circuit_bgp_junos(self.addresses[1])
        else:
            self.ipv6_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

    def circuit_bgp_junos(self, address):

        counts_raw = self.connection.rpc.get_bgp_neighbor_information(neighbor_address=address)
        adv_count, rx_count, vrf = ParseData(counts_raw, self.device_type).parse_circuit_bgp_nei_junos()

        if address == self.addresses[0]:
            default = '0.0.0.0/0'
            if vrf == 'master': table = 'inet.0'
            elif vrf == 'hpr': table = 'hpr.inet.0'
        else:
            default = '::/0'
            if vrf == 'master': table = 'inet6.0'
            elif vrf == 'hpr': table = 'hpr.inet6.0'

        self.vrf = vrf

        circuit_raw = self.connection.rpc.get_route_information(brief=True, table=table, peer=address, receive_protocol_name='bgp')
        routes_list = ParseData(circuit_raw, self.device_type).parse_circuit_bgp_brief()

        rx_routes = {}
        for route in routes_list:
            route_data = self.connection.rpc.get_route_information(destination=route, table=table, exact=True, detail=True, source_gateway=address)
            rx_routes.update(ParseData(route_data, self.device_type).parse_circuit_bgp_junos(route))

        default_raw = self.connection.rpc.get_route_information(destination=default, exact=True, neighbor=address, advertising_protocol_name='bgp')
        default = ParseData(default_raw, self.device_type).parse_circuit_default_junos(default=default)

        return rx_routes, adv_count, rx_count, default


class DeviceChecks(Device):

    def __init__(self, username, device_type, device_dict):

        self.username = username
        self.device_dict = device_dict
        self.device_type = device_type
        super().__init__(username, self.device_name, self.device_type)

    def get_device_main(self):
        """Main function call.

        Returns:
            dict: output dictionary
        """

        output_dict = {}
        for index, device in enumerate(self.device_dict, 1):
            start_time = time.time()

            for self.device, self.device_type in device.items():

                if self.device_type == 'junos':
                    try:
                        print(f'Connecting to {self.device}')
                        self.connection = Login(self.username, self.device, None).pyez_connect()
                        print(f'\t... Connected to {self.device} with PyEZ')
                        output_dict_1 = self.get_device_junos()
                    except:
                        print('\n\n\tAuthentication Error. Please wait and run again.\n\n')
                        sys.exit(1)

                elif self.device_type == 'iosxr':
                    try:
                        print(f'Connecting to {self.device}')
                        self.connection = Login(self.username, self.device, self.device_type).napalm_connect()
                        print(f'\t... Connected to {self.device} with napalm')
                        output_dict_1 = self.get_device_iosxr()
                    except:
                        print('\n\n\tAuthentication Error. Please wait and run again.\n\n')
                        sys.exit(1)

            output_dict.update(output_dict_1)

            elapsed_time = time.time() - start_time
            if int(elapsed_time) < 30 and index != len(self.device_dict):
                print(f'\t... resetting OTP ({int(30 - elapsed_time)} sec)')
                time.sleep(30 - elapsed_time)
                print('\t... done\n\n')

        return output_dict

    def get_device_junos(self):
        """Use PyEZ to pull from Junos. Called from main class function
        Returns:
            dict: output dict
        """

        self.connection.open()

        # parser = ParseData(self.device_type)

        software = self.connection.rpc.get_software_information()['software-information']['junos-version']
        power = ParseData(self.connection.rpc.get_power_usage_information_detail(), self.device_type).parse_device_power_junos()
        bgp = ParseData(self.connection.rpc.get_bgp_summary_information(), self.device_type).parse_device_bgp_junos()
        isis = ParseData(self.connection.rpc.get_isis_adjacency_information(), self.device_type).parse_device_isis_junos()
        msdp = ParseData(self.connection.rpc.get_msdp_information(), self.device_type).parse_device_msdp_junos()
        pim = ParseData(self.connection.rpc.get_pim_neighbors_information(), self.device_type).parse_device_pim_junos()
        optics = ParseData(self.connection.rpc.get_interface_optics_diagnostics_information(), self.device_type).parse_device_optics_junos()
        iface = ParseData(self.connection.rpc.get_interface_information(detail=True, statistics=True), self.device_type).parse_device_iface_junos(optics)

        vrfs = self.connection.rpc.get_instance_information(brief=True)
        vrf = None
        for i in vrfs['instance-information']['instance-core']:
            if i['instance-name'] == 'hpr':
                vrf = 'hpr'
                break

        if vrf == 'hpr':
            show_isis_hpr = self.connection.rpc.get_isis_adjacency_information(instance='hpr')
            isis_hpr = ParseData(show_isis_hpr, self.device_type).parse_isis_junos()
            isis.update(isis_hpr)

            show_msdp_hpr = self.connection.rpc.get_msdp_information(instance='hpr')
            msdp_hpr = ParseData(show_msdp_hpr, self.device_type).parse_msdp_junos()
            msdp.update(msdp_hpr)

            show_pim_hpr = self.connection.rpc.get_pim_neighbors_information(instance='hpr')
            pim_hpr = ParseData(show_pim_hpr, self.device_type).parse_pim_junos()
            pim.update(pim_hpr)

        self.connection.close()

        output_dict = {
            self.device.upper(): {
                'Software': software,
                'Power': power,
                'IS-IS': isis,
                'PIM Enabled Ports': pim,
                'Established MSDP Neighbors': msdp,
                'Interfaces': iface,
                'Established BGP Neighbors': bgp
            }
        }

        return output_dict