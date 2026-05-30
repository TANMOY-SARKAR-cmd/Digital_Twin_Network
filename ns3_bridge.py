# ns3_bridge.py
from shared_config import FEATURES
import asyncio
import websockets
import json
import pandas as pd
import numpy as np
import glob


def _is_lfs_pointer(file_path):
    with open(file_path, "r", encoding="utf-8") as f_check:
        first_line = f_check.readline()
    return "version https://git-lfs.github.com/spec/v1" in first_line


async def simulate_network():
    # FIX: Corrected endpoint from /ws/ns3 (which doesn't exist in core_api.py)
    # to /ws/network — the only packet-ingestion endpoint the API exposes.
    uri = "ws://localhost:8000/ws/network"

    csv_files = glob.glob("data/*.csv")
    if not csv_files:
        print("❌ No CSV files found in data/ folder! Please add a dataset.")
        return

    print(f"📡 NS-3 Bridge Started. Injecting dataset: {csv_files[0]}")

    if await asyncio.to_thread(_is_lfs_pointer, csv_files[0]):
        print("❌ Dataset is a Git LFS pointer. Please run 'git lfs pull' to download the actual CSV data.")
        import sys
        sys.exit(1)

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                i = 0
                chunk_iter = pd.read_csv(csv_files[0], chunksize=5000)
                while True:
                    chunk = await asyncio.to_thread(next, chunk_iter, None)
                    if chunk is None:
                        break
                    chunk.columns = chunk.columns.str.strip()
                    chunk = chunk.replace(['Infinity', 'inf', 'NaN'], np.nan).fillna(0)

                    for row_idx in range(len(chunk)):
                        row = chunk.iloc[row_idx]

                        # FIX: Convert to numeric and sanitize (handles "Infinity" strings not
                        # caught by fillna, and prevents json.dumps() from failing on np.nan/inf).
                        features = pd.to_numeric(row[FEATURES], errors='coerce').fillna(0).astype(float).values.tolist()

                        vol = float(
                            row.get('Total Length of Fwd Packets', 0) +
                            row.get('Total Length of Bwd Packets', 0)
                        )

                        # FIX: Strip whitespace and normalise case before comparing label,
                        # otherwise " BENIGN" (with a leading space) is treated as an attack.
                        raw_label = str(row.get('Label', 'BENIGN')).strip().upper()
                        is_attack = raw_label != 'BENIGN'

                        LINK_CAPACITY = 125000000  # Example: 1 Gbps in bytes
                        if vol >= LINK_CAPACITY:
                            lat_a = 0.99  # Max saturation
                        else:
                            # M/M/1 formula approximation
                            utilization = vol / LINK_CAPACITY
                            base_latency = 0.01
                            lat_a = base_latency / (1 - utilization)

                            # Cap maximum latency to prevent math errors
                            lat_a = min(lat_a, 0.95)

                        if is_attack:
                            lat_a = 0.95

                        lat_b = 0.05  # Backup is stable

                        payload = {
                            "features": features,
                            "volume": vol,
                            "lat_a": lat_a,
                            "lat_b": lat_b,
                        }

                        await websocket.send(json.dumps(payload))
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        decision = json.loads(response)

                        route_str = "Primary (Fiber)" if decision["route"] == 0 else "Backup (Sat)"
                        print(f"Packet {i} | Vol: {vol:.0f} | Attack: {is_attack} | Route: {route_str}")

                        # FIX: MUST be await asyncio.sleep(), not time.sleep().
                        # time.sleep() is a blocking call — it freezes the entire async event loop,
                        # preventing any WebSocket sends/receives while it's sleeping.
                        await asyncio.sleep(0.1)
                        i += 1
            break  # Exit if successfully finished the whole dataset
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, OSError, websockets.exceptions.WebSocketException) as e:
            print(f"WebSocket error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(simulate_network())
