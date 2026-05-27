import sqlite3
import random
import time
import threading

class TelemetryPipeline:
    """
    Simulates a NetFlow/sFlow ingest pipeline.
    Captures live traffic states and stores them in a fast buffer (SQLite here)
    for the RL agent to query link utilization.
    """
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._setup_db()

        # Valid links in our mock topology
        self.links = [
            ("Router_A", "Router_B"),
            ("Router_A", "Router_C"),
            ("Router_B", "Router_D"),
            ("Router_C", "Router_D"),
            ("Router_D", "Server_Farm")
        ]

    def _setup_db(self):
        """Creates the schema for fast time-series ingest."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetry (
                timestamp REAL,
                source_ip TEXT,
                dest_ip TEXT,
                link_source TEXT,
                link_target TEXT,
                bytes_sec REAL
            )
        ''')
        # Index for fast retrieval of latest records
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON telemetry(timestamp)
        ''')
        self.conn.commit()

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
        self.cursor.executemany('''
            INSERT INTO telemetry (timestamp, source_ip, dest_ip, link_source, link_target, bytes_sec)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', records)
        self.conn.commit()

        # Housekeeping: prune old records to keep the buffer fast
        # Only keep the last 60 seconds of data
        prune_time = time.time() - 60
        self.cursor.execute('DELETE FROM telemetry WHERE timestamp < ?', (prune_time,))
        self.conn.commit()

    def get_latest_utilization(self):
        """
        Fast query interface for app_brains.py.
        Returns the aggregated bandwidth utilization (bytes/sec) per link
        over the last 5 seconds to calculate the RL state observation.
        """
        cutoff_time = time.time() - 5

        # Aggregate bytes per second for each link in the last 5 seconds
        self.cursor.execute('''
            SELECT link_source, link_target, SUM(bytes_sec) / 5.0 as avg_bytes_sec
            FROM telemetry
            WHERE timestamp >= ?
            GROUP BY link_source, link_target
        ''', (cutoff_time,))

        results = self.cursor.fetchall()

        # Format as a dictionary for easy access by the AI
        utilization = {}
        for row in results:
            link_id = f"{row[0]}-{row[1]}"
            utilization[link_id] = round(row[2], 2)

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
