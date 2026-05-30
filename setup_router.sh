#!/bin/sh

# Install openvswitch and iproute2
apk update
apk add openvswitch iproute2

# Start ovsdb-server and ovs-vswitchd
mkdir -p /run/openvswitch
/usr/share/openvswitch/scripts/ovs-ctl start

# Wait for ovs-vswitchd to be ready
sleep 2

# Create OVS bridge br0
ovs-vsctl add-br br0

# Identify interfaces
# Sender link interface has IP 10.0.1.3
SENDER_IF=$(ip -4 addr show | grep 10.0.1.3 | awk '{print $NF}')
# Primary link interface has IP 10.0.2.2
PRIMARY_IF=$(ip -4 addr show | grep 10.0.2.2 | awk '{print $NF}')
# Backup link interface has IP 10.0.3.2
BACKUP_IF=$(ip -4 addr show | grep 10.0.3.2 | awk '{print $NF}')

# Save interfaces to file so actuator can read them easily
echo "$SENDER_IF" > /sender_if.txt
echo "$PRIMARY_IF" > /primary_if.txt
echo "$BACKUP_IF" > /backup_if.txt

# Attach primary and backup interfaces to br0
# We also need to attach sender_link to br0, otherwise traffic from sender cannot reach receiver
ovs-vsctl add-port br0 $SENDER_IF
ovs-vsctl add-port br0 $PRIMARY_IF
ovs-vsctl add-port br0 $BACKUP_IF

# Set IP address on br0 to act as gateway (optional, but good for routing if needed)
# Remove IP from physical interfaces and move to bridge if needed, but for simple layer-2 bridging,
# just adding ports is enough. Wait, if it acts as a router, we might need it to be a bridge
# Since we use ovs-ofctl to forward traffic, we will use Layer 2 bridging based on MAC or IP.
# Actually, the user says "forces all traffic from the sender IP to output explicitly through the port corresponding to the chosen route"
# This implies OpenFlow rules will match src IP and act on output port.

# Inject 50ms latency onto the backup_link interface using tc
tc qdisc add dev $BACKUP_IF root netem delay 50ms

# Optional: Add initial flow to drop all or forward to primary by default
# We leave it empty or default NORMAL forwarding.
# If we want NORMAL forwarding off, we could remove normal action:
# ovs-ofctl del-flows br0

echo "Setup router complete"
