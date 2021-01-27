from parse import ParseData
from neighbor_ips import GetNeighborIPs
import fsm

class GetNeighborRoutes:
    """Retrieves routes per 'circuit'. Gets:
    1. Recieved routes from neighbor (bgp only).
    2. Advertised count from neighbor (bgp only).
    3. Check if default route sent (bgp only).
    4. All routes with tagged ASN (static only).
    """

    def __init__(self, connection, circuit_dict, hostname):
        """
        Args:
            connection: napalm connection to agg router.
            circuit (dict): Contains IPs, device types, service, port strings.
        """

        self.hostname = hostname
        self.connection = connection
        self.circuit_dict = circuit_dict
        self.service = self.circuit_dict['service']
        self.rx_routes = self.adv_count = self.default = None

        if self.service == 'ibgp':
            GetNeighborIPs(self.circuit_dict, self.hostname ).get_ibgp_ips()
        else:
            GetNeighborIPs(self.circuit_dict, self.hostname ).get_ebgp_static_ips(self.connection)

        try:
            self.addresses = [self.circuit_dict['v4_neighbor'], self.circuit_dict['v6_neighbor']]
        except:
            pass

        print(f'Getting routes for {self.hostname}.')

    def get_xr_bgp_routes(self):
        """For XR Agg routers only.

        Returns:
            (list): v4 and v6 output lists
        """

        vrfs = self.connection.cli(['show vrf hpr'])
        if vrfs['show vrf hpr']:
            vrf = 'vrf all '
        else:
            vrf = ''

        for index, address in enumerate(self.addresses):
            if index == 0:
                version = 'ipv4'
            else:
                version = 'ipv6'

            if address:
                xr_rx_routes = f'show bgp {vrf}{version} unicast neighbor {address} routes'
                xr_adv_count = f'show bgp {vrf}{version} unicast neighbor {address} advertised-count'
                xr_default = f'show bgp {vrf}{version} unicast neighbor {address} | include Default'

                pull_bgp = self.connection.cli([xr_rx_routes, xr_adv_count, xr_default])

                rx_routes = ParseData(pull_bgp[xr_rx_routes], template=fsm.template_bgp_rx).parse_FSM()
                if len(rx_routes) == 0: rx_routes = None

                try:
                    if ParseData(pull_bgp[xr_default], template=fsm.template_xr_bgp_default).parse_FSM()[0]:
                        default = 'Default Sent'
                except:
                    default = 'Default Not Sent'

                if vrf == 'vrf all ' and index == 0:
                    check_hpr = ParseData(pull_bgp[xr_rx_routes], template=fsm.template_xr_bgp_hpr).parse_FSM()[0]
                try:
                    adv_count = int(ParseData(pull_bgp[xr_adv_count], template=fsm.template_xr_adv).parse_FSM()[0])
                    if vrf == '':
                        if adv_count > 800000 and index == 0:
                            adv_count = 'Full DC IPv4 Table'
                        elif adv_count > 100000 and index == 1:
                            adv_count = 'Full DC IPv6 Table'
                        elif adv_count > 1:
                            adv_count = adv_count
                    elif vrf == 'vrf all ' and check_hpr == 'hpr':
                        if adv_count > 20000 and index == 0:
                            adv_count = 'Full HPR IPv4 Table'
                        elif adv_count > 2000 and index == 1:
                            adv_count = 'Full HPR IPv6 Table'
                        elif adv_count > 1:
                            adv_count = adv_count
                except:
                    adv_count = 'No Adv. Routes'

            if index == 0:
                v4_list = [rx_routes, adv_count, default]
                rx_routes = adv_count = default = None
            else:
                v6_list = [rx_routes, adv_count, default]

        return v4_list, v6_list

    def get_junos_bgp_routes(self):
        """For Junos Agg routers only.

        Returns:
            (list): v4 and v6 output lists
        """

        for index, address in enumerate(self.addresses):

            if index == 0:
                default = '0.0.0.0/0'
            else:
                default = '::0/0'

            if address:
                junos_rx_routes = f'show route receive-protocol bgp {address}'
                junos_adv_count = f'show bgp neighbor {address}'
                junos_default = f'show route advertising-protocol bgp {address} exact {default}'

                pull_bgp = self.connection.cli([junos_rx_routes, junos_adv_count, junos_default])

                rx_routes = ParseData(pull_bgp[junos_rx_routes], template=fsm.template_bgp_rx).parse_FSM()
                adv_count = ParseData(pull_bgp[junos_adv_count], template=fsm.template_junos_adv).parse_FSM()
                default = ParseData(pull_bgp[junos_default], template=fsm.template_bgp_rx).parse_FSM()

                try:
                    if default[0] == '0.0.0.0/0' or default[0] == ':/0':
                        default = 'Default Sent'
                except:
                    default = 'Default Not Sent'

                if index == 0:
                    check_hpr = ParseData(pull_bgp[junos_adv_count], template=fsm.template_junos_bgp_hpr).parse_FSM()[0]

                if len(rx_routes) == 0: rx_routes = None

                try:
                    adv_count = int(adv_count[0])
                    if check_hpr != 'hpr':
                        if adv_count > 800000 and index == 0:
                            adv_count = 'Full DC IPv4 Table'
                        elif adv_count > 100000 and index == 1:
                            adv_count = 'Full DC IPv6 Table'
                        elif adv_count > 1:
                            adv_count = adv_count
                    elif check_hpr == 'hpr':
                        if adv_count > 20000 and index == 0:
                            adv_count = 'Full HPR IPv4 Table'
                        elif adv_count > 2000 and index == 1:
                            adv_count = 'Full HPR IPv6 Table'
                        elif adv_count > 1:
                            adv_count = adv_count
                except:
                    self.adv_count = 'No Adv. Routes'

            if index == 0:
                v4_list = [rx_routes, adv_count, default]
                rx_routes = adv_count = default = None
            else:
                v6_list = [rx_routes, adv_count, default]

        return v4_list, v6_list

    def get_static_routes(self, device_type):
        """For static only. Requires ASN tag (may not always be tagged).

        Args:
            device_type: Junos or IOS-XR

        Returns:
            (list): List of v4/v6 static routes tagged with ASN
        """

        self.device_type = device_type
        self.v4_routes = self.v6_routes = None
        self.asn = self.circuit_dict['asn']

        for index in range(2):

            if self.device_type == 'junos':
                if index == 0:
                    table = 'inet.0'
                else:
                    table = 'inet.6'
                static = f'show route protocol static active-path table {table} | match {self.asn}'

            elif self.device_type == 'iosxr':
                if index == 0:
                    table = 'ipv4'
                else:
                    table = 'ipv6'
                static = f'show run router static address-family {table} unicast | in {self.asn}'

            pull_static = self.connection.cli([static])
            routes = ParseData(pull_static[static], template=fsm.template_static).parse_FSM()

            if index == 0:
                v4_routes = routes
                routes = None
            else:
                v6_routes = routes

        return v4_routes, v6_routes


class GetNLRI:
    """Retrieve detailed BGP data per Rx route.
    """

    def __init__(self, connection, routes_list, asn):
        """
        Args:
            connection: Napalm connection to global agg router (must be junos).
            routes_list (list): List of routes to pass to global agg router.
            asn (str): For static only.
        """

        self.connection = connection
        self.routes_list = routes_list
        self.asn = asn

    def get_bgp_nlri(self):
        """
        Returns:
            (dict): IPv4/IPv6 route data: Next-Hop, AS Path, LocalPref, Metric, and Communities for each Rx route. 
        """

        v4_route_dict = {}
        v6_route_dict = {}

        for index, address_type in enumerate(self.routes_list):
            if address_type:
                for route in address_type:

                    try:
                        route_json = self.connection.get_route_to(route,'bgp')

                        if self.asn:
                            aspath = self.asn
                        else:
                            aspath = route_json[route][0]['protocol_attributes']['as_path'].split(' \n')[0]

                        route_dict = {
                            route: {
                                'Next-Hop': route_json[route][0]['next_hop'],
                                'AS Path': aspath,
                                'LocalPref': route_json[route][0]['protocol_attributes']['local_preference'],
                                'Metric': route_json[route][0]['protocol_attributes']['metric'],
                                'Communities': route_json[route][0]['protocol_attributes']['communities']
                            }
                        }

                        if index == 0: v4_route_dict.update(route_dict)
                        else: v6_route_dict.update(route_dict)

                    except:
                        print(f'\nManually check: {route}.\n')

            else:
                if index == 0: v4_route_dict = 'No Rx Routes'
                else: v6_route_dict = 'No Rx Routes'

        return v4_route_dict, v6_route_dict