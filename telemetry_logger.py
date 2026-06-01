import csv
import os
import queue
import threading
import time

LOG_FILE = "data/live_feedback.csv"
telemetry_queue = queue.Queue()


def _writer_worker():
    # Ensure directory exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Write header if file doesn't exist
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp", "state_0", "state_1", "state_2", "state_3",
                "state_4", "state_5", "action", "reward"
            ])

        while True:
            try:
                record = telemetry_queue.get()
                if record is None:
                    break  # Stop signal
                writer.writerow(record)
                f.flush()
            except Exception as e:
                print(f"Telemetry Logger Error: {e}")


# Start the background writer thread
writer_thread = threading.Thread(target=_writer_worker, daemon=True)
writer_thread.start()


def log_transition(state_vector, action, reward):
    """Pushes a state-action-reward tuple to the background CSV writer."""
    record = [time.time()] + list(state_vector) + [action, reward]
    telemetry_queue.put(record)
