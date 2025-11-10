import threading
import queue
import sys
import os
import datetime

class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    ENDC = "\033[0m"
    SUPPORTED_OSES = {"posix"}  # Only Unix terminals support ANSI colors


class MessageWriter:
    def __init__(self, log_file=None):
        self.queue = queue.Queue()
        self.log_file = log_file
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._writer)
        self.thread.daemon = True
        self.thread.start()

    def _is_output_coloring_supported(self):
        return sys.stdout.isatty() and os.name in Color.SUPPORTED_OSES

    def _wrap_with(self, color, message):
        if self._is_output_coloring_supported() and color:
            return f"{color}{message}{Color.ENDC}"
        return message

    def _writer(self):
        while not self._stop_event.is_set():
            try:
                message, color = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if message is None:
                self.queue.task_done()
                break
            print(self._wrap_with(color, message))
            sys.stdout.flush()
            if self.log_file:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
            self.queue.task_done()

    def write(self, message, color=None):
        self.queue.put((f"{message}", color))

    def flush(self):
        """
        Wait until all queued messages have been written.
        Safe to call multiple times; non-blocking if queue is empty.
        """
        while not self.queue.empty():
            try:
                self.queue.join()  # blocks until all tasks are marked done
                break
            except KeyboardInterrupt:
                break

    def stop(self):
        """
        Gracefully stop the writer thread and flush remaining messages.
        """
        self.flush()
        self._stop_event.set()
        self.queue.put((None, None))  # sentinel to break thread loop
        self.thread.join(timeout=1.0)


_writer_instance = None

def get_writer(log_dir=None):
    global _writer_instance
    if _writer_instance is None:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir or ".", "pabot_manager.log")
        _writer_instance = MessageWriter(log_file=log_file)
    return _writer_instance
