from parse import ParseData
from login import Login
import time
import filters
import textfsm
import tempfile


class XRGetHPR:

    def __init__(self, elapsed_time, username, device_name, addresses):

        self.device_name = device_name
        self.addresses = addresses

        if elapsed_time < 30:
            print(f'waiting {30 - elapsed_time}')
            time.sleep(30 - elapsed_time)

        self.napalm_connection = Login(username, device_name, 'iosxr').napalm_connect()
        print('waiting 30')
        time.sleep(30)
        self.global_connection = Login(username, 'lax-agg10', 'junos').napalm_connect()
        self.new_start = time.time()

        self.napalm_connection.open()
        self.global_connection.open()

    def get_xr_bgp_main(self):

        v4_list, v6_list = self.get_xr_bgp_routes()

        v4_routes = self.get_bgp_pa(v4_list[0])
        v6_routes = self.get_bgp_pa(v6_list[0])

        self.napalm_connection.close()
        self.global_connection.close()

        return [ v4_routes, v4_list[1], v4_list[2], v4_list[3] ], [ v6_routes, v6_list[1], v6_list[2], v6_list[3] ], self.new_start


    def get_xr_bgp_routes(self):
        """For HPR peerings on XR Agg routers only.

        Returns:
            (list): v4 and v6 output lists
        """

        for index, address in enumerate(self.addresses):

            rx_routes = adv_count = default = None
            if index == 0: version = 'ipv4'
            else: version = 'ipv6'

            if address:
                rx_routes_raw = f'show bgp vrf hpr {version} unicast neighbors {address} routes | begin Network'
                adv_routes_raw = f'show bgp vrf hpr {version} unicast neighbors {address} advertised-count'
                default = 'N/A'

                pull_bgp = self.napalm_connection.cli([rx_routes_raw, adv_routes_raw])

                rx_routes = self.parse_FSM(filters.template_bgp_rx, pull_bgp[rx_routes_raw])
                rx_count = len(rx_routes)
                if len(rx_routes) == 0: rx_routes = None

                try:
                    adv_count = int(self.parse_FSM(filters.template_xr_adv, pull_bgp[adv_routes_raw])[0])

                except:
                    adv_count = None

            if index == 0: v4_list = [rx_routes, adv_count, rx_count, default]
            else: v6_list = [rx_routes, adv_count, rx_count, default]

        return v4_list, v6_list

    def get_bgp_pa(self, routes_list):
        """
        Returns:
            (dict): IPv4/IPv6 route data: Next-Hop, AS Path, LocalPref, Metric, and Communities for each Rx route.
        """

        routes_dict = {}

        if routes_list:
            for route in routes_list:

                try:
                    route_dict = self.global_connection.get_route_to(route,'bgp')
                    route_dict = {
                        route: {
                            'Next-Hop': route_dict[route][0]['next_hop'],
                            'Local Preference': route_dict[route][0]['protocol_attributes']['local_preference'],
                            'AS Path': route_dict[route][0]['protocol_attributes']['as_path'].split(' \n')[0],
                            'MED': route_dict[route][0]['protocol_attributes']['metric'],
                            'Communities': route_dict[route][0]['protocol_attributes']['communities']
                        }
                    }
                    routes_dict.update(route_dict)

                except:
                    print(f'\nManually check: {route}.\n')

        else:
            route_dict = 'No prefixes received'

        return routes_dict

    def parse_FSM(self, template, data):
        """Assigns the passed template to a temporary file, parses with TextFSM, and then closes the file.
        Returns:
            fsm_results_flat: parsed output of text
        """

        tmp = tempfile.NamedTemporaryFile()
        with open(tmp.name, 'w') as f:
            f.write(template)

        with open(tmp.name, 'r') as f:
            fsm = textfsm.TextFSM(f)
            fsm_results = fsm.ParseText(data)

        fsm_results_flat = [val for sublist in fsm_results for val in sublist] # flatten list of lists

        return fsm_results_flat