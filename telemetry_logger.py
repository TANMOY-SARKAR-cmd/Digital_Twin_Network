import csv
import os
import queue
import threading
import time
import atexit

# Move out of 'data/' to prevent breaking dataset globbing
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, f"live_feedback_{os.getpid()}.csv")

# Bounded queue to prevent OOM
telemetry_queue = queue.Queue(maxsize=int(os.getenv("TELEMETRY_QUEUE_MAXSIZE", "10000")))

_writer_started = False
_writer_start_lock = threading.Lock()

def _writer_worker():
    os.makedirs(LOG_DIR, exist_ok=True)
    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "state_0", "state_1", "state_2", "state_3", "state_4", "state_5", "action", "reward"])

        while True:
            record = telemetry_queue.get()
            try:
                if record is None:  # Shutdown sentinel
                    break
                writer.writerow(record)
                f.flush()
            except Exception as e:
                print(f"Telemetry Logger Error: {e}")
                time.sleep(1)  # Prevent tight error loop
            finally:
                telemetry_queue.task_done()

def _ensure_writer_started():
    global _writer_started
    if _writer_started:
        return
    with _writer_start_lock:
        if _writer_started:
            return
        writer_thread = threading.Thread(target=_writer_worker, daemon=True)
        writer_thread.start()
        _writer_started = True

def _shutdown_writer():
    if _writer_started:
        try:
            telemetry_queue.put_nowait(None)
        except queue.Full:
            pass

atexit.register(_shutdown_writer)

def log_transition(state_vector, action, reward):
    """Pushes a state-action-reward tuple to the background CSV writer."""
    _ensure_writer_started()

    state_list = state_vector.tolist() if hasattr(state_vector, "tolist") else list(state_vector)
    record = [time.time()] + state_list + [action, reward]

    try:
        telemetry_queue.put_nowait(record)
    except queue.Full:
        pass  # Drop telemetry rather than blocking the inference path
