import unittest
import tempfile
import shutil
import subprocess
import sys
import re
import time
import textwrap
import os
import signal
from pathlib import Path
from typing import List


def _assert_runtime_at_least(output: str, min_seconds: float, max_seconds: float):
    """Parse Pabot stdout and assert that 'Total testing: X seconds' fits within expected range."""
    match = re.search(r"Total testing:\s*([\d.]+)\s*seconds", output)
    if not match:
        raise AssertionError("Could not find 'Total testing' in Pabot output")

    total_time = float(match.group(1))
    if total_time < min_seconds:
        raise AssertionError(f"Total testing time {total_time}s is less than expected {min_seconds}s")
    if total_time > max_seconds:
        raise AssertionError(f"Total testing time {total_time}s exceeds maximum expected {max_seconds}s")


class PabotProcessHandlingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create one temporary root directory for all suites
        cls.tmpdir = tempfile.mkdtemp(prefix="pabot_test_")
        cls.suites_dir = Path(cls.tmpdir)

        # --- Fast suite ---
        cls.fast_suite = cls.suites_dir / "fast_suite.robot"
        cls.fast_suite.write_text(
            "*** Test Cases ***\n"
            "Quick Test\n"
            "    Log    This test should finish fast.\n"
        )

        # --- Slow suite ---
        cls.slow_suite = cls.suites_dir / "slow_suite.robot"
        cls.slow_suite.write_text(
            "*** Test Cases ***\n"
            "Slow Test\n"
            "    Sleep    30s\n"
        )

        # --- Chain process & heartbeat ---
        cls.heartbeat_file = cls.suites_dir / f"heartbeat_{os.getpid()}.txt"
        chain_script = cls.suites_dir / "chain_process.py"
        chain_script_robot = str(chain_script).replace("/", "${/}").replace("\\", "${/}")

        with open(chain_script, "w", encoding="utf-8") as f:
            f.write(
                textwrap.dedent(f"""
                import time, os
                heartbeat_file = r'{cls.heartbeat_file}'
                with open(heartbeat_file, 'w') as f:
                    f.write(f"PID:{{os.getpid()}}\\n")
                    f.flush()
                    for _ in range(60):
                        f.write(str(time.time()) + '\\n')
                        f.flush()
                        time.sleep(1)
                """)
            )

        # --- Chain suite ---
        cls.chain_suite = cls.suites_dir / "chain_suite.robot"
        cls.chain_suite.write_text(
            textwrap.dedent(f"""
            *** Settings ***
            Library    Process
            Library    OperatingSystem

            *** Test Cases ***
            Chain Test
                Run Keyword    Start Chain Process

            *** Keywords ***
            Start Chain Process
                File Should Exist   {chain_script_robot}
                Run Process    python    {chain_script_robot}
            """)
        )


    def setUp(self):
        """Each test gets its own pabot output directory."""
        self.test_output_dir = self.suites_dir / f"results_{self._testMethodName}"
        self.test_output_dir.mkdir(exist_ok=True)


    def _run_with_process_counts(self, suites, timeout=None, process_counts: List[int] = [2]):
        """Run pabot with given suites and process counts."""
        for proc_count in process_counts:
            result_dir = self.test_output_dir / f"p{proc_count}"
            result_dir.mkdir(exist_ok=True)
            cmd = [
                sys.executable,
                "-m", "pabot.pabot",
                "--testlevelsplit",
                "--processes", str(proc_count),
                "--outputdir", str(result_dir)
            ]
            if timeout:
                cmd += ["--processtimeout", str(timeout)]
            cmd += [str(s) for s in suites]

                        
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                creationflags = 0

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if sys.platform != "win32" else None,
                creationflags=creationflags
            )
            yield result, result_dir, proc_count


    def test_multiple_fast_suites(self):
        """Ensure multiple fast suites run in parallel successfully with different process counts."""
        timeout = 3
        for result, result_dir, proc_count in self._run_with_process_counts([self.fast_suite, self.fast_suite], timeout=timeout):
            with self.subTest(processes=proc_count):
                self.assertEqual(result.returncode, 0, f"Pabot failed:\n{result.stderr}")
                self.assertTrue((result_dir / "output.xml").exists(), "Output file missing")
                self.assertIn("2 tests, 2 passed, 0 failed, 0 skipped.", result.stdout)
                _assert_runtime_at_least(result.stdout, 0, timeout + 2)
                self.assertEqual("", result.stderr)


    def test_long_running_suite_timeout(self):
        """Verify Pabot terminates long-running suite on timeout."""
        timeout = 3
        for result, _, _ in self._run_with_process_counts([self.slow_suite], timeout=timeout):
            self.assertNotEqual(result.returncode, 0, "Expected timeout")
            self.assertIn(f"Process Slow Suite.Slow Test killed due to exceeding the maximum timeout of {timeout} seconds", result.stdout)
            _assert_runtime_at_least(result.stdout, timeout, timeout + 2)
            self.assertIn("[ ERROR ] Suite '' contains no tests.", result.stderr)


    def test_chain_process_cleanup(self):
        """Ensure chain subprocesses terminate after --processtimeout; no zombie remains."""
        timeout = 3
        for result, _, _ in self._run_with_process_counts([self.chain_suite], timeout=timeout):
            time.sleep(2 * timeout)
            if self.heartbeat_file.exists():
                lines = self.heartbeat_file.read_text().splitlines()
                if lines and lines[0].startswith("PID:"):
                    pid = int(lines[0].split(":", 1)[1])
                    # Verify process is gone
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        pass
                    else:
                        raise AssertionError(f"PID {pid} still alive — possible zombie.")
            _assert_runtime_at_least(result.stdout, timeout, timeout + 2)
            self.assertIn("[ ERROR ] Suite '' contains no tests.", result.stderr)


    def tearDown(self):
        """Clean up heartbeat and any leftover processes."""
        if self.heartbeat_file.exists():
            try:
                first = self.heartbeat_file.read_text().splitlines()[0]
                if first.startswith("PID:"):
                    pid = int(first.split(":", 1)[1])
                    # Kill if alive
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        pass
                    else:
                        if os.name == "nt":
                            subprocess.call(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            os.killpg(os.getpgid(pid), signal.SIGTERM)
                            time.sleep(0.5)
                            try:
                                os.kill(pid, 0)
                            except OSError:
                                pass
                            else:
                                os.killpg(os.getpgid(pid), signal.SIGKILL)
            finally:
                self.heartbeat_file.unlink(missing_ok=True)


    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)
