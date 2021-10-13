from nautobot.extras.jobs import *
import netaddr

name = "Misc. Jobs"


class V4toV6(Job):
    """Maintained By: Josh Dickman (jdickman@cenic.org)
       Use flake8 & black for formatting
    """

    class Meta:
        name = "IPv4 to IPv6 Converter"
        description = "Convert IPv4 address to an IPv6 address"
        read_only = True

    v4 = IPAddressWithMaskVar(
        label="IPv4 Address",
        description="IPv4 Address with mask in slash notation",
    )
    NET_CHOICES = (
        ("",""),
        ("dc", "DC"),
        ("hpr", "HPR")
    )
    LINK_CHOICES = (
        ("",""),
        ("int", "Internal Link"),
        ("ext", "External Link")
    )
    net = ChoiceVar(
        label="Network",
        description="Choose which network the IPv4 address is on",
        choices=NET_CHOICES,
    )
    link = ChoiceVar(
        label="Link Type",
        description="Choose type of link. Internal means IPs are only configured on CENIC devices",
        choices=LINK_CHOICES,
    )

    def run(self, data, commit):

        v4_mask = netaddr.IPNetwork(data["v4"]).prefixlen
        v4 = netaddr.IPNetwork(data["v4"]).ip

        if data["link"] == "int":
            link = str(0)
        else:
            link = str(1)

        if data["net"] == "dc":
            net = str(1)
        else:
            net = str(0)

        # convert IP to hex
        v4_hex = hex(netaddr.IPAddress(v4)).lstrip("0x")

        # break into 3 hex 'chunks'
        hex_a = v4_hex[0]
        hex_b = v4_hex[1:5]
        hex_c = v4_hex[5 : len(v4_hex)]

        # convert mask v4 -> v6
        if v4_mask == 32:
            final_mask = "128"
        else:
            final_mask = str(v4_mask + 92)

        # create IPv6 string
        v6_str = f"2607:f380:000{link}:0:0:01{net}{hex_a}:{hex_b}:{hex_c}1"

        # convert IPv6 string to an IPv6 address
        v6 = str(netaddr.IPAddress(v6_str, 6))
        final_addr = v6 + "/" + final_mask

        output = (
            f'**Original IPv4:** `{data["v4"]}`\n\n**Converted IPv6:** `{final_addr}`'
        )
        self.log_success(message=output)

        return output


class PortTag(Job):
    """Maintained By: Josh Dickman (jdickman@cenic.org)
       Use flake8 & black for formatting
    """

    class Meta:
        name = "Interface Tag Generator"
        description = "Generates Interface Tags based on current standard defined: https://documentation.cenic.org/display/Core/Interface+Tag+Standard"
        read_only = True

    SPEED_CHOICES = (
        ("",""),
        ("100m", "100Mb"),
        ("500m", "500Mb"),
        ("1g", "1Gb"),
        ("10g", "10Gb"),
        ("40g", "40Gb"),
        ("100g", "100Gb"),
    )
    NET_CHOICES = (
        ("",""),
        ("dc", "DC"),
        ("hpr", "HPR")
    )
    SEGMENT_CHOICES = (
        ("",""),
        ("ccc", "CCC"),
        ("lib", "Library"),
        ("k12", "K12"),
        ("csu", "CSU"),
        ("uc", "UC"),
        ("uchs", "UC Health System"),
        ("health", "Non-UCHS Health"),
        ("cas", "Culture, Arts, Science"),
        ("dom-pac", "Domestic Pacwave"),
        ("indp", "Independent"),
        ("other", "Other"),
    )
    SERVICE_CHOICES = (
        ("",""),
        ("CENIC - CENIC L3", "CENIC Device - CENIC Device L3"),
        ("CENIC - CENIC L2", "CENIC Device - CENIC Device L2"),
        ("CENIC - CUST L3", "CENIC Device - Customer Device L3"),
        ("CENIC - CUST L2", "CENIC Device - Customer Device L2"),
        ("CENIC - CUST DMS", "CENIC Device - Customer Device DMS"),
    )
    SITE_CHOICES = (("alacc", "Alameda CC"), ("wvmcc", "West Valley Mission CC"))
    
    #DEV_CHOICES = Job.load_yaml('sites.yaml')['ccc']
    
    
    DEV_CHOICES = (
        ("",""),
        ("cpe_rtr", "CPE Router"),
        ("cpe_sw", "CPE Switch"),
        ("bb_rtr", "Backbone Router"),
        ("bb_sw", "Backbone Switch"),
    )
    speed = ChoiceVar(label="Interface Speed", choices=SPEED_CHOICES)
    net = ChoiceVar(
        label="Network",
        description="Choose which network the circuit is on",
        choices=NET_CHOICES,
    )
    segment = ChoiceVar(
        label="Segment",
        description="Choose the customer segment",
        choices=SEGMENT_CHOICES,
    )
    service = ChoiceVar(
        label="Service Type",
        description="Pick a Service Type. See Confluence page for details on the service types",
        choices=SERVICE_CHOICES,
    )
    site = ChoiceVar(
        label="Site", description="Choose the customer site", choices=SITE_CHOICES
    )
    local_dev = ChoiceVar(
        default = '',
        label="Local Device",
        description="Select the Local Device type",
        choices=DEV_CHOICES,
    )
    remote_dev = ChoiceVar(
        label="Remote Device",
        description="Select the Remote Device type",
        choices=DEV_CHOICES,
    )
    remote_name = StringVar(
        label="Remote Device",
    )
    remote_port = StringVar(label="Remote Device Port")
    clr = IntegerVar(
        label="CLR",
        description="CLR number for circuit",
    )
    subint = BooleanVar(
        label="Subinterface?",
        description="Is this a subinterface or non-0 unit?",
    )
    cust = BooleanVar(
        label="Customer facing?",
        description="Is this directly connected to customer? Does not apply if 'Subinterface' is selected.",
    )

    def run(self, data, commit):

        speed = data["speed"]
        net = data["net"]
        segment = data["segment"]
        service = data["service"]
        site_code = data["site"]
        subint = data["subint"]
        cust = data["cust"]
        local_dev = data["local_dev"]
        remote_dev = data["remote_dev"]
        remote_name = data["remote_name"]
        remote_port = data["remote_port"]
        clr = data["clr"]

        port_desc = f"{speed} to {remote_name} {remote_port} CLR- {clr}"

        unit_tag = port_tag = ""

        if service.startswith("CENIC - CENIC"):
            port_tag = f"[{net}:core]"

            if local_dev == "cpe_rtr":
                if remote_dev.startswith("bb") and service.endswith(
                    "L3"
                ):  # CPE-BB L3 circuit no ASI
                    port_tag = f"[{net}:infra]{port_tag} {port_desc}"

            elif local_dev == "bb_rtr":
                if service.endswith("L3"):
                    if remote_dev == "cpe_rtr":
                        if subint:
                            port_tag = f"[{net}:asi]{port_tag}"
                            unit_tag = f"[{net}:infra] {port_desc}"
                        else:
                            port_tag = f"[{net}:infra]{port_tag} {port_desc}"

                    elif remote_dev == "bb_rtr":  # BB-BB L2 circuit
                        bb_port_tag = f"[{net}:bb-{site_code}"
                        if subint:
                            unit_tag = f"[{net}:infra]"
                            port_tag = bb_port_tag
                        else:
                            port_tag = f"[{net}:infra]{bb_port_tag}"
                        port_tag = f"{port_tag} {port_desc}"

                    elif remote_dev == "bb_sw":  # ASI Router port
                        port_tag = f"[{net}:asi]{port_tag} {port_desc}"
                else:
                    if remote_dev == "cpe_rtr":
                        if subint:
                            port_tag = f"[{net}:asi]{port_tag}"
                            unit_tag = port_desc
                        else:
                            port_tag = f"{port_tag} {port_desc}"

            elif local_dev == "bb_sw":
                if remote_dev == "bb_rtr":  # ASI Switch port
                    port_tag = f"[{net}:l2agg]{port_tag}"
                elif remote_dev == "bb_sw":  # SW-SW trunk
                    port_tag = f"[{net}:l2icl]{port_tag}"
                elif remote_dev.startswith("cpe"):  # Accessport
                    port_tag = f"[{net}:l2acc]{port_tag}"

            else:  # catch-all, ex: cpe_sw
                if subint:
                    unit_tag = port_desc
                else:
                    port_tag = f"{port_tag} {port_desc}"

        elif service.startswith("CENIC - CUST"):
            port_tag = f"[{net}:{segment}][{net}:site-{site_code}]"

            if cust:  # if port connects to customer
                port_tag = f"[{net}:ext]{port_tag}"

            if service.endswith("L3"):  # 'edge' port
                port_tag = f"[{net}:edge]{port_tag}"

            else:  # 'l2ege' port
                port_tag = f"[{net}:l2edge]{port_tag}"
                if service.endswith("DMS"):
                    port_tag = f"[{net}:dms]{port_tag}"

            if subint:
                unit_tag = f"{port_tag} {port_desc}"
                port_tag = ""
            else:
                port_tag = f"{port_tag} {port_desc}"

        output = f"**Port Tag:** `{port_tag}`\n\n**Unit Tag:** `{unit_tag}`\n"
        self.log_success(message=output)

        return output
