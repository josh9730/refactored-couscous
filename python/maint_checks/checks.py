from login import Login
from neighbor_ips import GetNeighborIPs
from neighbor_routes import GetNeighborRoutes, GetRouteData
from parse import ParseData, etree_to_dict
import fsm
import time

from pprint import pprint

class CircuitChecks:
    """For per-circuit checks. Currently only BGP.
    """

    def __init__(self, username, global_agg, global_type, circuit_checks):
        """
        Args:
            username (str): Username for keyring/mfa.
            global_agg (str): Global agg router to login to for BGP checks (must be Junos).
            global_type (str): Device type of global router (junos/iosxr).
            circuit_checks (dict): All data to be checked. Contains each circuit to check per agg router.
        """

        self.username = username
        self.global_agg = global_agg
        self.global_type = global_type
        self.circuit_checks = circuit_checks
        self.global_connect = Login(username, global_agg, global_type).napalm_connect()
        self.output_dict = {}

    def get_bgp_output_dict(self):
        """Return dict of BGP data.

        Returns:
            (dict): Output dict for each neighbor defined in the circuits_checks dict.
        """

        self.global_connect.open()

        for agg_router in self.circuit_checks:

            if agg_router != self.global_agg:
                print(f'\t... resetting OTP (30 sec)')
                time.sleep(30)
                print('\t... done')

                agg_type = self.circuit_checks[agg_router]['device_type']
                self.agg_connect = Login(self.username, agg_router, agg_type).napalm_connect()
                self.agg_connect.open()

            else:
                self.agg_connect = self.global_connect
                agg_type = self.global_type

            self.circuits = self.circuit_checks[agg_router]['circuits']

            for circuit in self.circuits:
                self.circuit_dict = self.circuits[circuit]
                self.service = self.circuit_dict['service']

                if self.service.endswith('bgp'):
                    if self.service == 'ibgp':
                        GetNeighborIPs(self.circuit_dict, circuit).get_ibgp_ips()

                    elif self.service == 'ebgp':
                        GetNeighborIPs(self.circuit_dict, circuit).get_ebgp_ips(self.agg_connect)

                    if agg_type == 'junos':
                        bgp_routes = GetNeighborRoutes(self.agg_connect, self.circuit_dict).get_junos_bgp_routes()
                    elif agg_type == 'iosxr':
                        bgp_routes = GetNeighborRoutes(self.agg_connect, self.circuit_dict).get_xr_bgp_routes()
                    else:
                        print('Unsupported Agg Router type. Junos/IOS-XR are supported.')

                    v4_rx_routes = bgp_routes[0][0]
                    v4_adv_count = bgp_routes[0][1]
                    v4_default = bgp_routes[0][2]
                    v6_rx_routes = bgp_routes[1][0]
                    v6_adv_count = bgp_routes[1][1]
                    v6_default = bgp_routes[1][2]

                elif self.circuit_dict['service'] == 'static':
                    GetNeighborIPs(self.circuit_dict, circuit).get_ebgp_ips(self.agg_connect)
                    static_routes = GetNeighborRoutes(self.agg_connect, self.circuit_dict).get_static_routes(agg_type)

                    v4_rx_routes = static_routes[0]
                    v6_rx_routes = static_routes[1]
                    v4_adv_count=v4_default=v6_adv_count=v6_default = 'N/A'

                self.ipv4_nei = self.circuit_dict['ipv4_neighbor']
                self.ipv6_nei = self.circuit_dict['ipv6_neighbor']

                global_routes = GetRouteData(self.global_connect, [v4_rx_routes, v6_rx_routes]).get_bgp_nlri()

                output_dict_1 = {
                    circuit: {
                        'Service': self.circuit_dict['service'],
                        'IPv4 Neighbor': self.ipv4_nei,
                        'IPv6 Neighbor': self.ipv6_nei,
                        'IPv4 Adv. Count': v4_adv_count,
                        'IPv4 Adv. Default?': v4_default,
                        'IPv6 Adv. Count': v6_adv_count,
                        'IPv6 Adv. Default?': v6_default,
                        'IPv4 Routes': global_routes[0],
                        'IPv6 Routes': global_routes[1]
                    }
                }
                self.output_dict.update(output_dict_1)

        if self.agg_connect != self.global_connect:
            self.agg_connect.close()
        self.global_connect.close()

        return self.output_dict


class DeviceChecks:

    def __init__(self, username, device, device_type):
        self.username = username
        self.device = device
        self.device_type = device_type

        if device_type == 'junos':
            device_type = None
            self.connection = Login(self.username, self.device, device_type).pyez_connect()
        elif device_type == 'iosxr':
            self.connection = Login(self.username, self.device, self.device_type).napalm_connect()

    def get_device_main(self):
        """Main function call.

        Returns:
            dict: output dictionary
        """

        if self.device_type == 'junos':
            output_dict = self.get_device_junos()
        elif self.device_type == 'iosxr':
            output_dict = self.get_device_iosxr()

        return output_dict

    def get_device_junos(self):
        """Use PyEZ to pull from Junos. Called from main class function

        Returns:
            dict: output dict
        """

        self.connection.open()

        show_software = etree_to_dict(self.connection.rpc.get_software_information())
        show_power = etree_to_dict(self.connection.rpc.get_power_usage_information_detail())
        show_bgp = etree_to_dict(self.connection.rpc.get_bgp_summary_information())
        show_isis = etree_to_dict(self.connection.rpc.get_isis_adjacency_information())
        show_msdp = etree_to_dict(self.connection.rpc.get_msdp_information())
        show_pim = etree_to_dict(self.connection.rpc.get_pim_neighbors_information())
        show_optics = etree_to_dict(self.connection.rpc.get_interface_optics_diagnostics_information())
        show_iface = etree_to_dict(self.connection.rpc.get_interface_information(detail=True, statistics=True))

        software = show_software['software-information']['junos-version']
        power = ParseData(show_power).parse_power_junos()
        bgp = ParseData(show_bgp).parse_bgp_junos()
        isis = ParseData(show_isis).parse_isis_junos()
        msdp = ParseData(show_msdp).parse_msdp_junos()
        pim = ParseData(show_pim).parse_pim_junos()
        optics = ParseData(show_optics).parse_optics_junos()
        iface = ParseData(show_iface).parse_iface_junos(optics)

        vrfs = etree_to_dict(self.connection.rpc.get_instance_information(brief=True))
        vrf = None
        for i in vrfs['instance-information']['instance-core']:
            if i['instance-name'] == 'hpr':
                vrf = 'hpr'
                break
        if vrf == 'hpr':
            show_msdp_hpr = etree_to_dict(self.connection.rpc.get_msdp_information(instance='hpr'))
            msdp_hpr = ParseData(show_msdp_hpr).parse_msdp_junos()
            msdp.update(msdp_hpr)

            show_pim_hpr = etree_to_dict(self.connection.rpc.get_pim_neighbors_information(instance='hpr'))
            pim_hpr = ParseData(show_pim_hpr).parse_pim_junos()
            pim.update(pim_hpr)

        self.connection.close()

        output_dict = {
            'Hostname': self.device,
            'Software': software,
            'Power': power,
            'IS-IS': isis,
            'PIM Enabled Ports': pim,
            'Established MSDP Neighbors': msdp,
            'Interfaces': iface,
            'Established BGP Neighbors': bgp
        }

        return output_dict

    def get_device_iosxr(self):
        """Retrieve and parse output from IOS-XR Napalm getters
            1. Needs optics and to change

        Returns:
            dict: Each return is a nest dict
        """

        show_isis = "show isis neighbors | in PtoP"
        show_msdp = "show msdp summary"
        show_pim = "show pim neighbor"
        cli_list = [show_isis, show_pim, show_msdp]
        show_bgp = self.connection.get_bgp_neighbors()

        facts = self.connection.get_facts()
        iface = self.connection.get_interfaces()
        iface_counters = self.connection.get_interfaces_counters()
        cli_pull = self.connection.cli(cli_list)

        isis = ParseData(cli_pull[show_isis]).parse_isis_xr()
        msdp = ParseData(cli_pull[show_msdp], template=fsm.template_xr_msdp).parse_FSM()
        pim = ParseData(cli_pull[show_pim], template=fsm.template_junos_pim_msdp).parse_FSM()

        optics = None
        iface = ParseData(iface, device_type=self.device_type).parse_iface_xr(iface_counters, optics)

        bgp = ParseData(show_bgp, device_type=self.device_type).parse_bgp_xr()

        output_dict = {
            'Hostname': self.device,
            'Software': facts['os_version'],
            'Power': 'Pending',
            'IS-IS': isis,
            'PIM Enabled Ports': pim,
            'Established MSDP Neighbors': msdp,
            'Interfaces': iface,
            'Established BGP Neighbors': bgp
        }

        return output_dict

    # def show_device_status(self):

    #     get_status = get_device_status()