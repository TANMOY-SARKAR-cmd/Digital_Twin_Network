import asyncio
import websockets
import json
import subprocess
import time
import requests
import random
from shared_config import FEATURES


async def test_api():
    proc = subprocess.Popen(["uvicorn", "core_api:app", "--port", "8000"])

    # Poll for health
    max_retries = 30
    for i in range(max_retries):
        try:
            resp = requests.get("http://127.0.0.1:8000/health")
            if resp.status_code == 200:
                print("API is up!")
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.5)
    else:
        print("API failed to start")
        proc.terminate()
        return False

    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws/network") as ws_network, \
                   websockets.connect("ws://127.0.0.1:8000/ws/compare") as ws_compare:

            for i in range(50):
                payload = {feat: random.uniform(0, 100) for feat in FEATURES}
                payload['ground_truth_attack'] = random.choice([True, False])
                payload['lat_a'] = 0.01
                payload['lat_b'] = 0.05

                await ws_network.send(json.dumps(payload))
                await ws_compare.send(json.dumps(payload))

                res_net = await ws_network.recv()
                res_comp = await ws_compare.recv()

                # Check for errors in the responses if any
                net_data = json.loads(res_net)
                comp_data = json.loads(res_comp)

                if "error" in net_data:
                    print(f"Error in network response: {net_data['error']}")
                    raise Exception("Backend error")

                if "error" in comp_data:
                    print(f"Error in compare response: {comp_data['error']}")
                    raise Exception("Backend error")

                print(f"Packet {i+1} processed successfully")
        print("Test passed 100%")
        return True
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    asyncio.run(test_api())
