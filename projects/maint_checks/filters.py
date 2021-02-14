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