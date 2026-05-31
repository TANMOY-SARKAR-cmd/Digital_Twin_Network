import os
import subprocess
import sys
import time

import pytest
def test_bridge_starts():
    # Scapy sniffing typically requires root/cap_net_raw; skip in unprivileged CI.
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        pytest.skip("requires root privileges to sniff packets")

    # Ensure bridge doesn't crash immediately (simulating API failure retry)
    proc = subprocess.Popen([sys.executable, "live_docker_bridge.py"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        print(f"STDOUT:\n{stdout.decode(errors='replace')}")
        print(f"STDERR:\n{stderr.decode(errors='replace')}")
        pytest.fail("live_docker_bridge.py exited unexpectedly early")
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()

if __name__ == "__main__":
    test_bridge_starts()
    print("Bridge test passed!")
