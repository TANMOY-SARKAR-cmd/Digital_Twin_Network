from shared_config import FEATURES
import asyncio
import websockets
import json
import pandas as pd
import numpy as np
import os
import glob
import re

print("🚀 Booting up Network Bridge...")


def parse_latency(val, default_ms=10):
    try:
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val))
        return float(nums[0]) / 1000 if nums else (default_ms / 1000)
    except Exception:
        return default_ms / 1000


primary_latency_base = parse_latency(os.getenv("PRIMARY_LAT", "10"), default_ms=10)
backup_latency_base = parse_latency(os.getenv("BACKUP_LAT", "50"), default_ms=50)
selected_dataset = os.getenv("SELECTED_DATASET", "")
# FIX: Respect the injection-speed slider set in the Architect UI.
# The Architect writes SIM_SPEED (packets/sec) to the environment before
# launching this bridge. Default = 2 pkt/s (matches old hard-coded 0.5 s).
_sim_speed   = max(1, int(float(os.getenv("SIM_SPEED", "2"))))
_delay_per_packet = 1.0 / _sim_speed


def _is_lfs_pointer(file_path):
    with open(file_path, "r", encoding="utf-8") as f_check:
        first_line = f_check.readline()
    return "version https://git-lfs.github.com/spec/v1" in first_line


async def inject_traffic():
    uri = "ws://localhost:8000/ws/network"
    target_csv = (
        f"data/{selected_dataset}" if selected_dataset
        else (glob.glob("data/*.csv")[0] if glob.glob("data/*.csv") else None)
    )

    if not target_csv or not os.path.exists(target_csv):
        print(f"❌ Dataset not found: {target_csv}")
        return

    print(f"📡 Loading: {target_csv}")

    if await asyncio.to_thread(_is_lfs_pointer, target_csv):
        print("❌ Dataset is a Git LFS pointer. Please run 'git lfs pull' to download the actual CSV data.")
        import sys
        sys.exit(1)

    print("✅ LFS check passed. Connecting...")

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                i = 0
                chunk_iter = pd.read_csv(target_csv, chunksize=5000)
                while True:
                    chunk = await asyncio.to_thread(next, chunk_iter, None)
                    if chunk is None:
                        break
                    chunk.columns = [c.strip() for c in chunk.columns]
                    chunk = chunk.replace(['Infinity', 'inf', 'NaN'], np.nan).fillna(0)

                    for row_idx in range(len(chunk)):
                        row = chunk.iloc[row_idx]
                        features = pd.to_numeric(row[FEATURES], errors='coerce').fillna(0).astype(float).values.tolist()
                        vol = float(row.get('Total Length of Fwd Packets', 0) + row.get('Total Length of Bwd Packets', 0))

                        raw_label = str(row.get('Label', 'BENIGN')).strip().upper()
                        is_attack = raw_label != 'BENIGN'

                        lat_a = 0.95 if is_attack else np.random.uniform(primary_latency_base, primary_latency_base + 0.02)
                        lat_b = backup_latency_base

                        if is_attack:
                            print(f"🔥 Packet {i}: ATTACK ({raw_label}) -> lat_a: {lat_a}")

                        payload = {"features": features, "volume": vol, "lat_a": lat_a, "lat_b": lat_b}
                        await websocket.send(json.dumps(payload))
                        await websocket.recv()
                        await asyncio.sleep(_delay_per_packet)
                        i += 1
            break  # Exit if successfully finished the whole dataset
        except Exception as e:
            print(f"Connection error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(inject_traffic())
