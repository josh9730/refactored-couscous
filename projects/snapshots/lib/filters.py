"""RPC and TextFSM filters for IOS-XR."""
bgp_routes_filter = """
<filter>
  <oc-bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ipv4-bgp-oc-oper">
  <bgp-rib><afi-safi-table><{version}-unicast><open-config-neighbors><open-config-neighbor>
    <neighbor-address>{neighbor}</neighbor-address>
      <adj-rib-in-post></adj-rib-in-post>
      <adj-rib-out-post><num-routes><num-routes/></num-routes></adj-rib-out-post>
    </open-config-neighbor></open-config-neighbors></{version}-unicast></afi-safi-table></bgp-rib>
  </oc-bgp>
</filter>
"""

bgp_default_filter = """
<filter>
  <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ipv4-bgp-oper">
    <instances><instance><instance-active><default-vrf><afs><af>
      <af-name>{version}-unicast</af-name>
        <neighbor-af-table><neighbor><neighbor-address>{neighbor}</neighbor-address>
      <af-data><af-name>{version}</af-name><is-default-originate-sent/></af-data>
      </neighbor></neighbor-af-table>
    </af></afs></default-vrf></instance-active></instance></instances>
  </bgp>
</filter>
"""

arp = """
<filter>
    <arp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ipv4-arp-oper">
    <nodes><node><node-name>0/0/CPU0</node-name><entries><entry>
      <interface-name>{interface}</interface-name>
        <address/><state/>
    </entry></entries></node></nodes>
    </arp>
</filter>
"""

nd = """
<filter>
  <ipv6-node-discovery xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ipv6-nd-oper">
    <nodes><node><node-name>0/0/CPU0</node-name><neighbor-interfaces><neighbor-interface>
      <interface-name>{interface}</interface-name>
        <host-addresses><host-address>
          <host-address/><is-router/><origin-encapsulation/>
        </host-address></host-addresses>
    </neighbor-interface></neighbor-interfaces></node></nodes>
  </ipv6-node-discovery>
</filter>
"""

xr_vrf = """
<filter>
  <l3vpn xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-mpls-vpn-oper">
    <vrfs><vrf><vrf-name>hpr</vrf-name>
      <interface/>
    </vrf></vrfs>
  </l3vpn>
</filter>
"""

isis_device = """
<filter>
  <isis xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-clns-isis-oper">
    <instances><instance>
      <host-names><host-name>
        <system-id/><host-name/>
      </host-name></host-names>
      <neighbors><neighbor>
        <system-id/><interface-name/><neighbor-state/>
      </neighbor></neighbors>
    </instance></instances>
  </isis>
</filter>
"""

pim_device = """
<filter>
  <pim xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ipv4-pim-oper">
    <active><default-context><neighbor-old-formats><neighbor-old-format>
      <interface-name/><neighbor-address/>
    </neighbor-old-format></neighbor-old-formats></default-context></active>
  </pim>
</filter>
"""

bgp_device = """
<filter>
  <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ipv4-bgp-oper">
    <instances><instance><instance-active><default-vrf><afs><af>
      <af-name>ipv4-unicast</af-name>
      <neighbor-af-table><neighbor>
        <neighbor-address/><remote-as/><description/>
          <connection-state>bgp-st-estab</connection-state>
          <af-data><af-name>ipv4</af-name><prefixes-accepted/></af-data>
      </neighbor></neighbor-af-table>
      </af>
      <af><af-name>ipv6-unicast</af-name>
      <neighbor-af-table><neighbor>
        <neighbor-address/><remote-as/><description/>
          <connection-state>bgp-st-estab</connection-state>
          <af-data><af-name>ipv6</af-name><prefixes-accepted/></af-data>
      </neighbor></neighbor-af-table>
    </af></afs></default-vrf>
    <vrfs><vrf>
      <vrf-name>hpr</vrf-name>
      <neighbors><neighbor>
        <neighbor-address/><remote-as/><description/>
          <connection-state>bgp-st-estab</connection-state>
          <af-data><af-name/><prefixes-accepted/></af-data>
      </neighbor></neighbors>
    </vrf></vrfs></instance-active></instance></instances>
  </bgp>
</filter>
"""

iface_name_circuit = """
<filter>
  <interface-configurations xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ifmgr-cfg">
    <interface-configuration>
      <interface-name>{iface}</interface-name>
  </interface-configuration></interface-configurations>
</filter>
"""

iface_circuit = """
<filter>
  <infra-statistics xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-infra-statsd-oper">
    <interfaces><interface>
      <interface-name>{iface}</interface-name>
      <interfaces-mib-counters>
        <output-drops/><input-drops/><input-errors/><output-errors/>
      </interfaces-mib-counters>
      <data-rate>
        <input-data-rate/><output-data-rate/>
      </data-rate>
    </interface></interfaces>
  </infra-statistics>
</filter>
"""

isis_circuit = """
<filter>
  <isis xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-clns-isis-oper">
    <instances><instance><interfaces><interface>
      <interface-name>{iface}</interface-name>
        <interface-status-and-data><enabled>
          <clns-data><clns-status></clns-status></clns-data>
          <per-topology-data>
            <topology-id><af-name/></topology-id>
            <status><enabled><level2-metric/></enabled></status>
          </per-topology-data>
        </enabled></interface-status-and-data>
    </interface></interfaces></instance></instances>
  </isis>
</filter>
"""

template_bgp_rx = r"""Value Prefix (([a-z0-9]*[.:]*)*\/\d{1,2})

Start
 ^\D{0,3}${Prefix} -> Record
"""

template_xr_adv = r"""Value Count (\d+)

Start
 ^No\sof\sprefixes\sAdvertised:\s${Count} -> Record
"""

template_xr_msdp = r"""Value Peer (\S+)

Start
 ^\s${Peer}\s+\d+\s+Established -> Record
"""