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


class ParseData:

    def __init__(self, data,  device_type):
        """Parse string (TextFSM) or dict (clean up napalm output) data.

        Args:
            data (str or dict): Data to be parsed
            template (str, optional): Template file for TextFSM. Defaults to ''.
        """

        self.data = data
        self.device_type = device_type
        self.parsed_data = {}

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

    def parse_vrf_iface_xr(self):

        iface_list = []
        for iface in self.dict_data['rpc-reply']['data']['l3vpn']['vrfs']['vrf']['interface']:
            iface_list.append(iface['interface-name'])

        return iface_list

    def parse_circuit_bgp_xr(self, version=''):

        try:
            full_path = self.dict_data['rpc-reply']['data']['oc-bgp']['bgp-rib']['afi-safi-table'][f'{version}-unicast']['open-config-neighbors']['open-config-neighbor']
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
                adv_count = int(full_path[0]['advertised-prefix-count'])
                rx_count = full_path[0]['accepted-prefix-count']

        elif full_path['name'] == 'inet.0' or 'inet6.0' or 'hpr.inet.0' or 'hpr.inet6.0':
            adv_count = int(full_path['advertised-prefix-count'])
            rx_count = full_path['accepted-prefix-count']

        return adv_count, rx_count, vrf

    def parse_device_bgp_junos(self):
        """Return nested dict from dict of get_bgp_summary_information RPC call

        Returns:
            dict: peer, state, accepted prefixes
        """

        for peer in self.dict_data['bgp-information']['bgp-peer']:

            if type(peer['peer-state']) == dict:

                if type(peer['bgp-rib']) == list:
                    pref = peer['bgp-rib'][0]['accepted-prefix-count']
                elif type(peer['bgp-rib']) == dict:
                    pref = peer['bgp-rib']['accepted-prefix-count']

                try:
                    desc = peer['description']
                except:
                    desc = 'None'

                bgp_dict = {
                    peer['peer-address']: {
                        'Description': desc,
                        'Peer AS': peer['peer-as'],
                        'State': peer['peer-state']['@format'],
                        'Accepted Prefixes': pref
                    }
                }

            self.parsed_data.update(bgp_dict)

        return self.parsed_data

    def parse_device_isis_junos(self):
        """Return nested dict from dict of get_isis_adjacency_information RPC call

        Returns:
            dict: name, port, state
        """

        for peer in self.dict_data['isis-adjacency-information']['isis-adjacency']:
            isis_dict = {
                peer['system-name']: {
                    'Port': peer['interface-name'],
                    'State': peer['adjacency-state']
                }
            }

            self.parsed_data.update(isis_dict)

        return self.parsed_data

    def parse_device_msdp_junos(self):
        """Return nested dict from dict of get_msdp_information RPC call

        Returns:
            dict: peer, local-address, state, group
        """

        for peer in self.dict_data['msdp-peer-information']['msdp-peer']:
            if peer['msdp-state'] == 'Established':
                msdp_dict = {
                    peer['msdp-peer-address']: {
                        'Local Address': peer['msdp-local-address'],
                        'State': peer['msdp-state'],
                        'Group': peer['msdp-group-name']
                    }
                }
                self.parsed_data.update(msdp_dict)

        return self.parsed_data

    def parse_device_pim_junos(self):
        """Return nested dict from dict of get_pim_neighbors_information RPC call

        Returns:
            dict: peer, local-address, state, group
        """

        for neighbor in self.data['pim-neighbors-information']['pim-interface']:
            try:
                pim_dict = {
                    neighbor['pim-neighbor']['pim-interface-name']: {
                        'Neighbor': neighbor['pim-neighbor']['pim-neighbor-address']
                    }
                }
                self.parsed_data.update(pim_dict)
            except:
                pass

        return self.parsed_data

    def parse_device_optics_junos(self):
        """Return nested dict from dict of get_interface_optics_diagnostics_information RPC call

        Returns:
            dict: Tx/Rx Power (dbm)
        """

        for port in self.dict_data['interface-information']['physical-interface']:
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
            optics_dict = {
                port['name']: all_lane_dict
            }
            self.parsed_data.update(optics_dict)

        return self.parsed_data

    def parse_device_iface_junos(self, optics_dict):
        """Return nested dict from dict of get_interface_information RPC call

        Returns:
            dict: name, errors, optics
        """

        for port in self.dict_data['interface-information']['physical-interface']:
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
                        'Optics PMs': optics_dict[port['name']]
                    }
                }
                self.parsed_data.update(port_dict)

        return self.parsed_data

    def parse_device_power_junos(self):
        """Return nested dict from dict of get_power_usage_information_detail RPC call

        Returns:
            dict: status, capacity
        """

        for pem in self.dict_data['power-usage-information']['power-usage-item']:
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
            self.parsed_data.update(power_dict)

        return self.parsed_data