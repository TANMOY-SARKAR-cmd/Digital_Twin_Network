import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import asyncio
import websockets
import json
import time
import threading
import queue

sim_queue = queue.Queue()
from streamlit.runtime.scriptrunner import add_script_run_ctx

# FIX: nest_asyncio allows asyncio.run() to work inside Streamlit's already-running
# event loop. Without this, clicking Start Simulation raises:
#   RuntimeError: This event loop is already running
import nest_asyncio
nest_asyncio.apply()

# --- Page Configuration ---
st.set_page_config(page_title="Network Architect", layout="wide")
st.title("🛠️ SDN Network Architect")

# Initialize session state for simulation control
if 'stop_simulation' not in st.session_state:
    st.session_state.stop_simulation = False

# --- 1. Router Configuration ---
st.header("1. Router Configuration")
col1, col2, col3 = st.columns(3)
with col1:
    primary_bw = st.text_input("Primary Route Bandwidth", "1 Gbps", key="primary_bw_val")
    primary_lat = st.text_input("Primary Base Latency", "10ms")
with col2:
    backup_bw = st.text_input("Backup Route Bandwidth", "100 Mbps")
    backup_lat = st.text_input("Backup Base Latency", "50ms")
with col3:
    sim_speed = st.slider("Injection Speed (Packets/Sec)", 1, 50, 2)
    delay_per_packet = 1.0 / sim_speed

# --- 2. Dataset Injection ---
st.header("2. Dataset Injection")
if not os.path.exists("data"):
    os.makedirs("data")
datasets = [f for f in os.listdir("data") if f.endswith('.csv')]
selected_dataset = st.selectbox("Select Traffic Scenario", datasets)

# Feature list for the AI Model
FEATURES = [
    'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets', 'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
    'Fwd Packet Length Max', 'Fwd Packet Length Min', 'Fwd Packet Length Mean', 'Fwd Packet Length Std', 'Bwd Packet Length Max',
    'Bwd Packet Length Min', 'Bwd Packet Length Mean', 'Bwd Packet Length Std', 'Flow Bytes/s', 'Flow Packets/s', 'Flow IAT Mean',
    'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min', 'Fwd IAT Total', 'Bwd IAT Total', 'Fwd Header Length', 'Bwd Header Length',
    'Fwd Packets/s', 'Bwd Packets/s', 'Min Packet Length', 'Max Packet Length', 'Packet Length Mean', 'Packet Length Std',
    'Packet Length Variance', 'FIN Flag Count', 'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count', 'ACK Flag Count',
    'URG Flag Count', 'Down/Up Ratio', 'Average Packet Size', 'Init_Win_bytes_forward', 'Init_Win_bytes_backward'
]


def parse_latency(val):
    nums = re.findall(r"\d+", str(val))
    return float(nums[0]) / 1000 if nums else 0.01


# --- 3. Simulation Engine ---
async def start_injection(file_path, p_lat, b_lat):
    uri = "ws://localhost:8000/ws/network"


    # We don't have the exact total up front easily without scanning,
    # but we can omit or estimate. For simplicity, we just won't show exact progress % if total is unknown.
    # Alternatively we can just read the length first but that loads the whole file or requires a pass.
    # We will just iterate without a perfect progress bar or assume an arbitrary large number.
    # Actually, we can get total lines using a quick generator or wc if needed, but
    # let's just make the progress bar an indeterminate spinner or omit it.

    # Let's count rows first to keep the progress bar working
    total = sum(1 for _ in open(file_path)) - 1 # rough row count

    try:
        async with websockets.connect(uri) as websocket:
            i = 0
            for chunk in pd.read_csv(file_path, chunksize=5000):
                chunk.columns = [c.strip() for c in chunk.columns]
                for row_idx in range(len(chunk)):
                    if st.session_state.stop_simulation:
                        sim_queue.put({"type": "warning", "text": "🛑 Simulation manually terminated."})
                        return

                    row = chunk.iloc[row_idx]
                    features = pd.to_numeric(row[FEATURES], errors='coerce').fillna(0).tolist()
                    vol = float(
                        row.get('Total Length of Fwd Packets', 0) +
                        row.get('Total Length of Bwd Packets', 0)
                    )

                    label = str(row.get('Label', 'BENIGN')).strip().upper()
                    is_attack = "BENIGN" not in label

                    # Convert primary_bw string (e.g., "1 Gbps") to bytes per second for the math
                    bw_str = st.session_state.get('primary_bw_val', '1000000000') # default 1Gbps
                    LINK_CAPACITY = float(re.sub(r'[^\d.]', '', bw_str)) * 125000 # Convert bits to bytes

                    if vol >= LINK_CAPACITY:
                        lat_a = 0.99
                    else:
                        utilization = vol / LINK_CAPACITY
                        lat_a = p_lat / (1 - utilization)
                        lat_a = min(lat_a, 0.95)

                    if is_attack:
                        lat_a = 0.95

                    payload = {"features": features, "volume": vol, "lat_a": lat_a, "lat_b": b_lat}
                    await websocket.send(json.dumps(payload))
                    await websocket.recv()

                    i += 1

                    if total > 0:
                        prog = i / total
                        rem_packets = total - i
                        rem_seconds = rem_packets * delay_per_packet
                        hrs, rem = divmod(int(rem_seconds), 3600)
                        mins, secs = divmod(rem, 60)

                        sim_queue.put({
                            "type": "update",
                            "progress": min(prog, 1.0),
                            "text": f"Injecting: {i}/{total} | Type: {label}",
                            "time": f"**⏱️ Time Left:** {hrs}h {mins}m {secs}s"
                        })

                    await asyncio.sleep(delay_per_packet)
            sim_queue.put({"type": "completed"})

    except Exception as e:
        sim_queue.put({"type": "error", "text": f"Core API connection failed: {e}"})


def run_injection_thread(file_path, p_lat, b_lat):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_injection(file_path, p_lat, b_lat))

# Controls
c1, c2 = st.columns(2)
if c1.button("▶️ Start Simulation", type="primary", use_container_width=True):
    st.session_state.stop_simulation = False
    st.session_state.sim_active = True
    while not sim_queue.empty():
        sim_queue.get()
    if selected_dataset:
        file_path = f"data/{selected_dataset}"
        # Start in background instead of blocking:
        t = threading.Thread(target=run_injection_thread, args=(file_path, parse_latency(primary_lat), parse_latency(backup_lat)), daemon=True)
        add_script_run_ctx(t)
        t.start()
    else:
        st.warning("Please select a dataset first.")

if c2.button("🛑 Stop Injection", use_container_width=True):
    st.session_state.stop_simulation = True
    st.session_state.sim_active = False
if st.session_state.get('sim_active', False):
    # Initialize session state for UI updates
    if 'sim_progress' not in st.session_state:
        st.session_state.sim_progress = 0.0
    if 'sim_text' not in st.session_state:
        st.session_state.sim_text = ""
    if 'sim_time' not in st.session_state:
        st.session_state.sim_time = ""

    # Process all queued updates
    while not sim_queue.empty():
        update = sim_queue.get()
        if update.get("type") == "update":
            st.session_state.sim_progress = update["progress"]
            st.session_state.sim_text = update["text"]
            st.session_state.sim_time = update["time"]
        elif update.get("type") == "warning":
            st.warning(update["text"])
            st.session_state.sim_active = False
        elif update.get("type") == "error":
            st.error(update["text"])
            st.session_state.sim_active = False
        elif update.get("type") == "completed":
            st.success("✅ Simulation completed successfully.")
            st.session_state.sim_active = False

    # Render current state
    st.progress(st.session_state.sim_progress)
    st.text(st.session_state.sim_text)
    st.markdown(st.session_state.sim_time)

    time.sleep(0.5)
    if st.session_state.get('sim_active', False):
        st.rerun()
