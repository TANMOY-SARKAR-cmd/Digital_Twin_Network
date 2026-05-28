import random
import time
import threading

class TelemetryPipeline:
    """
    Simulates a NetFlow/sFlow ingest pipeline.
    Captures live traffic states and stores them in a fast buffer
    for the RL agent to query link utilization.
    """
    def __init__(self, db_path=":memory:"):
        self.buffer = __import__('collections').deque(maxlen=20000)

        # Valid links in our mock topology
        self.links = [
            ("Router_A", "Router_B"),
            ("Router_A", "Router_C"),
            ("Router_B", "Router_D"),
            ("Router_C", "Router_D"),
            ("Router_D", "Server_Farm")
        ]

    def generate_mock_netflow(self):
        """
        Simulates the arrival of a batch of NetFlow records.
        """
        records = []
        now = time.time()
        for link in self.links:
            # Generate baseline background traffic + some noise
            base_traffic = random.uniform(10_000, 50_000) # bytes/sec

            # Occasionally simulate a burst (e.g., video stream or download)
            if random.random() > 0.9:
                base_traffic += random.uniform(100_000, 500_000)

            src_ip = f"10.0.{random.randint(1, 10)}.{random.randint(2, 254)}"
            dst_ip = f"192.168.1.{random.randint(2, 254)}"

            records.append((
                now,
                src_ip,
                dst_ip,
                link[0], # link source
                link[1], # link target
                base_traffic
            ))

        return records

    def ingest_telemetry(self, records):
        """Batch inserts the streaming telemetry."""
        for r in records:
            self.buffer.append(r)

    def get_latest_utilization(self):
        """
        Fast query interface for app_brains.py.
        Returns the aggregated bandwidth utilization (bytes/sec) per link
        over the last 5 seconds to calculate the RL state observation.
        """
        cutoff = time.time() - 5
        recent = [r for r in self.buffer if r[0] >= cutoff]

        sums = {}
        for r in recent:
            # r: (now, src_ip, dst_ip, link_src, link_target, bytes)
            link_id = f"{r[3]}-{r[4]}"
            sums[link_id] = sums.get(link_id, 0) + r[5]

        utilization = {}
        for link_id, total_bytes in sums.items():
            utilization[link_id] = round(total_bytes / 5.0, 2)

        return utilization

    def run_generator_loop(self):
        """Background thread that constantly pumps data into the pipeline."""
        print("📊 Starting Telemetry Ingest Pipeline...")
        while True:
            try:
                records = self.generate_mock_netflow()
                self.ingest_telemetry(records)
                # NetFlow records typically export every 1 second in fast environments
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Telemetry generation error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    pipeline = TelemetryPipeline()

    # Start the background generator
    generator_thread = threading.Thread(target=pipeline.run_generator_loop, daemon=True)
    generator_thread.start()

    # Simulate app_brains.py polling for state updates
    try:
        for _ in range(5):
            time.sleep(2)
            utilization = pipeline.get_latest_utilization()
            print(f"📈 Current Link Utilization: {utilization}")
    except KeyboardInterrupt:
        print("\n🛑 Telemetry Pipeline Shutting Down.")
