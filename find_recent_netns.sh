#!/bin/bash

echo `ip netns list | grep -Eo "vpn[0-9]+" | grep -Eo "[0-9]+" | sort -n | tail -n 1`
