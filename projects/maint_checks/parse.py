from collections import defaultdict
from lxml import etree
import xml.dom.minidom
import xmltodict
import filters
import re
import textfsm
import tempfile


def etree_to_dict(etree_data):
    # Remove any comments (will cause error on json dump)
    estring = etree.tostring(etree_data)
    parser =  etree.XMLParser(remove_comments=True)
    etree_data = etree.fromstring(estring, parser = parser)

    # created nested dict by magic (???)
    etree_dict = {etree_data.tag: {} if etree_data.attrib else None}
    children = list(etree_data)

    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        etree_dict = {etree_data.tag: {k: v[0] if len(v) == 1 else v
                        for k, v in dd.items()}}
    if etree_data.attrib:
        etree_dict[etree_data.tag].update(('@' + k, v)
                        for k, v in etree_data.attrib.items())
    if etree_data.text:
        text = etree_data.text.strip()
        if children or etree_data.attrib:
            if text:
                etree_dict[etree_data.tag]['#text'] = text
        else:
            etree_dict[etree_data.tag] = text

    return etree_dict

def rpc_to_dict(data):

    return xmltodict.parse(xml.dom.minidom.parseString(data.xml).toprettyxml())


class ParseData:

    def __init__(self, device_type):
        """Parse string (TextFSM) or dict (clean up napalm output) data.

        Args:
            data (str or dict): Data to be parsed
            template (str, optional): Template file for TextFSM. Defaults to ''.
        """

        self.device_type = device_type
        self.addtl_dict = {}
        self.optics_dict = {}

    # pylint: disable=no-self-argument, not-callable
    def to_dict(func):
        def wrapper(self, data):

            if self.device_type == 'junos':
                to_dict = func(self, etree_to_dict(data))
            elif self.device_type == 'iosxr':
                to_dict = func(self, rpc_to_dict(data))

            return to_dict
        return wrapper

    def create_routes_dict(self, route, nh, lp, asp, med, comm):

        route_nlri_dict = {
            route: {
                'Next-Hop': nh,
                'Local Preference': lp,
                'AS-Path': asp,
                'MED': med,
                'Community': comm
            }
        }

        return route_nlri_dict

    # Junos Circuit Parsing

    @to_dict
    def parse_circuit_arp_junos(self, data):

        try: ipv4 = data['arp-table-information']['arp-table-entry']['ip-address']
        except: ipv4 = data['arp-table-information']['arp-table-entry'][0]['ip-address']

        return ipv4

    @to_dict
    def parse_circuit_nd_junos(self, data):

        try: ipv6 = data['ipv6-nd-information']['ipv6-nd-entry'][0]['ipv6-nd-neighbor-address']
        except: ipv6 = None

        return ipv6

    @to_dict
    def parse_circuit_bgp_nei_junos(self, data):

        vrf = data['bgp-information']['bgp-peer']['peer-fwd-rti']
        full_path = data['bgp-information']['bgp-peer']['bgp-rib']

        if type(full_path) == list:

            if full_path[0]['name'] == 'inet.0' or 'inet6.0' or 'hpr.inet.0' or 'hpr.inet6.0':
                adv_count = int(full_path[0]['advertised-prefix-count'])
                rx_count = full_path[0]['accepted-prefix-count']

        elif full_path['name'] == 'inet.0' or 'inet6.0' or 'hpr.inet.0' or 'hpr.inet6.0':
            adv_count = int(full_path['advertised-prefix-count'])
            rx_count = full_path['accepted-prefix-count']

        return adv_count, rx_count, vrf

    @to_dict
    def parse_circuit_bgp_junos_brief(self, data):

        try:
            routes = []
            full_path = data['route-information']['route-table']['rt']

            if type(full_path) == dict:
                routes = [ full_path['rt-destination'] ]

            elif type(full_path) == list:
                for route in full_path:
                    routes.append(route['rt-destination'])

        except:
            'No prefixes recieved'

        return routes

    @to_dict
    def parse_circuit_bgp_junos(self, data):

        full_path = data['route-information']['route-table']['rt']
        route = full_path['rt-destination'] + '/' + full_path['rt-prefix-length']

        try: med = full_path['rt-entry']['metric']
        except: med = "Not set"

        lp = full_path['rt-entry']['local-preference']
        as_path = full_path['rt-entry']['bgp-path-attributes']['attr-as-path-effective']['attr-value'].rstrip(' I')
        community = full_path['rt-entry']['communities']['community']
        next_hop = full_path['rt-entry']['nh']['to']

        route_dict = self.create_routes_dict(route, next_hop, lp, as_path, med, community)

        return route_dict

    @to_dict
    def parse_circuit_default_junos(self, data):

        try:
            if data['route-information']['route-table']['rt']['rt-destination'] == '0.0.0.0/0' or '::/0':
                default = 'Yes'
            else: default = 'No'

        except: default = 'No'

        return default

    # XR Circuit Parsing

    @to_dict
    def parse_circuit_arp_xr(self, data):

        try:
            for ip in data['rpc-reply']['data']['arp']['nodes']['node']['entries']['entry']:
                if ip['state'] == 'state-dynamic':
                    ipv4 = ip['address']
        except: ipv4 = None

        return ipv4

    @to_dict
    def parse_circuit_nd_xr(self, data):

        try:
            for ip in data['rpc-reply']['data']['ipv6-node-discovery']['nodes']['node']['neighbor-interfaces']['neighbor-interface']['host-addresses']['host-address']:
                if ip['is-router'] == 'true' and not ip['host-address'].startswith('fe80'):
                    ipv6 = ip['host-address']
        except: ipv6 = None

        return ipv6

    @to_dict
    def parse_vrf_iface_xr(self, data):

        iface_list = []
        for iface in data['rpc-reply']['data']['l3vpn']['vrfs']['vrf']['interface']:
            iface_list.append(iface['interface-name'])

        return iface_list

    @to_dict
    def parse_circuit_bgp_xr(self, data):

        try:
            for table in data['rpc-reply']['data']['oc-bgp']['bgp-rib']['afi-safi-table'].keys():
                version = re.match('(ipv(4|6))-unicast', table).groups()[0]

            full_path = data['rpc-reply']['data']['oc-bgp']['bgp-rib']['afi-safi-table'][f'{version}-unicast']['open-config-neighbors']['open-config-neighbor']
            adv_count = int(full_path['adj-rib-out-post']['num-routes']['num-routes'])
            rx_count = full_path['adj-rib-in-post']['num-routes']['num-routes']

            try:
                rx_routes = {}
                if type(full_path['adj-rib-in-post']['routes']['route']) == list:
                    for route in full_path['adj-rib-in-post']['routes']['route']:
                        path = route['route-attr-list']
                        nh, lp, asp, med, comm = self.parse_circuit_bgp_xr_routes(path, version)
                        rx_routes.update(self.create_routes_dict(route['route'], nh, lp, asp, med, comm ))

                else:
                    route = full_path['adj-rib-in-post']['routes']['route']
                    nh, lp, asp, med, comm = self.parse_circuit_bgp_xr_routes(route['route-attr-list'], version)
                    rx_routes.update(self.create_routes_dict(route['route'], nh, lp, asp, med, comm ))

            except:
                rx_routes = 'No prefixes received'

        except:
            rx_count = rx_routes = 'No peering'
            adv_count = None

        return rx_routes, adv_count, rx_count

    @to_dict
    def parse_circuit_default_xr(self, data):

        try:
            default = data['rpc-reply']['data']['bgp']['instances']['instance']['instance-active']['default-vrf']['afs']['af']['neighbor-af-table']['neighbor']['af-data']['is-default-originate-sent']

            if default == 'true': default = 'Yes'
            else: default = 'No'

        except: default = 'No peering'

        return default

    def parse_circuit_bgp_xr_routes(self, path, version):

        comm = []
        for community in path['community']: comm.append(community['objects'])
        nh = path['next-hop'][f'{version}-address']
        lp = path['local-pref']
        asp = path['as-path']
        med = path['med']

        return nh, lp, asp, med, comm

    # Junos device parsing

    @to_dict
    def device_power_junos(self, data):
        """Return nested dict from dict of get_power_usage_information_detail RPC call

        Returns:
            dict: status, capacity
        """

        pem_dict = {}
        for pem in data['power-usage-information']['power-usage-item']:
            try:
                in_stat = pem['dc-input-detail2']['dc-input-status']
            except:
                in_stat = pem['dc-input-detail']['dc-input']

            power_dict = {
                pem['name']: {
                    'Status': pem['state'],
                    'Input Status': in_stat,
                    'Capacity': pem['pem-capacity-detail']['capacity-actual'],
                }
            }
            pem_dict.update(power_dict)

        return pem_dict

    @to_dict
    def device_bgp_junos(self, data):
        """Return nested dict from dict of get_bgp_summary_information RPC call

        Returns:
            dict: peer, state, accepted prefixes
        """

        bgp_dict = {}
        for peer in data['bgp-information']['bgp-peer']:

            if type(peer['peer-state']) == dict:

                if type(peer['bgp-rib']) == list:
                    pref = peer['bgp-rib'][0]['accepted-prefix-count']
                elif type(peer['bgp-rib']) == dict:
                    pref = peer['bgp-rib']['accepted-prefix-count']

                try:
                    desc = peer['description']
                except:
                    desc = 'None'

                nei_dict = {
                    peer['peer-address']: {
                        'Description': desc,
                        'Peer AS': peer['peer-as'],
                        'State': peer['peer-state']['@format'],
                        'Accepted Prefixes': pref
                    }
                }

            bgp_dict.update(nei_dict)

        return bgp_dict

    @to_dict
    def device_isis_junos(self, data):
        """Return nested dict from dict of get_isis_adjacency_information RPC call

        Returns:
            dict: name, port, state
        """

        isis_dict = {}
        for peer in data['isis-adjacency-information']['isis-adjacency']:
            nei_dict = {
                peer['system-name']: {
                    'Port': peer['interface-name'],
                    'State': peer['adjacency-state']
                }
            }
            isis_dict.update(nei_dict)

        return isis_dict

    @to_dict
    def device_msdp_junos(self, data):
        """Return nested dict from dict of get_msdp_information RPC call

        Returns:
            dict: peer, local-address, state, group
        """

        msdp_dict = {}
        for peer in data['msdp-peer-information']['msdp-peer']:
            if peer['msdp-state'] == 'Established':
                nei_dict = {
                    peer['msdp-peer-address']: {
                        'Local Address': peer['msdp-local-address'],
                        'State': peer['msdp-state'],
                        'Group': peer['msdp-group-name']
                    }
                }
                msdp_dict.update(nei_dict)

        return msdp_dict

    @to_dict
    def device_pim_junos(self, data):
        """Return nested dict from dict of get_pim_neighbors_information RPC call

        Returns:
            dict: peer, local-address, state, group
        """

        pim_dict = {}
        for neighbor in data['pim-neighbors-information']['pim-interface']:
            try:
                nei_dict = {
                    neighbor['pim-neighbor']['pim-interface-name']: {
                        'Neighbor': neighbor['pim-neighbor']['pim-neighbor-address']
                    }
                }
                pim_dict.update(nei_dict)
            except:
                pass

        return pim_dict

    @to_dict
    def device_optics_junos(self, data):
        """Return nested dict from dict of get_interface_optics_diagnostics_information RPC call

        Returns:
            dict: Tx/Rx Power (dbm)
        """

        for port in data['interface-information']['physical-interface']:

            all_lane_dict = {}
            if type(port['optics-diagnostics']['optics-diagnostics-lane-values']) == list:
                for lane in port['optics-diagnostics']['optics-diagnostics-lane-values']:
                    lane_num = lane['lane-index']
                    lane_dict = {
                        f'Lane {lane_num}': {
                            'Rx Power': lane['laser-rx-optical-power-dbm']+'dBm',
                            'Tx Power': lane['laser-output-power-dbm']+'dBm'
                        }
                    }
                    all_lane_dict.update(lane_dict)

            else:
                lane_num = port['optics-diagnostics']['optics-diagnostics-lane-values']['lane-index']
                all_lane_dict = {
                    f'Lane {lane_num}': {
                        'Rx Power': port['optics-diagnostics']['optics-diagnostics-lane-values']['laser-rx-optical-power-dbm']+'dBm',
                        'Tx Power': port['optics-diagnostics']['optics-diagnostics-lane-values']['laser-output-power-dbm']+'dBm'
                    }
                }
            optic_dict = {
                port['name']: all_lane_dict
            }
            self.optics_dict.update(optic_dict)

        # return optics_dict

    @to_dict
    def device_iface_junos(self, data):
        """Return nested dict from dict of get_interface_information RPC call

        Returns:
            dict: name, errors, optics
        """

        iface_dict = {}
        for port in data['interface-information']['physical-interface']:
            try:
                desc = port['description']
            except:
                desc = 'No description'

            if port['oper-status'] == 'up' and port['name'].startswith(('xe', 'et', 'ge')):
                port_dict = {
                    port['name']: {
                        'Description': desc,
                        'Errors': {
                            'Rx Errors': port['input-error-list']['input-errors'],
                            'Rx Drops': port['input-error-list']['input-drops'],
                            'Tx Errors': port['output-error-list']['output-errors'],
                            'Tx Drops': port['output-error-list']['output-drops']},
                        'Optics PMs': self.optics_dict[port['name']]
                    }
                }
                iface_dict.update(port_dict)

        return iface_dict

    @to_dict
    def device_isis_xr(self, data):

        id_name_dict = {}
        for neighbor in data['rpc-reply']['data']['isis']['instances']['instance']['host-names']['host-name']:
            id_name_list  = list(neighbor.values())
            nei = { id_name_list[0]: id_name_list[1] }
            id_name_dict.update(nei)

        isis_dict = {}
        for neighbor in data['rpc-reply']['data']['isis']['instances']['instance']['neighbors']['neighbor']:
            if neighbor['neighbor-state'] == 'isis-adj-up-state': state = 'Up'
            else: state = 'Down'

            nei_dict = {
                id_name_dict[neighbor['system-id']]: {
                    'Port': neighbor['interface-name'],
                    'State': state
                }
            }
            isis_dict.update(nei_dict)

        return isis_dict

    @to_dict
    def device_pim_xr(self, data):

        pim_dict = {}
        for neighbor in data['rpc-reply']['data']['pim']['active']['default-context']['neighbor-old-formats']['neighbor-old-format']:
            nei_dict = {
                neighbor['interface-name']: {
                    'Neighbor': neighbor['neighbor-address']
                }
            }
            pim_dict.update(nei_dict)

        return pim_dict