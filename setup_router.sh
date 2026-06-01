#!/bin/sh

echo "Updating OpenWrt Packages..."
opkg update

echo "Installing Open vSwitch..."
opkg install openvswitch ip-full

# Start OVS services
mkdir -p /var/run/openvswitch
ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
ovsdb-server --remote=punix:/var/run/openvswitch/db.sock --pidfile --detach
ovs-vsctl --no-wait init
ovs-vswitchd --pidfile --detach
sleep 2

# Create OVS bridge br0
ovs-vsctl add-br br0

# Identify WAN and LAN interfaces inside OpenWrt
WAN_IF=$(ip -4 addr show | grep 172.20.0.2 | awk '{print $NF}')
LAN_IF=$(ip -4 addr show | grep 10.0.0.1 | awk '{print $NF}')

# Save interfaces to file so the Python actuator can read them later
echo "$WAN_IF" > /wan_if.txt
echo "$LAN_IF" > /lan_if.txt

# Remove IP addresses from physical interfaces
ip addr flush dev $WAN_IF
ip addr flush dev $LAN_IF

# Attach interfaces to the OVS bridge
ovs-vsctl add-port br0 $WAN_IF
ovs-vsctl add-port br0 $LAN_IF

# Assign the gateway IPs directly to the bridge so OpenWrt can route
ip addr add 172.20.0.2/16 dev br0
ip addr add 10.0.0.1/24 dev br0
ip link set br0 up

# Enable IP forwarding globally
sysctl -w net.ipv4.ip_forward=1

# Add basic NORMAL flow for the AI baseline
ovs-ofctl add-flow br0 "priority=0,actions=NORMAL"

# Add static routes so OpenWrt knows how to reach the downstream VLANs via the Core Switch
ip route replace 10.0.10.0/24 via 10.0.0.2
ip route replace 10.0.20.0/24 via 10.0.0.2

echo "✅ OpenWrt Edge Router + OVS Setup Complete!"
