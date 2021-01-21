# Use algorithm to return the IPv6 address for a given IPv4 address

# Args: 
#    int/ext - internal facing or external facing link
#    hpr/dc - HPR link or DC link

import netaddr
from sys import argv

# pull mask, change to 'int' to convert to v6 mask
mask = int(argv[1].split("/")[1])

# IP only
ip = netaddr.IPNetwork(argv[1]).ip

# determine if internal or external facing
if argv[2] == "int": 
    int_ext = str(0)
    print("\n=== Internal facing ===")
elif argv[2] == "ext":
    int_ext = str(1)
    print("\n=== External facing ===")
else: 
    print("\nEnter either 'ext' or 'int'")
    exit()

# determine if HPR or DC
if argv[3] == "hpr":
    network = str(0)
    print("=== HPR network ===")
elif argv[3] == "dc":
    network = str(1)
    print("=== DC network ===")
else: 
    print("\nEnter either 'hpr' or 'dc'")
    exit()

# convert IP to hex
v4_hex = hex(netaddr.IPAddress(ip)).lstrip("0x")

# break into 3 hex 'chunks'
hex_a = v4_hex[0]
hex_b = v4_hex[1:5]
hex_c = v4_hex[5:len(v4_hex)]

# convert mask v4 -> v6 
final_mask = str(mask + 92)

# create IPv6 string
joined_ip = f"2607:F380:000{int_ext}:0:0:01{network}{hex_a}:{hex_b}:{hex_c}1"

# convert IPv6 string to an IPv6 address
final_ip = str(netaddr.IPAddress(joined_ip, 6))
final_net = final_ip + "/" + final_mask

# print the result
print (f"\nThe converted IPv4 to IPv6 address is: {final_net}")