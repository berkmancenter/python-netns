#!/bin/bash

# Find most recently created network namespace
dir=`dirname "$(readlink -f "$0")"`
highest_vpn=`$dir/find_recent_netns.sh`
if [ "$highest_vpn" = "" ]; then
  echo "No network namespaces to remove"
  exit
fi

function removeNetns {
  to_remove=$1
  num_to_remove=`echo $to_remove | grep -Eo "[0-9]+"`

  ext_interface=`route | grep '^default' | grep -o '[^ ]*$'`

  ns=$to_remove
  interface_outside_ns="veth$(($num_to_remove * 2))"
  interface_inside_ns="veth$(($num_to_remove * 2 + 1))"
  addr_outside="10.1.${num_to_remove}.1/24"
  addr_inside="10.1.${num_to_remove}.2/24"

  # Remove namespace
  ip netns del $ns

  # Remove virtual interface
  ip link del $interface_outside_ns

  # Remove NAT rules
  iptables -w 10 -t nat -D POSTROUTING -s ${addr_outside} -o ${ext_interface} -j MASQUERADE
  iptables -w 10 -D FORWARD -i ${ext_interface} -o ${interface_outside_ns} -j ACCEPT
  iptables -w 10 -D FORWARD -o ${ext_interface} -i ${interface_outside_ns} -j ACCEPT

  rm -rf /etc/netns/${ns}/ &> /dev/null

  echo $ns
}

# Remove the provided namespace, or the most recent if none provided
to_remove=$1

if [ "$to_remove" = "all" ]; then
  while [ `$dir/find_recent_netns.sh` ]; do
    highest_vpn=`$dir/find_recent_netns.sh`
    removeNetns "vpn$highest_vpn"
  done
  exit
fi

if [ "$to_remove" = "" ]; then
  to_remove="vpn$highest_vpn"
fi
removeNetns $to_remove

