import os
import sys
import time
import signal
import threading
import subprocess
import datetime
import queue
import locale

try:
    import psutil
except ImportError:
    psutil = None

from .writer import get_writer, Color

class ProcessManager:
    def __init__(self):
        self.processes = []
        self.lock = threading.Lock()
        self.writer = get_writer()
        # Register SIGINT only in main thread (test-safe)
        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, self._handle_sigint)
            else:
                self.writer.write(
                    "[ProcessManager] (test mode) signal handlers disabled (not main thread)"
                )
        except Exception as e:
            self.writer.write(f"[WARN] Could not register signal handler: {e}")


    def _handle_sigint(self, signum, frame):
        self.writer.write("[ProcessManager] Ctrl+C detected — terminating all subprocesses", color=Color.RED)
        self.terminate_all()
        sys.exit(130)


    def _enqueue_output(self, pipe, queue):
        try:
            with pipe:
                for line in iter(pipe.readline, b""):
                    queue.put(line)
        finally:
            pipe.close()


    def _safe_write_to_stream(self, stream, text):
        """
        Try to write `text` to a text stream. If the stream cannot encode characters,
        fall back to writing encoded bytes to stream.buffer (if available) with errors='replace'.
        If even that isn't possible, fallback to print() to avoid crashing the thread.
        """
        try:
            stream.write(text)
            try:
                stream.flush()
            except Exception:
                pass
            return
        except UnicodeEncodeError:
            pass
        except Exception:
            # Some streams might raise weird errors; fallback below
            pass

        # Determine encoding to use (prefer stream.encoding, else system preferred)
        enc = getattr(stream, "encoding", None) or locale.getpreferredencoding(False) or "utf-8"
        try:
            b = (text).encode(enc, errors="replace")
            buf = getattr(stream, "buffer", None)
            if buf is not None:
                try:
                    buf.write(b)
                    buf.write(b"\n")
                    try:
                        buf.flush()
                    except Exception:
                        pass
                    return
                except Exception:
                    # Fall through to fallback print
                    pass

            # If no buffer, try writing decoded back to stream with safe decode
            safe = b.decode(enc, errors="replace")
            try:
                stream.write(safe + "\n")
                try:
                    stream.flush()
                except Exception:
                    pass
                return
            except Exception:
                pass
        except Exception:
            pass

        # Last resort — use print to original stdout to avoid crashing
        try:
            print(text)
        except Exception:
            # give up silently (we don't want to crash the worker thread)
            return


    def _stream_output(
            self, process, stdout=None, stderr=None,
            item_name="process", log_file=None
        ):
        q_stdout, q_stderr = queue.Queue(), queue.Queue()
        threads = []

        if process.stdout:
            t_out = threading.Thread(target=self._enqueue_output, args=(process.stdout, q_stdout))
            t_out.daemon = True
            t_out.start()
            threads.append(t_out)
        if process.stderr:
            t_err = threading.Thread(target=self._enqueue_output, args=(process.stderr, q_stderr))
            t_err.daemon = True
            t_err.start()
            threads.append(t_err)

        log_handle = None
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            log_handle = open(log_file, "a", encoding="utf-8")

        try:
            while True:
                ts = datetime.datetime.now()
                try:
                    line = q_stdout.get_nowait()
                    if line:
                        msg = line.decode(errors="replace").rstrip()
                        formatted = f"{ts} {msg}"
                        target_out = stdout or sys.stdout
                        self._safe_write_to_stream(target_out, f"{msg}\n")
                        if log_handle:
                            log_handle.write(formatted + "\n")
                except queue.Empty:
                    pass

                try:
                    line = q_stderr.get_nowait()
                    if line:
                        msg = line.decode(errors="replace").rstrip()
                        formatted = f"{ts} {msg}"
                        target_err = stderr or sys.stderr
                        self._safe_write_to_stream(target_err, f"{msg}\n")
                        if log_handle:
                            log_handle.write(formatted + "\n")
                except queue.Empty:
                    pass

                if process.poll() is not None and q_stdout.empty() and q_stderr.empty():
                    break
                time.sleep(0.05)
        finally:
            for t in threads:
                t.join(timeout=0.1)
            if log_handle:
                log_handle.close()


    def _start_process(self, cmd, env=None):
        if sys.platform == "win32":
            return subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=False,
            )
        else:
            return subprocess.Popen(
                cmd,
                preexec_fn=os.setsid,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=False,
            )


    def _terminate_tree(self, process):
        if process.poll() is not None:
            return

        self.writer.write(f"[ProcessManager] Terminating process tree PID={process.pid}", color=Color.YELLOW)

        if psutil:
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                psutil.wait_procs(children, timeout=3)
                for child in children:
                    if child.is_running():
                        child.kill()
                parent.terminate()
                parent.wait(timeout=3)
                return
            except Exception:
                pass

        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                time.sleep(2)
                if process.poll() is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                process.kill()
        try:
            process.wait(timeout=5)
        except Exception:
            pass


    def terminate_all(self):
        with self.lock:
            for p in list(self.processes):
                self._terminate_tree(p)
            self.processes.clear()


    def run(self, cmd, *, env=None, stdout=None, stderr=None,
            timeout=None, verbose=False, item_name="process",
            log_file=None, pool_id=0, item_index=0):
        """
        Run a subprocess with real-time streaming and optional logging to a file.
        """
        start_time = time.time()
        process = self._start_process(cmd, env=env)

        with self.lock:
            self.processes.append(process)

        ts = datetime.datetime.now()
        if verbose:
            self.writer.write(f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] EXECUTING PARALLEL {item_name} with command:\n{' '.join(cmd)}")
        else:
            self.writer.write(f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] EXECUTING {item_name}")

        # Start real-time logging with optional log file
        log_thread = threading.Thread(
            target=self._stream_output,
            args=(process, stdout, stderr, item_name, log_file)
        )
        log_thread.daemon = True
        log_thread.start()

        rc = None
        elapsed = 0
        ping_interval = 50  # Start value: 50 * 0.1s = 5s
        ping_time = ping_interval
        
        while rc is None:
            rc = process.poll()
            if timeout and (time.time() - start_time) > timeout:
                ts = datetime.datetime.now()
                self.writer.write(f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] Process {item_name} killed due to exceeding the maximum timeout of {timeout} seconds")
                self._terminate_tree(process)
                rc = -1
                break

            if elapsed == ping_time:
                ping_interval += 50        # Increasing increments: (5s, 10s, 15s etc.)
                ping_time += ping_interval
                self.writer.write(f"[PID:{process.pid}] [{pool_id}] [ID:{item_index}] still running {item_name} after {elapsed * 0.1:.1f} seconds")

            time.sleep(0.1)
            elapsed += 1

        log_thread.join()
        elapsed = round(time.time() - start_time, 1)

        with self.lock:
            if process in self.processes:
                self.processes.remove(process)

        return process, (rc, elapsed)
