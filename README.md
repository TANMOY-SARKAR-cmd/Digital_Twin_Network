# Digital Twin Network

## Quick Start Guide

**1. Setup Data Dependencies (Git LFS)**
The datasets for simulation are tracked via Git Large File Storage (LFS). Ensure you have Git LFS installed, then pull the datasets:
```bash
git lfs install
git lfs pull
```

**2. Start the Core API Backend**
The backend coordinates AI inference and runs the WebSocket server. Start it first:
```bash
uvicorn core_api:app --host 0.0.0.0 --port 8000
# OR
python core_api.py
```

**3. Start the Dashboard UI (Streamlit)**
In a new terminal window, start the interactive frontend dashboard:
```bash
python -m streamlit run app_dashboard.py
```

**4. Start the Data Injector (Bridge)**
In another terminal, start simulating network traffic by feeding a dataset through the bridge:
```bash
python network_bridge.py
```
(You can also use `ns3_bridge.py` for simulated topologies.)
