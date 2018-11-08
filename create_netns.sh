#!/bin/bash
sysctl -w net.ipv4.ip_forward=1 &> /dev/null

ext_interface=`route | grep '^default' | grep -o '[^ ]*$'`

# Find the most recently created network namespace
# From https://stackoverflow.com/a/246128
dir=`dirname "$(readlink -f "$0")"`
new_vpn=`$dir/find_avail_netns.sh`

ns="vpn${new_vpn}"
interface_outside_ns="veth$(($new_vpn * 2))"
interface_inside_ns="veth$(($new_vpn * 2 + 1))"
addr_outside="10.1.${new_vpn}.1/24"
addr_inside="10.1.${new_vpn}.2/24"

# Create netns
ip netns add $ns
# Enable loopback in netns
ip netns exec $ns ip link set dev lo up

# Create veth pair
ip link add $interface_outside_ns type veth peer name $interface_inside_ns
ip link set $interface_inside_ns netns $ns

# Assign addresses and set default route
ip link set $interface_outside_ns up
ip addr add $addr_outside dev $interface_outside_ns
ip netns exec $ns \
ip link set $interface_inside_ns up
ip netns exec $ns \
ip addr add $addr_inside dev $interface_inside_ns
ip netns exec $ns \
ip route add default via ${addr_outside%/*} dev $interface_inside_ns

# Forward traffic
iptables -w 10 -t nat -A POSTROUTING -s ${addr_outside} -o ${ext_interface} -j MASQUERADE
iptables -w 10 -A FORWARD -i ${ext_interface} -o ${interface_outside_ns} -j ACCEPT
iptables -w 10 -A FORWARD -o ${ext_interface} -i ${interface_outside_ns} -j ACCEPT

# Setup DNS
mkdir -p /etc/netns/${ns}/
echo -e 'nameserver 8.8.4.4\nnameserver 198.18.0.1\nnameserver 1.1.1.1\nnameserver 198.18.0.2\n' > /etc/netns/${ns}/resolv.conf

echo $ns
