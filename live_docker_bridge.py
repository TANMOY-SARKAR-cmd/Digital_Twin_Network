import asyncio
import websockets
import json
import os
import queue
import threading
import time
from scapy.all import sniff, IP, TCP

# Target API
URI = "ws://127.0.0.1:8000/ws/network"
# Sniff on all interfaces by default, or specify via env var
IFACE = os.getenv("IFACE", None)

# Shared queue to move packets from the Scapy thread to the Asyncio thread
# maxsize parsed from env
maxsize = int(os.getenv("PACKET_QUEUE_MAXSIZE", "10000"))
packet_queue = queue.Queue(maxsize=maxsize)

# Live TCP Latency Tracking
ema_latency = 0.01  # Default to 10ms
expected_acks = {}  # Dictionary to track packet transmission times
MAX_TRACK_SIZE = 5000  # Prevent OOM memory leaks during a SYN flood


def packet_handler(pkt):
    """Callback for Scapy to process packets and calc real-time TCP RTT."""
    global ema_latency

    if IP in pkt:
        src_ip = pkt[IP].src
        dst_ip = pkt[IP].dst
        pkt_len = len(pkt)
        protocol = pkt[IP].proto

        # --- LIVE TCP RTT CALCULATION ---
        if TCP in pkt:
            tcp_layer = pkt[TCP]
            current_time = time.time()

            # 1. Check if this packet is an ACK for something we sent
            ack_key = (src_ip, dst_ip, tcp_layer.ack)
            if ack_key in expected_acks:
                rtt = current_time - expected_acks.pop(ack_key)
                rtt = min(rtt, 2.0)   # Cap anomalies at 2 seconds

                # Update Exponential Moving Average (EMA) - 80% old, 20% new
                ema_latency = (0.8 * ema_latency) + (0.2 * rtt)

            # 2. Track this packet if it expects an ACK (Payload or SYN flag)
            payload_len = len(tcp_layer.payload)
            is_syn = tcp_layer.flags & 0x02

            if payload_len > 0 or is_syn:
                seq_next = tcp_layer.seq + \
                    (payload_len if payload_len > 0 else 1)
                track_key = (dst_ip, src_ip, seq_next)

                # Bounded dictionary (O(1) LRU eviction) to survive SYN floods
                if len(expected_acks) >= MAX_TRACK_SIZE:
                    expected_acks.pop(next(iter(expected_acks)))
                expected_acks[track_key] = current_time

        # --- BUILD AI PAYLOAD ---
        features = [0.0] * 40
        features[0] = float(protocol)
        features[1] = float(pkt_len)

        payload = {
            "features": features,
            "volume": float(pkt_len),
            "src_ip": src_ip,
            "ground_truth_attack": False,
            "lat_a": round(ema_latency, 4),   # 🔴 LIVE PHYSICAL LATENCY
            "lat_b": 0.05  # Static baseline for the blocked/mitigated state
        }

        try:
            packet_queue.put_nowait(payload)
        except queue.Full:
            pass  # Consumer is slower than producer; drop packet to avoid...


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

                        route_str = {
                            0: "Traffic Allowed",
                            1: "IP Blocked (Mitigating)"
                        }.get(route, f"Unknown ({route})")
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
