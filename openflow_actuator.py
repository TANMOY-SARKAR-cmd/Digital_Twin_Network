import subprocess

# The known IP of the external attacker from our docker-compose.yml
ATTACKER_IP = "172.20.0.10"
CONTAINER_NAME = "sdn_router"


def block_attacker():
    """Injects an OpenFlow rule to drop all traffic from the attacker."""
    print(f"🛡️ ACTUATOR: Blocking attacker IP {ATTACKER_IP} "
          "at the Edge Switch!")
    # Priority 200 overrides the Priority 0 NORMAL rule set by setup_router.sh
    cmd = (f"docker exec {CONTAINER_NAME} ovs-ofctl add-flow br0 "
           f"priority=200,ip,nw_src={ATTACKER_IP},actions=drop")
    subprocess.run(
        cmd, shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def unblock_attacker():
    """Removes the drop rule to restore normal traffic."""
    print("🟢 ACTUATOR: Restoring normal traffic flow.")
    cmd = (f"docker exec {CONTAINER_NAME} "
           f"ovs-ofctl del-flows br0 ip,nw_src={ATTACKER_IP}")
    subprocess.run(
        cmd, shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def switch_route(route_id):
    """
    Adapter function: Maps AI's old routing logic to new Edge Firewall logic.
    route_id == 0: Normal / Safe
    route_id == 1: Attack Detected / Mitigate
    """
    if route_id == 1:
        block_attacker()
    else:
        unblock_attacker()


if __name__ == "__main__":
    # Test the mitigation if run directly
    print("Testing Actuator Mitigation...")
    block_attacker()
