from parse import ParseData
import fsm

class GetNeighborRoutes:
    """Retrieves routes per 'circuit'. Gets:
    1. Recieved routes from neighbor (bgp only).
    2. Advertised count from neighbor (bgp only).
    3. Check if default route sent (bgp only).
    4. All routes with tagged ASN (static only).
    """

    def __init__(self, connection, circuit):
        """
        Args:
            connection: napalm connection to agg router.
            circuit (dict): Contains IPs, device types, service, port strings.
        """

        self.connection = connection
        self.circuit = circuit
        self.rx_routes = self.adv_count = self.default = None
        try:
            self.addresses = [self.circuit['ipv4_neighbor'], self.circuit['ipv6_neighbor']]
        except:
            pass

    def get_xr_bgp_routes(self):
        """For XR Agg routers only.

        Returns:
            (list): v4 and v6 output lists
        """

        hpr = self.connection.cli(['show vrf hpr'])
        if hpr['show vrf hpr']:
            vrf = 'vrf all '
        else:
            vrf = ''

        for index, address in enumerate(self.addresses):
            if index == 0:
                version = 'ipv4'
            else:
                version = 'ipv6'

            if address:
                print('getting routes')
                xr_rx_routes = f'show bgp {vrf}{version} unicast neighbor {address} routes'
                xr_adv_count = f'show bgp {vrf}{version} unicast neighbor {address} advertised-count'
                xr_default = f'show bgp {vrf}{version} unicast neighbor {address} | include Default'

                pull_bgp = self.connection.cli([xr_rx_routes, xr_adv_count, xr_default])

                self.rx_routes = ParseData(pull_bgp[xr_rx_routes], template=fsm.template_bgp_rx).parse_FSM()
                if len(self.rx_routes) == 0: self.rx_routes = None

                try:
                    if ParseData(pull_bgp[xr_default], template=fsm.template_xr_bgp_default).parse_FSM()[0]:
                        self.default = 'Default Sent'
                except:
                    self.default = 'Default Not Sent'

                try:
                    self.adv_count = int(ParseData(pull_bgp[xr_adv_count], template=fsm.template_xr_adv).parse_FSM()[0])
                    if self.adv_count > 800000 and vrf == '' and index == 0:
                        self.adv_count = 'Full DC Table'
                    elif self.adv_count > 100000 and vrf == '' and index == 1:
                        self.adv_count = 'Full DC Table'
                except:
                    self.adv_count = 'No TX Routes'

            if index == 0:
                self.v4_list = [self.rx_routes, self.adv_count, self.default]
                self.rx_routes = self.adv_count = self.default = None
            else:
                self.v6_list = [self.rx_routes, self.adv_count, self.default]

        return self.v4_list, self.v6_list

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

                self.rx_routes = ParseData(pull_bgp[junos_rx_routes], template=fsm.template_bgp_rx).parse_FSM()
                self.adv_count = ParseData(pull_bgp[junos_adv_count], template=fsm.template_junos_adv).parse_FSM()
                self.default = ParseData(pull_bgp[junos_default], template=fsm.template_bgp_rx).parse_FSM()

                if len(self.adv_count) > 0: self.adv_count = self.adv_count[0]
                if len(self.rx_routes) == 0: self.rx_routes = None

                try:
                    if index == 0:
                        if self.default[0] == '0.0.0.0/0' or self.default[0] == ':/0':
                            self.default = 'Default Sent'
                except:
                    self.default = 'Default Not Sent'

            if index == 0:
                self.v4_list = [self.rx_routes, self.adv_count, self.default]
                self.rx_routes = self.adv_count = self.default = None
            else:
                self.v6_list = [self.rx_routes, self.adv_count, self.default]

        return self.v4_list, self.v6_list

    def get_static_routes(self, device_type):
        """For static only. Requires ASN tag (may not always be tagged).

        Args:
            device_type: Junos or IOS-XR

        Returns:
            (list): List of v4/v6 static routes tagged with ASN
        """
        self.device_type = device_type
        self.v4_routes = self.v6_routes = None
        self.asn = self.circuit['asn']

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
            self.routes = ParseData(pull_static[static], template=fsm.template_static).parse_FSM()

            if index == 0:
                self.v4_routes = self.routes
                self.routes = None
            else:
                self.v6_routes = self.routes

        return self.v4_routes, self.v6_routes


class GetRouteData:
    """Retrieve detailed BGP data per Rx route.
    """

    def __init__(self, connection, routes_list):
        """
        Args:
            connection: Napalm connection to global agg router (must be junos).
            routes_list (list): List of routes to pass to global agg router.
        """
        self.connection = connection
        self.routes_list = routes_list

    def get_bgp_nlri(self):
        """
        Returns:
            (dict): IPv4/IPv6 route data: Next-Hop, AS Path, LocalPref, Metric, and Communities for each Rx route. 
        """
        self.v4_route_dict = {}
        self.v6_route_dict = {}

        for index, address_type in enumerate(self.routes_list):
            print('getting NLRIs')
            if address_type:
                for route in address_type:

                    try:
                        route_json = self.connection.get_route_to(route,'bgp')
                        route_dict = {
                            route: {
                                'Next-Hop': route_json[route][0]['next_hop'],
                                'AS Path': route_json[route][0]['protocol_attributes']['as_path'].split(' \n')[0],
                                'LocalPref': route_json[route][0]['protocol_attributes']['local_preference'],
                                'Metric': route_json[route][0]['protocol_attributes']['metric'],
                                'Communities': route_json[route][0]['protocol_attributes']['communities']
                            }
                        }

                        if index == 0: self.v4_route_dict.update(route_dict)
                        else: self.v6_route_dict.update(route_dict)

                    except:
                        print(f'\nManually check: {route}.\n')

            else:
                if index == 0: self.v4_route_dict = 'No Rx Routes'
                else: self.v6_route_dict = 'No Rx Routes'

        return self.v4_route_dict, self.v6_route_dict