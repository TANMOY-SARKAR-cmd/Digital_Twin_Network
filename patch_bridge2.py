with open("live_docker_bridge.py", "r") as f:
    content = f.read()

content = content.replace("expected_acks = {}  # Dictionary to track packet transmission times", "expected_acks = {}  # Dictionary to track packet transmission times\nlast_cleanup_time = time.monotonic()")

with open("live_docker_bridge.py", "w") as f:
    f.write(content)
