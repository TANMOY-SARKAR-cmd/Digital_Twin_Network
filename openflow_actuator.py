import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONTAINER_NAME = "app-sdn_router-1"


def get_interface_port(if_name: str) -> str:
    """
    Get the OpenFlow port number for a given interface on br0.
    """
    # Run ovs-ofctl show br0
    cmd = ["docker", "exec", CONTAINER_NAME, "ovs-ofctl", "show", "br0"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Failed to get ports: {result.stderr}")
        return ""

    # Parse the output to find the port number
    # Output looks like:
    #  1(eth1): addr:02:42:0a:00:01:03
    for line in result.stdout.splitlines():
        if f"({if_name})" in line:
            # Extract the port number before the '('
            port_str = line.strip().split('(')[0]
            return port_str.strip()
    return ""


def get_interface_name(file_path: str) -> str:
    """
    Read the interface name saved by setup_router.sh
    """
    cmd = ["docker", "exec", CONTAINER_NAME, "cat", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Failed to read {file_path}: {result.stderr}")
        return ""
    return result.stdout.strip()


def switch_route(target_route: int):
    """
    Switch traffic route.
    target_route: 0 for Primary, 1 for Backup
    """
    # 1. Determine interfaces
    sender_if = get_interface_name("/sender_if.txt")
    primary_if = get_interface_name("/primary_if.txt")
    backup_if = get_interface_name("/backup_if.txt")

    if not sender_if or not primary_if or not backup_if:
        logger.error("Could not determine all interfaces.")
        return

    # 2. Get OpenFlow port numbers
    sender_port = get_interface_port(sender_if)
    primary_port = get_interface_port(primary_if)
    backup_port = get_interface_port(backup_if)

    if not sender_port or not primary_port or not backup_port:
        logger.error("Could not determine OpenFlow port numbers.")
        return

    # 3. Determine output port based on target route
    # target_route: 0 = Primary, 1 = Backup
    if target_route == 0:
        out_port = primary_port
        route_name = "Primary"
    elif target_route == 1:
        out_port = backup_port
        route_name = "Backup"
    else:
        logger.error(f"Invalid route {target_route}")
        return

    logger.info(f"Switching route to {route_name} (port {out_port})")

    # 4. Flush existing flows
    cmd_del = [
        "docker", "exec", CONTAINER_NAME, "ovs-ofctl", "del-flows", "br0"
    ]
    res_del = subprocess.run(cmd_del, capture_output=True, text=True)
    if res_del.returncode != 0:
        logger.error(f"Failed to delete flows: {res_del.stderr}")
        return

    # 5. Add new flow to force all traffic from sender IP to output
    # Also add a rule to allow return traffic or ARP if necessary.
    # Normal forwarding handles the rest.

    # Low priority NORMAL forwarding (so ARP works)
    cmd_add_normal = [
        "docker", "exec", CONTAINER_NAME, "ovs-ofctl", "add-flow", "br0",
        "priority=0,actions=NORMAL"
    ]
    subprocess.run(cmd_add_normal, capture_output=True, text=True)

    # High priority rule for sender to receiver
    # Sender IP: 10.0.1.2
    cmd_add_ip = [
        "docker", "exec", CONTAINER_NAME, "ovs-ofctl", "add-flow", "br0",
        f"priority=100,ip,nw_src=10.0.1.2,actions=output:{out_port}"
    ]
    res_add_ip = subprocess.run(cmd_add_ip, capture_output=True, text=True)
    if res_add_ip.returncode != 0:
        logger.error(f"Failed to add IP flow: {res_add_ip.stderr}")
        return

    logger.info("Successfully updated OpenFlow rules.")


if __name__ == "__main__":
    pass
