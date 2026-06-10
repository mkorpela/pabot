import os
import threading
import time

from pabot.writer import MessageWriter


def test_messagewriter_flush_blocks_until_queue_drains(tmp_path, monkeypatch):
    writer = MessageWriter(log_file=str(tmp_path / "pabot.log"), console_type="none")
    stop_event = threading.Event()

    original_flush_batch = writer._flush_batch

    def blocking_flush_batch(batch, log_f):
        stop_event.wait(timeout=5)
        return original_flush_batch(batch, log_f)

    monkeypatch.setattr(writer, "_flush_batch", blocking_flush_batch)

    try:
        for i in range(200):
            writer.write(f"msg-{i}", level="info")

        time.sleep(0.01)
        assert writer.queue.unfinished_tasks != 0

        t0 = time.perf_counter()
        ok1 = writer.flush(timeout=0.05)
        assert ok1 is False
        assert (time.perf_counter() - t0) < 0.5

        stop_event.set()

        t1 = time.perf_counter()
        ok2 = writer.flush(timeout=2)
        assert ok2 is True
        assert (time.perf_counter() - t1) < 0.5

    finally:
        writer.stop()


def test_messagewriter_flush_timeout_none_waits_until_drained(tmp_path):
    writer = MessageWriter(log_file=str(tmp_path / "pabot.log"), console_type="none")
    try:
        for i in range(10):
            writer.write(f"msg-{i}", level="info")
        assert writer.flush(timeout=None) is True
    finally:
        writer.stop()
