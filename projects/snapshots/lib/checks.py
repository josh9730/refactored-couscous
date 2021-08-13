from .parse import ParseData, etree_to_dict
from .login import Login
from .ipchecks import GetNeighborIPs, get_agg_v4
from .napalm_xr import NapalmXR
from . import filters
import time
import sys


class Device:

    def __init__(self, username, device_name, device_type):
        """Device login parameters

        Args:
            username (str): mfa username
            device_name (str): device for the circuit
            device_type (str): device type (iosxr or junos)
        """

        self.username = username
        self.device_name = device_name
        self.device_type = device_type
        creds = Login(username, device_name, device_type)

        try:
            if device_type == 'iosxr':
                self.connection = creds.ncc_connect()
            elif device_type == 'junos':
                self.connection = creds.pyez_connect()
                self.connection.open()
        except:
            print('\n\n\tAuthentication Error. Please wait and run again.\n\n')
            sys.exit(1)

        self.start_time = time.time()

    def close_connections(self):

        #pylint: disable=no-member
        if self.device_type == 'iosxr':
            self.connection.close_session()

        elif self.device_type == 'junos':
            self.connection.close()


class CircuitChecks(Device):

    def __init__(self, username, device_name, device_type, circuits_dict):
        """Return circuit-based pre/post maintenance checks.

        Args:
            username (str): mfa username
            device_name (str): device for the circuit
            device_type (str): device type (iosxr or junos)
            circuits_dict (dict): dict of circuit name, service type, IPs
        """

        super().__init__(username, device_name, device_type)
        self.circuits_dict = circuits_dict

    def get_circuit_main(self):
        """Main method for circuit checks.

        Returns:
            dict: nested dict of interesting items
        """

        circuits_output = {}
        for self.circuit in self.circuits_dict:

            print(f'\t{self.circuit.upper()}: {{')

            # main method calls
            if self.circuits_dict[self.circuit]['service'] == 'static':

                # try:
                #     print(f'\t\t1) IPv4 Static')
                #     ipv4_static = self.get_circuit_static('inet.0', self.circuits_dict[self.circuit]['ipv4_routes'])
                # except: ipv4_static = 'None'

                print(f'\t\t1) IPv4 Static')
                ipv4_static = self.get_circuit_static('inet.0', self.circuits_dict[self.circuit]['ipv4_routes'])

                try:
                    print(f'\t\t2) IPv6 Static')
                    ipv6_static = self.get_circuit_static('inet6.0', self.circuits_dict[self.circuit]['ipv6_routes'])

                except:
                    ipv6_static = 'None'

                output_dict = {
                    self.circuit: {
                        'Service': self.circuits_dict[self.circuit]['service'],
                        'IPv4 BGP Data': ipv4_static,
                        'IPv6 BGP Data': ipv6_static
                    }
                }

            else:
                if self.circuits_dict[self.circuit]['service'] == 'ebgp':
                    try:
                        self.port = self.circuits_dict[self.circuit]['port']

                    except:
                        print('\n\n\tPlease enter a valid port and re-run.\n\n')
                        sys.exit(1)

                # get IPs unless defined manually
                print(f'\t\t1) Neighbor IPs')
                get_ips = GetNeighborIPs(self.circuits_dict[self.circuit], self.circuit)
                if self.circuits_dict[self.circuit]['service'] == ('ebgp' or 'static'):
                    get_ips.get_ebgp_static_ips(self.device_type, self.connection)
                else:
                    get_ips.get_ibgp_ips()
                self.addresses = [ self.circuits_dict[self.circuit]['ipv4_neighbor'], self.circuits_dict[self.circuit]['ipv6_neighbor']]

                print(f'\t\t2) BGP Routes')
                self.get_circuit_bgp()
                self.adv_counts([ self.ipv4_circuit_data[1], self.ipv6_circuit_data[1] ])

                print(f'\t\t3) Interface')
                self.get_circuit_iface()

                print(f'\t\t4) IS-IS')
                self.get_circuit_isis()

                # output dict returned
                output_dict = {
                    self.circuit: {
                        'Service': self.circuits_dict[self.circuit]['service'],
                        'Interface': self.iface,
                        'IS-IS': self.isis,
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
            print('\t}')

        self.close_connections()

        return circuits_output, self.start_time

    def get_circuit_bgp(self):
        """Call device-specific methods. HPR check called first for XR"""

        if self.device_type == 'iosxr':
            self.check_hpr_xr()
            self.get_circuit_bgp_xr()

        elif self.device_type == 'junos':
            self.get_circuit_bgp_junos()

    def get_circuit_iface(self):

        if self.device_type == 'iosxr':
            self.get_circuit_iface_xr()

        elif self.device_type == 'junos':
            self.get_circuit_iface_junos()

    def get_circuit_isis(self):

        if self.device_type == 'iosxr':
            self.get_circuit_isis_xr()

        elif self.device_type == 'junos':
            self.get_circuit_isis_junos()

    def adv_counts(self, adv_counts):
        """Convert adv_count int to string for diffs - adv. counts fluctuate.

        Args:
            adv_counts (list): list of v4, v6 adv_count ints
        """

        for index, adv_count in enumerate(adv_counts):

            if not adv_count:
                if index == 0: self.ipv4_adv_count = 'No Adv. Routes'
                elif index == 1: self.ipv6_adv_count = 'No Adv. Routes'

            # HPR Full Table ~ 20,000 / 20,000
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

            # DC Full Table ~ 800,000 / 100,000
            elif self.vrf == 'default' or 'master':

                if adv_count > 800000 and index == 0: self.ipv4_adv_count = 'Full DC IPv4 Table'
                elif adv_count > 100000 and index == 1: self.ipv6_adv_count = 'Full DC IPv6 Table'

                elif adv_count > 0:
                    if index == 0: self.ipv4_adv_count = adv_count
                    elif index == 1: self.ipv6_adv_count = adv_count

                elif adv_count == 0:
                    if index == 0: self.ipv4_adv_count = 'No Adv. Routes'
                    elif index == 1: self.ipv6_adv_count = 'No Adv. Routes'


    # XR CIRCUIT METHODS
    def check_hpr_xr(self):
        """HPR VRF not check-able via RPC in 6.3.3. Using napalm"""

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
        except:
            pass

    def get_circuit_bgp_xr(self):
        """Check HPR, if not HPR pass addresses to get checks data"""

        if self.vrf == 'hpr':

            elapsed_time = int(time.time() - self.start_time)
            self.ipv4_circuit_data,  self.ipv6_circuit_data, self.start_time, = NapalmXR(elapsed_time, self.username, self.device_name, addresses=self.addresses).get_circuit_hpr()

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
        """Run twice per circuit, once for v4 and once for v6"""

        # pylint: disable=no-member
        if address == self.addresses[0]: version = 'ipv4'
        else: version = 'ipv6'

        xr_parse = ParseData(self.device_type)

        circuit_raw = self.connection.get((filters.bgp_routes_filter.format(version=version, neighbor=address)))
        default_raw = self.connection.get((filters.bgp_default_filter.format(version=version, neighbor=address)))

        circuit_bgp = xr_parse.parse_circuit_bgp_xr(circuit_raw)
        default = xr_parse.parse_circuit_default_xr(default_raw)

        return circuit_bgp[0], circuit_bgp[1], circuit_bgp[2], default

    def get_circuit_iface_xr(self):

        # pylint: disable=no-member
        xr_parse = ParseData(self.device_type)

        iface_name_raw = self.connection.get((filters.iface_name_circuit.format(iface=self.port)))
        iface_raw = self.connection.get((filters.iface_circuit.format(iface=self.port)))

        xr_parse.parse_circuit_iface_name_xr(iface_name_raw)
        self.iface = xr_parse.parse_circuit_iface_xr(iface_raw)

    def get_circuit_isis_xr(self):

        # pylint: disable=no-member
        xr_parse = ParseData(self.device_type)
        isis_raw = self.connection.get((filters.isis_circuit.format(iface=self.port)))
        self.isis = xr_parse.parse_circuit_isis_xr(isis_raw)


    # JUNOS CIRCUIT METHODS
    def get_circuit_bgp_junos(self):
        """Pass addresses to get checks data"""

        if self.addresses[0]:
            self.ipv4_circuit_data = self.circuit_bgp_junos(self.addresses[0])
        else:
            self.ipv4_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

        if self.addresses[1]:
            self.ipv6_circuit_data = self.circuit_bgp_junos(self.addresses[1])
        else:
            self.ipv6_circuit_data = [ 'No Peering', None, 'No Peering', 'No Peering']

    def circuit_bgp_junos(self, address):
        """Run twice per circuit, once for v4 and once for v6"""

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
        rx_routes = self.rx_routes_junos(routes_list, table, address)

        default_raw = self.connection.rpc.get_route_information(destination=default, exact=True, neighbor=address, advertising_protocol_name='bgp')
        default = junos_parse.parse_circuit_default_junos(default_raw)

        return rx_routes, adv_count, rx_count, default

    def rx_routes_junos(self, routes_list, table, address, connection_static='', static=False):

        junos_parse = ParseData(self.device_type)

        if connection_static != '': connection = connection_static
        else: connection = self.connection

        rx_routes = {}
        for route in routes_list:

            if static:
                route_data = connection.rpc.get_route_information(destination=route, table=table, exact=True, detail=True, protocol='bgp')
            else:
                route_data = connection.rpc.get_route_information(destination=route, table=table, exact=True, detail=True, protocol='bgp', source_gateway=address)
            rx_routes.update(junos_parse.parse_circuit_bgp_junos(route_data))

        return rx_routes

    def get_circuit_iface_junos(self):

        junos_parse = ParseData(self.device_type)

        optics_raw = self.connection.rpc.get_interface_optics_diagnostics_information(interface_name=self.port)
        junos_parse.parse_circuit_optics_junos(optics_raw)
        iface_raw = self.connection.rpc.get_interface_information(interface_name=self.port, extensive=True)
        self.iface = junos_parse.parse_circuit_iface_junos(iface_raw)

    def get_circuit_isis_junos(self):

        isis_raw = self.connection.rpc.get_isis_interface_information(interface_name=self.port, extensive=True)
        junos_parse = ParseData(self.device_type)
        self.isis = junos_parse.parse_circuit_isis_junos(isis_raw)

    def get_circuit_static(self, table, routes_list):
        """No good RPC for XR, all statics done via Junos"""

        address = get_agg_v4(self.device_name)
        if self.device_type != 'junos':
            self.device_type = 'junos'
            switch = True

            elapsed_time = int(time.time() - self.start_time)
            if elapsed_time < 30:
                print(f'\t\t\t... {int(30 - elapsed_time)} sec')
                time.sleep(30 - elapsed_time)

            connection = Login(self.username, 'lax-agg10', 'junos').pyez_connect()
            connection.open()

        else:
            connection = self.connection
            switch = False

        rx_routes = self.rx_routes_junos(routes_list, table, address, connection_static=connection, static=True)

        self.start_time = time.time()
        if switch:
            connection.close()
            self.device_type = 'iosxr'

        return rx_routes


class DeviceChecks(Device):

    def __init__(self, username, device_name, device_type):
        """Return device-based pre/post maintenance checks.

        Args:
            username (str): mfa username
            device_name (str): device for the circuit
            device_type (str): device type (iosxr or junos)
        """

        super().__init__(username, device_name, device_type)

    def get_device_main(self):
        """Main function call.

        Returns:
            dict: output dictionary
        """

        if self.device_type == 'junos':
            output_dict_list = self.get_device_junos()

        elif self.device_type == 'iosxr':
            output_dict_list = self.get_device_xr()

        output_dict = self.create_output_dict(output_dict_list)
        self.close_connections()

        return output_dict, self.start_time

    def create_output_dict(self, output_dict_list):
        """Convert to nested dict"""

        output_dict = {
            'Software': output_dict_list[0],
            'Power': output_dict_list[1],
            'IS-IS': output_dict_list[2],
            'PIM Enabled Ports': output_dict_list[3],
            'Established MSDP Neighbors': output_dict_list[4],
            'Interfaces': output_dict_list[5],
            'Established BGP Neighbors': output_dict_list[6]
        }

        return output_dict


    # XR DEVICE METHODS
    def get_device_xr(self):

        # pylint: disable=no-member

        xr_parse = ParseData(self.device_type)

        power = 'Not Supported'
        print(f'\t1) PIM Neighbors')
        pim_raw = self.connection.get((filters.pim_device))
        pim = xr_parse.device_pim_xr(pim_raw)

        print(f'\t2) IS-IS Adjacencies')
        isis_raw = self.connection.get((filters.isis_device))
        isis = xr_parse.device_isis_xr(isis_raw)

        print(f'\t3) BGP Neighbors')
        bgp_raw = self.connection.get((filters.bgp_device))
        bgp = xr_parse.device_bgp_xr(bgp_raw)

        self.napalm_device_xr()

        return self.software, power, isis, pim, self.msdp, self.ifaces, bgp

    def napalm_device_xr(self):

        elapsed_time = int(time.time() - self.start_time)
        self.software, self.msdp, self.ifaces, self.start_time = NapalmXR(elapsed_time, self.username, self.device_name, circuit=False).get_device_xr()


    # JUNOS DEVICE METHODS
    def get_device_junos(self):
        """Use PyEZ to pull from Junos. Called from main class method

        Returns:
            dict: output dict
        """

        junos_parse = ParseData(self.device_type)

        print(f'\t1) PIM Neighbors')
        pim_raw = self.connection.rpc.get_pim_neighbors_information()
        pim = junos_parse.device_pim_junos(pim_raw)

        print(f'\t2) IS-IS Adjacencies')
        isis_raw = self.connection.rpc.get_isis_adjacency_information()
        isis = junos_parse.device_isis_junos(isis_raw)

        print(f'\t3) BGP Neighbors')
        bgp_raw = self.connection.rpc.get_bgp_summary_information()
        bgp = junos_parse.device_bgp_junos(bgp_raw)

        print(f'\t4) Interface Stats')
        iface_raw = self.connection.rpc.get_interface_information(detail=True, statistics=True)
        iface = junos_parse.device_iface_junos(iface_raw)

        print(f'\t5) Software')
        software = etree_to_dict(self.connection.rpc.get_software_information())['software-information']['junos-version']

        print(f'\t6) MSDP Neighbors')
        msdp_raw = self.connection.rpc.get_msdp_information()
        msdp = junos_parse.device_msdp_junos(msdp_raw)

        print(f'\t7) Power')
        power_raw = self.connection.rpc.get_power_usage_information_detail()
        power = junos_parse.device_power_junos(power_raw)

        vrfs = etree_to_dict(self.connection.rpc.get_instance_information(brief=True))
        vrf = None
        for i in vrfs['instance-information']['instance-core']:
            if i['instance-name'] == 'hpr':
                vrf = 'hpr'
                break

        if vrf == 'hpr':
            print(f'\t8) HPR: {{')
            print(f'\t\t1) IS-IS HPR Adjacencies')
            isis_hpr_raw = self.connection.rpc.get_isis_adjacency_information(instance='hpr')
            isis_hpr = junos_parse.device_isis_junos(isis_hpr_raw)
            isis.update(isis_hpr)

            print(f'\t\t2) MSDP HPR Neighbors')
            msdp_hpr_raw = self.connection.rpc.get_msdp_information(instance='hpr')
            msdp_hpr = junos_parse.device_msdp_junos(msdp_hpr_raw)
            msdp.update(msdp_hpr)

            print(f'\t\t3) PIM HPR Neighbors')
            pim_hpr_raw = self.connection.rpc.get_pim_neighbors_information(instance='hpr')
            pim_hpr = junos_parse.device_pim_junos(pim_hpr_raw)
            pim.update(pim_hpr)
            print('\t}')

        return software, power, isis, pim, msdp, iface, bgp