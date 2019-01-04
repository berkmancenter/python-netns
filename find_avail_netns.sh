#!/bin/bash

for i in {0..255}
do
  if [ ! `ip netns list | grep -o "vpn$i\b"` ]; then
    echo $i
    exit
  fi
done
