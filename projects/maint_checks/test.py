from pprint import pprint
import json

with open('output.json', 'r') as pre_file:
    ipv4_nlri = json.load(pre_file)

circuit_nlri_dict = {}
full_path = ipv4_nlri['rpc-reply']['data']['oc-bgp']['bgp-rib']['afi-safi-table']['ipv4-unicast']['open-config-neighbors']['open-config-neighbor']
ipv4_adv_count = full_path['adj-rib-out-post']['num-routes']['num-routes']

routes = {}
route_nlri_dict = {}
for route in full_path['adj-rib-in-post']['routes']['route']:
    comm_list = []
    for community in route['route-attr-list']['community']:
        comm_list.append(community['objects'])


    route_nlri_dict = {
        route['route']: {
            'Origin-Type': route['route-attr-list']['origin-type'],
            'AS-Path': route['route-attr-list']['as-path'],
            'Next-Hop': route['route-attr-list']['next-hop']['ipv4-address'],
            'MED': route['route-attr-list']['med'],
            'Local Preference': route['route-attr-list']['local-pref'],
            'Community': comm_list
        }
    }
    routes.update(route_nlri_dict)
circuit_nlri_dict = {
    'CLR2118': {
        # 'Service': self.service,
        # 'IPv4 Neighbor': self.addresses[0],
        # 'IPv6 Neighbor': self.addresses[1],
        'IPv4 Adv. Count': ipv4_adv_count,
        # 'IPv4 Adv. Default?': ipv4_adv_def,
        # 'IPv6 Adv. Count': ipv6_adv_count,
        # 'IPv6 Adv. Default?': ipv6_adv_def,
        'IPv4 Routes': routes
        # 'IPv6 Routes': global_routes[1]
    }
}
pprint(circuit_nlri_dict)