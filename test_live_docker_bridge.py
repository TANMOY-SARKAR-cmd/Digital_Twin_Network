import subprocess
import time
import requests

def test_bridge_starts():
    # Ensure bridge doesn't crash immediately (simulating API failure retry)
    proc = subprocess.Popen(["sudo", "/home/jules/.pyenv/versions/3.12.13/bin/python3", "live_docker_bridge.py"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        print(f"STDOUT:\n{stdout.decode()}")
        print(f"STDERR:\n{stderr.decode()}")
        assert False, "live_docker_bridge.py exited unexpectedly early"
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()

if __name__ == "__main__":
    test_bridge_starts()
    print("Bridge test passed!")
