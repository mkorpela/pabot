import threading
import time
from pabot.writer import get_writer

def worker(writer, start, end, delay=0.1):
    """Simulates a single worker writing log output with a small delay."""
    for i in range(start, end):
        writer.write(f"step {i}")
        time.sleep(delay)


def test_pabot_console_streaming_realtime():
    """
    Tests Pabot console streaming with multiple "workers".
    Fails if output is excessively buffered (i.e., not near-real-time).
    """
    # Get the MessageWriter directly (not ThreadSafeWriter)
    # Use console_type='none' to capture logs in memory instead of printing
    writer = get_writer(console_type="none")

    # List to capture timestamps of each log
    log_times = []

    # Override writer.write to capture timestamps
    original_write = writer.write
    def capture_write(msg, color=None, level="info"):
        log_times.append(time.time())
        original_write(msg, color=color, level=level)

    writer.write = capture_write

    threads = []
    num_workers = 8
    steps_per_worker = 100
    sleep_delay = 0.05
    max_interval_threshold = 0.1  # Max allowed interval between log messages (in seconds)

    # Start worker threads
    for w in range(num_workers):
        t = threading.Thread(
            target=worker,
            args=(writer, w * steps_per_worker, (w + 1) * steps_per_worker, sleep_delay),
        )
        t.start()
        threads.append(t)

    # Wait for all threads to finish
    for t in threads:
        t.join()

    # Ensure all queued messages are flushed
    writer.flush(timeout=5)
    # Stop the background writer thread
    writer.stop()

    # Calculate intervals between log messages
    intervals = [t2 - t1 for t1, t2 in zip(log_times, log_times[1:])]
    max_interval = max(intervals) if intervals else 0.0

    print(f"Max interval between log messages: {max_interval:.3f}s")

    # Fail if any interval is too long (i.e., buffering happened)
    assert max_interval < max_interval_threshold, f"Console output appears buffered, max interval={max_interval:.3f}s"
