#!/bin/bash

sudo apt update

# Install dhclient
sudo apt install isc-dhcp-client -y

# Search [ifupdown]\n managed=false in /etc/NetworkManager/NetworkManager.conf
# If there is a [ifupdown] section, change managed=false to managed=true
sudo sed -i '/^\[ifupdown\]$/,/^\[/ s/managed=false/managed=true/' /etc/NetworkManager/NetworkManager.conf

# If there is no [ifupdown] section, add it to the end of the file
if ! grep -q "\[ifupdown\]" /etc/NetworkManager/NetworkManager.conf; then
    echo "[ifupdown]" | sudo tee -a /etc/NetworkManager/NetworkManager.conf
    echo "managed=true" | sudo tee -a /etc/NetworkManager/NetworkManager.conf
fi

# Make dhclient configurations for dns nameservers
echo 'supersede domain-name-servers 8.8.8.8,8.8.4.4;' | sudo tee -a /etc/dhcp/dhclient.conf

# Add configuraiton for wwan0 interface to /etc/network/interfaces.d/wwan0
echo 'allow-hotplug wwan0
iface wwan0 inet dhcp
    metric 700' | sudo tee /etc/network/interfaces.d/wwan0

# Restart networking and Network Manager
sudo systemctl restart NetworkManager
sudo systemctl restart networking
