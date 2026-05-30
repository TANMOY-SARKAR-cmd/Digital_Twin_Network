import pytest
import asyncio
import websockets
import json
import subprocess
import requests
import random
from shared_config import FEATURES


@pytest.mark.asyncio
async def test_api():
    proc = subprocess.Popen(["uvicorn", "core_api:app", "--port", "8000"])

    # Poll for health
    max_retries = 30
    for i in range(max_retries):
        try:
            resp = await asyncio.to_thread(requests.get, "http://127.0.0.1:8000/health")
            if resp.status_code == 200:
                print("API is up!")
                break
        except requests.exceptions.ConnectionError:
            pass
        await asyncio.sleep(0.5)
    else:
        proc.terminate()
        proc.wait()  # Ensure the process releases the port before failing
        pytest.fail("API failed to start")

    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws/network") as ws_network, \
                   websockets.connect("ws://127.0.0.1:8000/ws/compare") as ws_compare:

            for i in range(50):
                payload = {
                    "features": [random.uniform(0, 100) for _ in FEATURES],
                    "volume": random.uniform(100, 5000),
                    "ground_truth_attack": random.choice([True, False]),
                    "lat_a": 0.01,
                    "lat_b": 0.05,
                }

                await ws_network.send(json.dumps(payload))
                await ws_compare.send(json.dumps(payload))

                res_net = await asyncio.wait_for(ws_network.recv(), timeout=5.0)
                res_comp = await asyncio.wait_for(ws_compare.recv(), timeout=5.0)

                # Check for errors in the responses if any
                net_data = json.loads(res_net)
                comp_data = json.loads(res_comp)

                if "error" in net_data:
                    pytest.fail(f"Error in network response: {net_data['error']}")

                if "error" in comp_data:
                    pytest.fail(f"Error in compare response: {comp_data['error']}")

                print(f"Packet {i + 1} processed successfully")
        print("Test passed 100%")
        return True
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    asyncio.run(test_api())
