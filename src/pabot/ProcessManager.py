import os
import sys
import time
import threading
import subprocess
import datetime
import queue
import locale
import signal

try:
    import psutil
except ImportError:
    psutil = None

from .writer import get_writer, Color


def split_on_first(lst, value):
    for i, x in enumerate(lst):
        if x == value:
            return lst[:i], lst[i+1:]
    return lst, []


class ProcessManager:
    def __init__(self):
        self.processes = []
        self.lock = threading.Lock()
        self.writer = get_writer()
        self.interrupted = False
        # Note: Signal handling is done in pabot.py's main_program() to ensure
        # PabotLib is shut down gracefully before process termination
        # This ProcessManager will check the interrupted flag set by pabot.py's keyboard_interrupt()

    def set_interrupted(self):
        """Called by pabot.py when CTRL+C is received."""
        self.interrupted = True

    # -------------------------------
    # OUTPUT STREAM READERS
    # -------------------------------

    def _enqueue_output(self, pipe, q):
        """
        Reads lines from `pipe` and puts them into queue `q`.
        When pipe is exhausted, pushes `None` sentinel.
        """
        try:
            with pipe:
                for line in iter(pipe.readline, b""):
                    q.put(line)
        finally:
            q.put(None)  # sentinel → "this stream is finished"

    def _safe_write_to_stream(self, stream, text):
        """
        Writes text safely to an output stream.
        If encoding errors occur, fall back to bytes/replace.
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
            pass

        enc = getattr(stream, "encoding", None) or locale.getpreferredencoding(False) or "utf-8"

        try:
            b = text.encode(enc, errors="replace")
            if hasattr(stream, "buffer"):
                try:
                    stream.buffer.write(b)
                    stream.buffer.write(b"\n")
                    stream.buffer.flush()
                    return
                except Exception:
                    pass

            safe = b.decode(enc, errors="replace")
            stream.write(safe + "\n")
            stream.flush()
        except Exception:
            try:
                print(text)
            except Exception:
                pass

    # -------------------------------
    # STREAM OUTPUT MERGER
    # -------------------------------

    def _stream_output(self, process, stdout=None, stderr=None,
                       item_name="process", log_file=None):

        q_out = queue.Queue()
        q_err = queue.Queue()

        t_out = None
        t_err = None

        if process.stdout:
            t_out = threading.Thread(target=self._enqueue_output, args=(process.stdout, q_out))
            t_out.daemon = True
            t_out.start()

        if process.stderr:
            t_err = threading.Thread(target=self._enqueue_output, args=(process.stderr, q_err))
            t_err.daemon = True
            t_err.start()

        stdout_done = False
        stderr_done = False

        log_handle = None
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            log_handle = open(log_file, "a", encoding="utf-8")

        try:
            while True:
                now = datetime.datetime.now()

                # STDOUT
                if not stdout_done:
                    try:
                        line = q_out.get(timeout=0.05)
                        if line is None:
                            stdout_done = True
                        else:
                            msg = line.decode(errors="replace").rstrip()
                            self._safe_write_to_stream(stdout or sys.stdout, msg + "\n")
                            if log_handle:
                                log_handle.write(f"{now} {msg}\n")
                    except queue.Empty:
                        pass

                # STDERR
                if not stderr_done:
                    try:
                        line = q_err.get_nowait()
                        if line is None:
                            stderr_done = True
                        else:
                            msg = line.decode(errors="replace").rstrip()
                            self._safe_write_to_stream(stderr or sys.stderr, msg + "\n")
                            if log_handle:
                                log_handle.write(f"{now} {msg}\n")
                    except queue.Empty:
                        pass

                # Terminate when both streams finished
                if stdout_done and stderr_done:
                    break

        finally:
            if t_out:
                t_out.join()
            if t_err:
                t_err.join()
            if log_handle:
                log_handle.close()

    # -------------------------------
    # PROCESS CREATION
    # -------------------------------

    def _start_process(self, cmd, env=None):
        if sys.platform == "win32":
            return subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            return subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=False,
                preexec_fn=os.setsid,
            )

    # -------------------------------
    # PROCESS TREE TERMINATION
    # -------------------------------

    def _terminate_tree(self, process):
        if process.poll() is not None:
            return

        self.writer.write(
            f"[ProcessManager] Terminating process tree PID={process.pid}",
            level='debug'
        )

        # PRIMARY: psutil (best reliability)
        if psutil:
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for c in children:
                    try:
                        c.terminate()
                    except Exception:
                        pass
                psutil.wait_procs(children, timeout=5)

                for c in children:
                    if c.is_running():
                        try:
                            c.kill()
                        except Exception:
                            pass

                try:
                    parent.terminate()
                except Exception:
                    pass

                try:
                    parent.wait(timeout=5)
                except psutil.TimeoutExpired:
                    try:
                        parent.kill()
                    except Exception:
                        pass

                return
            except Exception:
                pass

        # FALLBACK — Windows
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return

        # FALLBACK — Linux / macOS
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            time.sleep(2)
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception:
            if process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass

        try:
            process.wait(timeout=5)
        except Exception:
            pass

    # -------------------------------
    # PUBLIC API
    # -------------------------------

    def terminate_all(self):
        with self.lock:
            for p in list(self.processes):
                self._terminate_tree(p)
            self.processes.clear()

    def run(self, cmd, *, env=None, stdout=None, stderr=None,
            timeout=None, verbose=False, item_name="process",
            log_file=None, pool_id=0, item_index=0):

        start = time.time()
        process = self._start_process(cmd, env)

        with self.lock:
            self.processes.append(process)

        ts = datetime.datetime.now()

        if verbose:
            self.writer.write(
                f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] "
                f"EXECUTING PARALLEL {item_name}:\n{' '.join(cmd)}",
                level='debug'
            )
        else:
            self.writer.write(
                f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] EXECUTING {item_name}",
                level='debug'
            )

        # Start logging thread
        log_thread = threading.Thread(
            target=self._stream_output,
            args=(process, stdout, stderr, item_name, log_file),
        )
        log_thread.daemon = True
        log_thread.start()

        rc = None
        ping_interval = 50   # 5s
        next_ping = ping_interval
        counter = 0

        while rc is None:
            rc = process.poll()

            # INTERRUPT CHECK - terminate process gracefully when CTRL+C is pressed
            if self.interrupted:
                ts = datetime.datetime.now()
                self.writer.write(
                    f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] "
                    f"Process {item_name} interrupted by user (Ctrl+C)",
                    color=Color.YELLOW, level='warning'
                )
                self._terminate_tree(process)
                rc = -1

                # Dryrun process to mark all tests as failed due to user interrupt
                this_dir = os.path.dirname(os.path.abspath(__file__))
                listener_path = os.path.join(this_dir, "listener", "interrupt_listener.py")
                dry_run_env = env.copy() if env else os.environ.copy()
                before, after = split_on_first(cmd, "-A")
                dryrun_cmd = before + ["--dryrun", '--exitonerror', '--listener', listener_path, '-A'] + after

                self.writer.write(
                    f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] "
                    f"Starting dry run to mark test as failed due to user interrupt: {' '.join(dryrun_cmd)}",
                    level='debug'
                )
                try:
                    subprocess.run(
                        dryrun_cmd,
                        env=dry_run_env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=3,
                        text=True,
                    )
                except subprocess.TimeoutExpired as e:
                    self.writer.write(f"Dry-run timed out after 3s: {e}", level='debug')
                break

            # TIMEOUT CHECK
            if timeout and (time.time() - start > timeout):
                ts = datetime.datetime.now()
                self.writer.write(
                    f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] "
                    f"Process {item_name} killed due to exceeding the maximum timeout of {timeout} seconds",
                    color=Color.YELLOW, level='warning'
                )
                self._terminate_tree(process)
                rc = -1

                # Dryrun process to mark all tests as failed due to timeout
                this_dir = os.path.dirname(os.path.abspath(__file__))
                listener_path = os.path.join(this_dir, "listener", "timeout_listener.py")
                dry_run_env = env.copy() if env else os.environ.copy()
                before, after = split_on_first(cmd, "-A")
                dryrun_cmd = before + ["--dryrun", '--exitonerror', '--listener', listener_path, '-A'] + after

                self.writer.write(
                    f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] "
                    f"Starting dry run to mark test as failed due to timeout: {' '.join(dryrun_cmd)}",
                    level='debug'
                )
                try:
                    subprocess.run(
                        dryrun_cmd,
                        env=dry_run_env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=3,
                        text=True,
                    )
                except subprocess.TimeoutExpired as e:
                    self.writer.write(f"Dry-run timed out after 3s: {e}", level='debug')

                break

            # Progress ping
            if counter == next_ping:
                ts = datetime.datetime.now()
                self.writer.write(
                    f"{ts} [PID:{process.pid}] [{pool_id}] [ID:{item_index}] still running "
                    f"{item_name} after {(counter * 0.1):.1f}s",
                    level='debug'
                )
                ping_interval += 50
                next_ping += ping_interval

            time.sleep(0.1)
            counter += 1

        log_thread.join()

        elapsed = round(time.time() - start, 1)

        with self.lock:
            if process in self.processes:
                self.processes.remove(process)

        return process, (rc, elapsed)
