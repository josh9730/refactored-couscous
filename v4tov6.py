"""Use algorithm to return the IPv6 address for a given IPv4 address

Args:
    int/ext - internal facing or external facing link
    hpr/dc - HPR link or DC link
"""

import argparse

import netaddr

parser = argparse.ArgumentParser(description="Convert IPv4 to IPv6 address.")
parser.add_argument(
    "address", metavar="IPv4Address", help="IPv4 address with mask in slash notation."
)
parser.add_argument(
    "link",
    metavar="LinkType",
    help='Link Options: "int" or "ext"',
    choices=["int", "ext"],
)
parser.add_argument(
    "network",
    metavar="NetworkType",
    help='Network Options: "hpr" or "dc"',
    choices=["hpr", "dc"],
)
args = parser.parse_args()


def main(args):
    mask = int(args.address.split("/")[1])
    ip = netaddr.IPNetwork(args.address).ip

    if args.link == "int":
        int_ext = str(0)
        link_name = "Internal"
    else:
        int_ext = str(1)
        link_name = "External"

    if args.network == "hpr":
        network = str(0)
        net_name = "HPR"
    else:
        network = str(1)
        net_name = "DC"

    # convert IP to hex
    v4_hex = hex(netaddr.IPAddress(ip)).lstrip("0x")

    # break into 3 hex 'chunks'
    hex_a = v4_hex[0]
    hex_b = v4_hex[1:5]
    hex_c = v4_hex[5 : len(v4_hex)]

    # convert mask v4 -> v6
    if mask == 32:
        final_mask = "128"
    else:
        final_mask = str(mask + 92)

    # create IPv6 string
    joined_ip = f"2607:F380:000{int_ext}:0:0:01{network}{hex_a}:{hex_b}:{hex_c}1"

    # convert IPv6 string to an IPv6 address
    final_ip = str(netaddr.IPAddress(joined_ip, 6))
    final_net = final_ip + "/" + final_mask

    print(f"\n- {link_name} link")
    print(f"- {net_name} Network\n")
    print(f"\t--- Translated IPv4: {final_net} ---\n")


if __name__ == "__main__":
    main(args)
