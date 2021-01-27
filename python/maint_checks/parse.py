from collections import defaultdict
from lxml import etree
import tempfile
import textfsm
import fsm
import re

def etree_to_dict(etree_data):
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

    def __init__(self, data, template='', device_type=''):
        """Parse string (TextFSM) or dict (clean up napalm output) data.

        Args:
            data (str or dict): Data to be parsed
            template (str, optional): Template file for TextFSM. Defaults to ''.
        """

        self.data = data
        self.template = template
        self.device_type = device_type
        self.parsed_data = {}

    def parse_FSM(self):
        """Assigns the passed template to a temporary file, parses with TextFSM, and then closes the file.

        Returns:
            fsm_results_flat: parsed output of text
        """

        tmp = tempfile.NamedTemporaryFile()
        with open(tmp.name, 'w') as f:
            f.write(self.template)

        with open(tmp.name, 'r') as f:
            fsm = textfsm.TextFSM(f)
            fsm_results = fsm.ParseText(self.data)

        fsm_results_flat = [val for sublist in fsm_results for val in sublist] # flatten list of lists

        return fsm_results_flat

    def parse_isis_xr(self):
        """Parse ISIS data and return dict of needed output.

        Args:
            device_type (str): junos or iosxr

        Returns:
            dict: Port: { Neighbor, Status}
        """

        isis_list = self.data.split('\n')

        for i in isis_list:
            isis_parsed = ParseData(i, template=fsm.template_xr_isis_status).parse_FSM()
            isis_dict = {
                isis_parsed[0]: {
                    'Port': isis_parsed[1],
                    'Status': isis_parsed[2]
                }
            }
            self.parsed_data.update(isis_dict)

        return self.parsed_data

    def parse_optics_napalm_junos(self):
        """Parse and return dict with only Rx/Tx per lane. Only supported on Junos currently.

        Returns:
            dict: Rx/Tx per lane.
        """

        for port in self.data:
            all_lane_dict = {}
            for lane in self.data[port]['physical_channels']['channel']:
                lane_num = lane['index']
                lane_dict = {
                    f'Lane {lane_num}': {
                        'Rx': lane['state']['input_power']['instant'],
                        'Tx': lane['state']['output_power']['instant']
                    }
                }
                all_lane_dict.update(lane_dict)

            port_dict = {
                port: all_lane_dict
            }
            self.parsed_data.update(port_dict)

        return self.parsed_data

    def parse_iface_xr(self, iface_counters, optics_dict=None):
        """Parse Interface output for interesting ports, return nested dict and add Optics dict per port (if available)

        Args:
            iface_counters (dict): Contains all counters per port
            optics_dict (dict, optional): Napalm output of optics PMs. Only supported on Junos currently. Defaults to ''.

        Returns:
            dict: Contains Port PMs + Optics PMs if available.
        """

        for i in self.data:
            if self.data[i]['is_up'] == True and not i.startswith('Loop'):

                if optics_dict:
                    optics = optics_dict[i]
                else:
                    optics = 'Not supported on IOS-XR'

                iface_dict = {
                    i: {
                        'Description': self.data[i]['description'],
                        'Errors': {
                            'Tx Discards': iface_counters[i]['tx_discards'],
                            'Rx Discards': iface_counters[i]['rx_discards'],
                            'Tx Errors': iface_counters[i]['tx_errors'],
                            'Rx Errors': iface_counters[i]['rx_errors']},
                        'Optic PMs': optics
                    }
                }
                self.parsed_data.update(iface_dict)

        return self.parsed_data


    def parse_bgp_xr(self):
        """Parse raw BGP data - string if junos with HPR and dict if XR. Junos with HPR does not support BGP getter.

        Args:
            network (str, optional): Only needed for Junos. Defaults to None.

        Returns:
            dict: Interesting BGP data
        """
        for i in self.data:
            for j in self.data[i]['peers']:

                bgp_nei = {
                    j: {
                        'Remote AS': self.data[i]['peers'][j]['remote_as'],
                        'Up': self.data[i]['peers'][j]['is_up'],
                        'Description': self.data[i]['peers'][j]['description'],
                        'Prefixes': self.data[i]['peers'][j]['address_family']
                    }
                }

                try:
                    bgp_nei[j]['Prefixes']['ipv4']['sent_prefixes'] = 'Not Supported'
                except:
                    pass
                try:
                    bgp_nei[j]['Prefixes']['ipv6']['sent_prefixes'] = 'Not Supported'
                except:
                    pass

                self.parsed_data.update(bgp_nei)

        return self.parsed_data

    def parse_bgp_junos(self):
        """Return nested dict from dict of get_bgp_summary_information RPC call

        Returns:
            dict: peer, state, accepted prefixes
        """

        for peer in self.data['bgp-information']['bgp-peer']:
            try:
                if peer['peer-state']['@format'] == 'Establ':

                    if type(peer['bgp-rib']) == list:
                        pref = peer['bgp-rib'][0]['accepted-prefix-count']
                    elif type(peer['bgp-rib']) == dict:
                        pref = peer['bgp-rib']['accepted-prefix-count']

                    bgp_dict = {
                        peer['peer-address']: {
                            'Description': peer['description'],
                            'State': peer['peer-state']['@format'],
                            'Accepted Prefixes': pref
                        }
                    }
                self.parsed_data.update(bgp_dict)

            except:
                pass

        return self.parsed_data

    def parse_isis_junos(self):
        """Return nested dict from dict of get_isis_adjacency_information RPC call

        Returns:
            dict: name, port, state
        """

        for peer in self.data['isis-adjacency-information']['isis-adjacency']:
            isis_dict = {
                peer['system-name']: {
                    'Port': peer['interface-name'],
                    'State': peer['adjacency-state']
                }
            }

            self.parsed_data.update(isis_dict)

        return self.parsed_data

    def parse_msdp_junos(self):
        """Return nested dict from dict of get_msdp_information RPC call

        Returns:
            dict: peer, local-address, state, group
        """

        for peer in self.data['msdp-peer-information']['msdp-peer']:
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

    def parse_pim_junos(self):
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

    def parse_optics_junos(self):
        """Return nested dict from dict of get_interface_optics_diagnostics_information RPC call

        Returns:
            dict: Tx/Rx Power (dbm)
        """

        for port in self.data['interface-information']['physical-interface']:
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

    def parse_iface_junos(self, optics_dict):
        """Return nested dict from dict of get_interface_information RPC call

        Returns:
            dict: name, errors, optics
        """

        for port in self.data['interface-information']['physical-interface']:
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

    def parse_power_junos(self):
        """Return nested dict from dict of get_power_usage_information_detail RPC call

        Returns:
            dict: status, capacity
        """

        for pem in self.data['power-usage-information']['power-usage-item']:
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