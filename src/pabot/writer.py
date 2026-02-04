import threading
import queue
import sys
import os
import time

class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    ENDC = "\033[0m"
    SUPPORTED_OSES = {"posix"}  # Only Unix terminals support ANSI colors


class DottedConsole:
    def __init__(self):
        self._on_line = False

    def dot(self, char):
        print(char, end="", flush=True)
        self._on_line = True

    def newline(self):
        if self._on_line:
            print()
            self._on_line = False


class BufferingWriter:
    """
    Buffers partial writes until a newline is encountered.
    Useful for handling output that comes in fragments (e.g., from stderr).
    """
    def __init__(self, writer, level="info", original_stderr_name=None):
        self._writer = writer
        self._level = level
        self.original_stderr_name = original_stderr_name
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, msg):
        with self._lock:
            if not msg:
                return
            
            self._buffer += msg
            
            # Check if buffer contains newline(s)
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line:  # Only write non-empty lines
                    if self.original_stderr_name:
                        line = f"From {self.original_stderr_name}: {line}"
                    try:
                        self._writer.write(line, level=self._level)
                    except (RuntimeError, ValueError):
                        # Writer/stdout already closed
                        break

            # If buffer ends with partial content (no newline), keep it buffered
    
    def flush(self):
        with self._lock:
            if self._buffer:
                try:
                    self._writer.write(self._buffer, level=self._level)
                except (RuntimeError, ValueError):
                    pass
                self._buffer = ""


class ThreadSafeWriter:
    def __init__(self, writer, level="info"):
        self._writer = writer
        self._lock = threading.Lock()
        self._level = level  # Default level for this writer instance

    def write(self, msg, level=None):
        # Use provided level or fall back to instance default
        msg_level = level if level is not None else self._level
        with self._lock:
            self._writer.write(msg, level=msg_level)

    def flush(self):
        with self._lock:
            self._writer.flush()


class MessageWriter:
    def __init__(self, log_file=None, console_type="verbose"):
        self.queue = queue.Queue(maxsize=10000)
        self.log_file = log_file
        self.console_type = console_type
        self.console = DottedConsole() if console_type == "dotted" else None
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._writer)
        self.thread.daemon = False
        self.thread.start()

    def _is_output_coloring_supported(self):
        return sys.stdout.isatty() and os.name in Color.SUPPORTED_OSES

    def _wrap_with(self, color, message):
        if self._is_output_coloring_supported() and color:
            return f"{color}{message}{Color.ENDC}"
        return message


    def _should_print_to_console(self, console_type=None, level="debug"):
        """
        Determine if message should be printed to console based on console_type and level.
        Always write to log file.
        
        Args:
            console_type: The console type mode. If None, uses instance default.
            level: Message level (debug, info, warning, error, and spesial results infos: info_passed, info_failed, info_skipped, info_ignored). Defaults to debug.
        """
        ct = console_type if console_type is not None else self.console_type

        # Map levels to importance: debug < info_passed/info_ignored/info_skipped < info_failed < info < warning < error
        level_map = {"debug": 0, "info_passed": 1, "info_ignored": 1, "info_skipped": 1, "info_failed": 2, "info": 3, "warning": 4, "error": 5}
        message_level = level_map.get(level, 0)  # default to debug
        
        if ct == "none":
            return False
        elif ct == "quiet":
            # In quiet mode, show only warning and error level messages
            return message_level >= 3
        elif ct == "dotted":
            # In dotted mode, show test result indicators (info_passed/failed/skipped/ignored) and warnings/errors
            return message_level >= 1
        # verbose mode - print everything
        return True

    def _flush_batch(self, batch, log_f):
        for message, color, level in batch:
            # Log file
            if log_f:
                lvl = f"[{level.split('_')[0].upper()}]".ljust(9)
                log_f.write(f"{lvl} {message}\n")

            # Console
            if self._should_print_to_console(level=level):
                if self.console:
                    if level == "info_passed":
                        self.console.dot(self._wrap_with(color, "."))
                    elif level == "info_failed":
                        self.console.dot(self._wrap_with(color, "F"))
                    elif level in ("info_ignored", "info_skipped"):
                        self.console.dot(self._wrap_with(color, "s"))
                    else:
                        self.console.newline()
                        print(self._wrap_with(color, message))
                else:
                    print(self._wrap_with(color, message))
                    
    def _writer(self):
        log_f = None
        try:
            if self.log_file:
                log_f = open(self.log_file, "a", encoding="utf-8", buffering=1)

            buffer = []
            last_flush = time.time()
            FLUSH_INTERVAL = 0.2       # secs
            BATCH_SIZE = 50            # rows

            while True:
                try:
                    item = self.queue.get(timeout=0.1)
                except queue.Empty:
                    # Timebased flush
                    if buffer and (time.time() - last_flush) > FLUSH_INTERVAL:
                        self._flush_batch(buffer, log_f)
                        buffer.clear()
                        last_flush = time.time()
                    if self._stop_event.is_set():
                        break
                    continue

                message, color, level = item

                if message is None:
                    self.queue.task_done()
                    break

                message = message.rstrip("\n")

                buffer.append((message, color, level))
                self.queue.task_done()

                # Batch full → flush
                if len(buffer) >= BATCH_SIZE:
                    self._flush_batch(buffer, log_f)
                    buffer.clear()
                    last_flush = time.time()

            # Final flush
            if buffer:
                self._flush_batch(buffer, log_f)

        except Exception:
            import traceback
            traceback.print_exc()

        finally:
            if log_f:
                try:
                    log_f.flush()
                    log_f.close()
                except Exception:
                    pass


    def write(self, message, color=None, level="info"):
        if self._stop_event.is_set():
            return
        try:
            self.queue.put((f"{message}", color, level), timeout=0.1)
        except queue.Full:
            pass  # drop
        
    def flush(self, timeout=5):
        end = time.time() + timeout
        try:
            while time.time() < end:
                if self.queue.unfinished_tasks == 0:
                    return True
                time.sleep(0.05)
            return False
        except KeyboardInterrupt:
            # Allow tests/cli to interrupt flushing
            return False

    def stop(self):
        """
        Gracefully stop the writer thread and flush remaining messages.
        """
        self._stop_event.set()
        try:
            self.queue.put_nowait((None, None, None))
        except queue.Full:
            pass
        self.thread.join(timeout=2)


_writer_instance = None

def get_writer(log_dir=None, console_type="verbose"):
    global _writer_instance
    if _writer_instance is None:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir or ".", "pabot_manager.log")
        _writer_instance = MessageWriter(log_file=log_file, console_type=console_type)
    return _writer_instance

def get_stdout_writer(log_dir=None, console_type="verbose"):
    """Get a writer configured for stdout with 'info' level"""
    return ThreadSafeWriter(get_writer(log_dir, console_type), level="info")

def get_stderr_writer(log_dir=None, console_type="verbose", original_stderr_name: str = None):
    """Get a writer configured for stderr with 'error' level, buffered to handle partial writes"""
    # Use BufferingWriter to combine fragments that come without newlines
    buffering_writer = BufferingWriter(get_writer(log_dir, console_type), level="error", original_stderr_name=original_stderr_name)
    return buffering_writer
