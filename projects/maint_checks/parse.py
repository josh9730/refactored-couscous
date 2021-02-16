from collections import defaultdict
from lxml import etree
import xml.dom.minidom
import xmltodict
import filters
import re

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


class ParseData:

    def __init__(self, data, device_type):
        """Parse string (TextFSM) or dict (clean up napalm output) data.

        Args:
            data (str or dict): Data to be parsed
            template (str, optional): Template file for TextFSM. Defaults to ''.
        """

        self.data = data
        self.device_type = device_type
        # self.dict_data = {}

        if device_type == 'iosxr':
            self.rpc_to_dict()

        elif device_type == 'junos':
            self.dict_data = etree_to_dict(self.data)

    def rpc_to_dict(self):

        self.dict_data = xmltodict.parse(xml.dom.minidom.parseString(self.data.xml).toprettyxml())

    def parse_circuit_arp_junos(self):

        try: ipv4 = self.dict_data['arp-table-information']['arp-table-entry']['ip-address']
        except: ipv4 = self.dict_data['arp-table-information']['arp-table-entry'][0]['ip-address']

        return ipv4

    def parse_circuit_nd_junos(self):

        try: ipv6 = self.dict_data['ipv6-nd-information']['ipv6-nd-entry'][0]['ipv6-nd-neighbor-address']
        except: ipv6 = None

        return ipv6

    def parse_circuit_arp_xr(self):

        try:
            for ip in self.dict_data['rpc-reply']['data']['arp']['nodes']['node']['entries']['entry']:
                if ip['state'] == 'state-dynamic':
                    ipv4 = ip['address']
        except: ipv4 = None

        return ipv4

    def parse_circuit_nd_xr(self):

        try:
            for ip in self.dict_data['rpc-reply']['data']['ipv6-node-discovery']['nodes']['node']['neighbor-interfaces']['neighbor-interface']['host-addresses']['host-address']:
                if ip['is-router'] == 'true' and not ip['host-address'].startswith('fe80'):
                    ipv6 = ip['host-address']
        except: ipv6 = None

        return ipv6

    def parse_circuit_bgp_xr(self, version=''):

        try:
            full_path = self.dict_data['rpc-reply']['data']['oc-bgp']['bgp-rib']['afi-safi-table'][f'{version}-unicast']['open-config-neighbors']['open-config-neighbor']
            adv_count = full_path['adj-rib-out-post']['num-routes']['num-routes']
            rx_count = full_path['adj-rib-in-post']['num-routes']['num-routes']

            try:
                routes = {}
                if type(full_path['adj-rib-in-post']['routes']['route']) == list:
                    for route in full_path['adj-rib-in-post']['routes']['route']:
                        path = route['route-attr-list']
                        nh, lp, asp, med, comm = self.parse_circuit_bgp_xr_routes(path, version)
                        routes.update(self.create_routes_dict(route['route'], nh, lp, asp, med, comm ))

                else:
                    route = full_path['adj-rib-in-post']['routes']['route']
                    nh, lp, asp, med, comm = self.parse_circuit_bgp_xr_routes(route['route-attr-list'], version)
                    routes.update(self.create_routes_dict(route['route'], nh, lp, asp, med, comm ))

            except:
                routes = 'No prefixes received'

        except:
            adv_count = rx_count = routes = 'No peering'

        return adv_count, rx_count, routes

    def parse_circuit_bgp_xr_routes(self, path, version):

        comm = []
        for community in path['community']: comm.append(community['objects'])
        nh = path['next-hop'][f'{version}-address']
        lp = path['local-pref']
        asp = path['as-path']
        med = path['med']

        return nh, lp, asp, med, comm

    def parse_circuit_default_xr(self, version=''):

        try:
            default = self.dict_data['rpc-reply']['data']['bgp']['instances']['instance']['instance-active']['default-vrf']['afs']['af']['neighbor-af-table']['neighbor']['af-data']['is-default-originate-sent']

            if default == 'true':
                default = 'Yes'
            else:
                default = 'No'

        except:
            default = 'No peering'

        return default

    def parse_circuit_bgp_junos(self, route):

        full_path = self.dict_data['route-information']['route-table']['rt']['rt-entry']
        lp = full_path['local-preference']
        try: med = full_path['metric']
        except: med = "Not set"
        as_path = full_path['bgp-path-attributes']['attr-as-path-effective']['attr-value'].rstrip(' I')
        community = full_path['communities']['community']
        next_hop = full_path['nh']['to']

        route_dict = self.create_routes_dict(route, next_hop, lp, as_path, med, community)

        return route_dict

    def parse_circuit_bgp_brief(self):

        try:
            routes = []
            full_path = self.dict_data['route-information']['route-table']['rt']

            if type(full_path) == dict:
                routes = [ full_path['rt-destination'] ]

            elif type(full_path) == list:
                for route in full_path:
                    routes.append(route['rt-destination'])

        except:
            'No prefixes recieved'

        return routes

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

    def parse_circuit_default_junos(self, default=''):

        try:
            if self.dict_data['route-information']['route-table']['rt']['rt-destination'] == default:
                default = 'Yes'
            else:
                default = 'No'

        except:
            default = 'No'

        return default

    def parse_circuit_bgp_nei_junos(self):

        vrf = self.dict_data['bgp-information']['bgp-peer']['peer-fwd-rti']
        full_path = self.dict_data['bgp-information']['bgp-peer']['bgp-rib']

        if type(full_path) == list:

            if full_path[0]['name'] == 'inet.0' or 'inet6.0' or 'hpr.inet.0' or 'hpr.inet6.0':
                adv_count = full_path[0]['advertised-prefix-count']
                rx_count = full_path[0]['accepted-prefix-count']

        elif full_path['name'] == 'inet.0' or 'inet6.0' or 'hpr.inet.0' or 'hpr.inet6.0':
            adv_count = full_path['advertised-prefix-count']
            rx_count = full_path['accepted-prefix-count']

        return adv_count, rx_count, vrf