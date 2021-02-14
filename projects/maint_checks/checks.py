from login import Login
from neighbor_routes import GetNeighborRoutes, GetNLRI
from parse import ParseData, etree_to_dict
import fsm
import time
import sys


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
        self.output_dict = {}
        self.global_connect = Login(username, global_agg, global_type).napalm_connect()


    def get_bgp_output_dict(self):
        """Return dict of BGP data.
        Returns:
            (dict): Output dict for each neighbor defined in the circuits_checks dict.
        """
        try:
            print(f'\nConnecting to BGP Table Source - {self.global_agg}')
            start_time = time.time()
            self.global_connect.open()
            print(f'\t... connected to {self.global_agg} with napalm.')
        except:
            print('\n\n\tAuthentication Error. Please wait and run again.\n\n')
            sys.exit(1)

        for agg_router in self.circuit_checks:

            if agg_router != self.global_agg:
                elapsed_time = time.time() - start_time
                print(f'\t... resetting OTP ({int(30 - elapsed_time)} sec)')
                time.sleep(30 - elapsed_time)
                print(f'\t... done')

                agg_type = self.circuit_checks[agg_router]['device_type']
                self.agg_connect = Login(self.username, agg_router, agg_type).napalm_connect()
                try:
                    print(f'Connecting to Agg Router - {agg_router}')
                    self.agg_connect.open()
                    print(f'\t... connected to {agg_router} with napalm')
                    start_time = time.time()
                except:
                    print('\n\n\tAuthentication Error. Please wait and run again.\n\n')
                    sys.exit(1)

            else:
                self.agg_connect = self.global_connect
                agg_type = self.global_type

            circuits = self.circuit_checks[agg_router]['circuits']

            for circuit in circuits:
                circuit_dict = circuits[circuit]
                service = circuit_dict['service']
                asn = None
                print(f'\n\n\t----- Starting {circuit} -----')

                if service.endswith('bgp'):

                    if agg_type == 'junos':
                        bgp_routes = GetNeighborRoutes(self.agg_connect, circuit_dict, circuit).get_junos_bgp_routes()
                    elif agg_type == 'iosxr':
                        bgp_routes = GetNeighborRoutes(self.agg_connect, circuit_dict, circuit).get_xr_bgp_routes()
                    else:
                        print('*** ERROR: Unsupported Agg Router type. Junos/IOS-XR are supported.')
                        sys.exit(1)

                    v4_rx_routes = bgp_routes[0][0]
                    v4_adv_count = bgp_routes[0][1]
                    v4_default = bgp_routes[0][2]
                    v6_rx_routes = bgp_routes[1][0]
                    v6_adv_count = bgp_routes[1][1]
                    v6_default = bgp_routes[1][2]

                elif service == 'static':

                    static_routes =  GetNeighborRoutes(self.agg_connect, circuit_dict, circuit).get_static_routes(agg_type)

                    v4_rx_routes = static_routes[0]
                    v6_rx_routes = static_routes[1]
                    v4_adv_count = v4_default = v6_adv_count = v6_default = None
                    asn = circuit_dict['asn']

                print(f'Getting BGP NLRIs per-BGP route for {circuit}.')
                global_routes = GetNLRI(self.global_connect, [v4_rx_routes, v6_rx_routes], asn).get_bgp_nlri()

                check_values = [circuit_dict['v4_neighbor'], circuit_dict['v6_neighbor'], v4_adv_count, v6_adv_count, v4_default, v6_default]
                for index, value in enumerate(check_values):
                    if not value:
                        if index in (0,1):
                            check_values[index] = 'No Address Defined'
                        else:
                            check_values[index] = 'N/A'

                output_dict_1 = {
                    circuit: {
                        'Service': circuit_dict['service'],
                        'IPv4 Neighbor': check_values[0],
                        'IPv6 Neighbor': check_values[1],
                        'IPv4 Adv. Count': check_values[2],
                        'IPv4 Adv. Default?': check_values[4],
                        'IPv6 Adv. Count': check_values[3],
                        'IPv6 Adv. Default?': check_values[5],
                        'IPv4 Routes': global_routes[0],
                        'IPv6 Routes': global_routes[1]
                    }
                }
                self.output_dict.update(output_dict_1)
                print(f'\t----- Done with {circuit} -----')

        if self.agg_connect != self.global_connect:
            self.agg_connect.close()
        self.global_connect.close()

        return self.output_dict


class DeviceChecks:

    def __init__(self, username, device_dict):
        self.username = username
        self.device_dict = device_dict

    def get_device_main(self):
        """Main function call.
        Returns:
            dict: output dictionary
        """
        output_dict = {}
        for index, device in enumerate(self.device_dict):
            start_time = time.time()

            for self.device, self.device_type in device.items():

                if self.device_type == 'junos':
                    try:
                        print(f'Connecting to {self.device}')
                        self.connection = Login(self.username, self.device, None).pyez_login()
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

        software = etree_to_dict(self.connection.rpc.get_software_information())['software-information']['junos-version']
        power = ParseData(etree_to_dict(self.connection.rpc.get_power_usage_information_detail())).parse_power_junos()
        bgp = ParseData(etree_to_dict(self.connection.rpc.get_bgp_summary_information())).parse_bgp_junos()
        isis = ParseData(etree_to_dict(self.connection.rpc.get_isis_adjacency_information())).parse_isis_junos()
        msdp = ParseData(etree_to_dict(self.connection.rpc.get_msdp_information())).parse_msdp_junos()
        pim = ParseData(etree_to_dict(self.connection.rpc.get_pim_neighbors_information())).parse_pim_junos()
        optics = ParseData(etree_to_dict(self.connection.rpc.get_interface_optics_diagnostics_information())).parse_optics_junos()
        iface = ParseData(etree_to_dict(self.connection.rpc.get_interface_information(detail=True, statistics=True))).parse_iface_junos(optics)

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

    def get_device_iosxr(self):
        """Retrieve and parse output from IOS-XR Napalm getters
            1. Needs optics and to change
        Returns:
            dict: Each return is a nest dict
        """

        self.connection.open()

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

        self.connection.close()

        output_dict = {
            self.device.upper(): {
                'Software': facts['os_version'],
                'Power': 'Pending',
                'IS-IS': isis,
                'Established PIM Neighbors': pim,
                'Established MSDP Neighbors': msdp,
                'Interfaces': iface,
                'Established BGP Neighbors': bgp
            }
        }

        return output_dict