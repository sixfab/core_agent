#!/bin/bash
OS_VERSION=$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2)
OS_VERSION_NUM=$(echo $OS_VERSION | grep -o -E '[0-9]+([.][0-9]+)?')


if command -v NetworkManager; then
    F_NM=true
else
    F_NM=false
fi

sudo apt install bc -y

if [ $F_NM == true ]; then
    if [[ $(echo "$OS_VERSION_NUM >= 12.0" | bc) -eq 1 ]]; then
        echo "OS version is equal or greater than 12"
        echo "Installing dhcpcd"
        sudo apt update
        sudo apt install dhcpcd -y
        echo "Configuring dhcpcd"
        echo "allowinterfaces wwan*" >> /etc/dhcpcd.conf
        echo "nohook resolv.conf" >> /etc/dhcpcd.conf

        echo "Removing if up down configuration"
        sudo rm /etc/network/interfaces.d/wwan0 > /dev/null
        sudo sed -i '/^\[ifupdown\]$/,/^\[/ s/managed=true/managed=false/' /etc/NetworkManager/NetworkManager.conf

        sudo systemctl restart dhcpcd.service    
    else
        echo "OS version is less than 12. Pass it."
    fi
else
    echo "Network Manager is not installed. Fix not needed!"
fi
