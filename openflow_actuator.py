import subprocess

CONTAINER_NAME = "sdn_router"


def block_attacker(target_ip):
    """Injects an OpenFlow rule to drop all traffic from the target IP."""
    print(f"🛡️ ACTUATOR: Blocking IP {target_ip} at the Edge Switch!")
    cmd = (f"docker exec {CONTAINER_NAME} ovs-ofctl add-flow br0 "
           f"priority=200,ip,nw_src={target_ip},actions=drop")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ ACTUATOR ERROR: {result.stderr}")


def unblock_attacker(target_ip):
    """Removes the drop rule to restore normal traffic."""
    print(f"🟢 ACTUATOR: Restoring traffic flow for {target_ip}.")
    cmd = (f"docker exec {CONTAINER_NAME} "
           f"ovs-ofctl del-flows br0 ip,nw_src={target_ip}")
    subprocess.run(cmd, shell=True, capture_output=True, text=True)


def switch_route(route_id, target_ip="172.20.0.10"):
    """
    Adapter function: route_id 1 mitigates the specific target_ip.
    """
    if route_id == 1:
        block_attacker(target_ip)
    else:
        unblock_attacker(target_ip)
