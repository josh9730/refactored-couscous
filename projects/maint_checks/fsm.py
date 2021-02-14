""" TextFSM templates
"""

template_10k_bgp = r"""Value Peer (\S+)
Value State (Establ)
Value Accepted (\d+)
Start
 ^${Peer}(\s+\S+){5}\s+(\S+\s+){0,1}\S+\s${State}
 ^\s+(hpr\.){0,1}inet\.(0|6):\s\d+\/\d+\/${Accepted} -> Record
"""

template_junos_isis_status = r"""Value Port (\S+)
Value Neighbor (\S+)
Value Status (\S+)
Start
 ^${Port}\s+${Neighbor}\s+\d\s+${Status} -> Record
"""

template_xr_isis_status = r"""Value Neighbor (\S+)
Value Port (\S+)
Value State (\S+)
Start
 ^${Neighbor}\s+${Port}\s+\W\S+\W+${State} -> Record
"""

template_junos_pim_msdp = r"""Value Port (\S+\d)
Start
 ^${Port} -> Record
"""

template_xr_msdp = r"""Value Peer (\S+)
Start
 ^\s${Peer}\s+\d+\s+Established -> Record
"""

template_junos_adv = r"""Value Count (\d+)
Start
 ^\s+Advertised\sprefixes:\s+${Count} -> Record
"""

template_static = r"""Value Prefix (([a-z0-9]*[.:]*)*\/\d{2})
Start
 ^\D{0,2}${Prefix} -> Record
"""

template_bgp_rx = r"""Value Prefix (([a-z0-9]*[.:]*)*\/\d{1,2})
Start
 ^\D{0,3}${Prefix} -> Record
"""

template_xr_bgp_default = r"""Value Sent (default\ssent)
Start
 ^([a-zA-z]|\s|:|-)*,\s${Sent} -> Record
"""

template_xr_adv = r"""Value Count (\d+)
Start
 ^No\sof\sprefixes\sAdvertised:\s${Count} -> Record
"""

template_xr_bgp_hpr = r"""Value HPR (\S+)
Start
 ^VRF: ${HPR} -> Record
 """

template_junos_bgp_hpr = r"""Value VRF (\S+)
Start
 ^\s+Group:\s\S+\s+Routing-Instance:\s${VRF} -> Record
"""