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
        self.parsed_data = {}

        if device_type == 'iosxr':
            self.parsed_data = self.rpc_to_dict()

        elif device_type == 'junos':
            self.parsed_data = etree_to_dict(self.data)

    def rpc_to_dict(self):

        self.parsed_data = xmltodict.parse(xml.dom.minidom.parseString(self.data.xml).toprettyxml())

        return self.parsed_data

    def parse_circuit_bgp_xr(self, version=''):

        try:
            full_path = self.parsed_data['rpc-reply']['data']['oc-bgp']['bgp-rib']['afi-safi-table'][f'{version}-unicast']['open-config-neighbors']['open-config-neighbor']
            adv_count = full_path['adj-rib-out-post']['num-routes']['num-routes']
            rx_count = full_path['adj-rib-in-post']['num-routes']['num-routes']

            try:
                routes = {}
                for route in full_path['adj-rib-in-post']['routes']['route']:

                    comm_list = []
                    for community in route['route-attr-list']['community']:
                        comm_list.append(community['objects'])

                    route_nlri_dict = {}
                    route_nlri_dict = {
                        route['route']: {
                            'Next-Hop': route['route-attr-list']['next-hop'][f'{version}-address'],
                            'Local Preference': route['route-attr-list']['local-pref'],
                            'AS-Path': route['route-attr-list']['as-path'],
                            'MED': route['route-attr-list']['med'],
                            'Community': comm_list
                        }
                    }
                    routes.update(route_nlri_dict)

            except:
                routes = 'No prefixes received'

        except:
            adv_count = routes = 'No peering'

        return adv_count, rx_count, routes

    def parse_circuit_default_xr(self, version=''):

        try:
            default = self.parsed_data['rpc-reply']['data']['bgp']['instances']['instance']['instance-active']['default-vrf']['afs']['af']['neighbor-af-table']['neighbor']['af-data']['is-default-originate-sent']

            if default == 'true':
                default = 'Yes'
            else:
                default = 'No'

        except:
            default = 'No peering'

        return default

    def parse_circuit_bgp_junos(self):

        try:
            routes = {}
            full_path = self.parsed_data['route-information']['route-table']['rt']

            if type(full_path) == dict:

                try: lp = full_path['rt-entry']['local-preference']
                except: lp = "Not Set"

                try: med = full_path['rt-entry']['med']
                except: med = "Not Set"

                prefix = full_path['rt-destination'] + '/' + full_path['rt-prefix-length']
                as_path = full_path['rt-entry']['bgp-path-attributes']['attr-as-path-effective']['attr-value']
                community = full_path['rt-entry']['communities']['community']
                next_hop = full_path['rt-entry']['nh']['to']

                routes.update(self.create_routes_dict_junos(prefix, next_hop, lp, as_path, med, community))

            elif type(full_path) == list:

                for route in full_path:

                    try: lp = route['rt-entry']['local-preference']
                    except: lp = "Not Set"

                    try: med = route['rt-entry']['med']
                    except: med = "Not Set"

                    prefix = route['rt-destination'] + '/' + route['rt-prefix-length']
                    as_path = route['rt-entry']['bgp-path-attributes']['attr-as-path-effective']['attr-value']
                    community = route['rt-entry']['communities']['community']
                    next_hop = route['rt-entry']['nh']['to']

                    routes.update(self.create_routes_dict_junos(prefix, next_hop, lp, as_path, med, community))

        except:
            routes = 'No prefixes received'

        return routes

    def create_routes_dict_junos(self, route, nh, lp, asp, med, comm):

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
            if self.parsed_data['route-information']['route-table']['rt']['rt-destination'] == default:
                default = 'Yes'
            else:
                default = 'No'

        except:
            default = 'No'

        return default

    def parse_circuit_bgp_nei_junos(self):

        vrf = self.parsed_data['bgp-information']['bgp-peer']['peer-fwd-rti']
        full_path = self.parsed_data['bgp-information']['bgp-peer']['bgp-rib']

        if type(full_path) == list:

            if full_path[0]['name'] == 'inet.0' or 'inet6.0' or 'hpr.inet.0' or 'hpr.inet6.0':
                adv_count = full_path[0]['advertised-prefix-count']
                rx_count = full_path[0]['accepted-prefix-count']

        elif full_path['name'] == 'inet.0' or 'inet6.0' or 'hpr.inet.0' or 'hpr.inet6.0':
            adv_count = full_path['advertised-prefix-count']
            rx_count = full_path['accepted-prefix-count']

        return adv_count, rx_count, vrf