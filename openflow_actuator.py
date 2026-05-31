import subprocess
import ipaddress

CONTAINER_NAME = "sdn_router"


def is_valid_ip(ip_str):
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def block_attacker(target_ip):
    """Injects an OpenFlow rule to drop all traffic from the target IP."""
    if not is_valid_ip(target_ip):
        print(f"⚠️ ACTUATOR ERROR: Invalid IP address: {target_ip}")
        return

    print(f"🛡️ ACTUATOR: Blocking IP {target_ip} at the Edge Switch!")
    cmd = [
        "docker", "exec", CONTAINER_NAME, "ovs-ofctl", "add-flow", "br0",
        f"priority=200,ip,nw_src={target_ip},actions=drop"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ ACTUATOR ERROR: {result.stderr}")


def unblock_attacker(target_ip):
    """Removes the drop rule to restore normal traffic."""
    if not is_valid_ip(target_ip):
        return

    print(f"🟢 ACTUATOR: Restoring traffic flow for {target_ip}.")
    cmd = [
        "docker", "exec", CONTAINER_NAME, "ovs-ofctl", "del-flows", "br0",
        f"ip,nw_src={target_ip}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ ACTUATOR ERROR: {result.stderr}")


def switch_route(route_id, target_ip="172.20.0.10"):
    """Adapter function mapping the AI routing decision to firewall rules."""
    if route_id == 1:
        block_attacker(target_ip)
    else:
        unblock_attacker(target_ip)
