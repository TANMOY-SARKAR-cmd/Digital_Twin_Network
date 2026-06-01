import asyncio
import websockets
import json
import os
import queue
import threading
from scapy.all import sniff, IP

# Target API
URI = "ws://127.0.0.1:8000/ws/network"
# Sniff on all interfaces by default, or specify via env var
IFACE = os.getenv("IFACE", None)

# Shared queue to move packets from the Scapy thread to the Asyncio thread
# maxsize parsed from env
maxsize = int(os.getenv("PACKET_QUEUE_MAXSIZE", "10000"))
packet_queue = queue.Queue(maxsize=maxsize)


def packet_handler(pkt):
    """Callback for Scapy to process packets."""
    if IP in pkt:
        src_ip = pkt[IP].src

        # Extract basic features to mimic the CICFlowMeter CSV shape
        pkt_len = len(pkt)
        protocol = pkt[IP].proto

        # We construct a dummy 40-feature array to satisfy the API's shape
        # requirements, but inject the real live volume/length data that
        # the normal_router uses.
        features = [0.0] * 40
        features[0] = float(protocol)
        features[1] = float(pkt_len)

        payload = {
            "features": features,
            "volume": float(pkt_len),  # The critical metric for DDoS detection
            "ground_truth_attack": False,  # Unknown in live traffic
            "lat_a": 0.01,  # Default base latency
            "lat_b": 0.05,  # Default satellite latency
            "src_ip": src_ip
        }
        try:
            packet_queue.put_nowait(payload)
        except queue.Full:
            # Consumer is slower than producer; drop to avoid unbounded backlog
            pass


def run_sniffer():
    """Runs the Scapy sniffer in a blocking background thread."""
    iface_str = IFACE if IFACE else 'ALL'
    print(f"🕵️  Starting live packet sniffer on interface: {iface_str}")
    sniff(iface=IFACE, filter="ip", prn=packet_handler, store=False)


async def stream_to_api():
    """Async loop to pull from the queue and send to the API."""
    while True:
        try:
            print("🔗 Connecting to Digital Twin API...")
            async with websockets.connect(URI) as websocket:
                print("✅ Connected! Streaming live packets...")
                while True:
                    # Non-blocking queue check
                    if not packet_queue.empty():
                        payload = packet_queue.get()
                        await websocket.send(json.dumps(payload))
                        # Receive AI route decision
                        response = await asyncio.wait_for(
                            websocket.recv(), timeout=5.0
                        )
                        decision = json.loads(response)

                        route = decision.get("route")
                        if route is None:
                            print(f"⚠️ Unexpected API response: {decision}")
                            continue

                        route_str = ("Traffic Allowed" if route == 0
                                     else "IP Blocked")
                        vol = payload['volume']
                        print(f"📡 Sent {vol} bytes | AI Route: {route_str}")
                    else:
                        await asyncio.sleep(0.01)  # Yield to event loop

        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, OSError,
                websockets.exceptions.WebSocketException) as e:
            print(f"⚠️ API Connection lost ({e}). Retrying in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    # Start Scapy in a background thread so it doesn't block Asyncio
    sniffer_thread = threading.Thread(target=run_sniffer, daemon=True)
    sniffer_thread.start()

    # Start the Async WebSocket stream
    try:
        asyncio.run(stream_to_api())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down live bridge.")
