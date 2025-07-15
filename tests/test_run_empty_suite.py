import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess
from robot import __version__ as ROBOT_VERSION


class PabotRunEmptySuiteTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_tests(self, testfile):
        with open("{}/test.robot".format(self.tmpdir), "w") as robot_file:
            robot_file.write(textwrap.dedent(testfile))

    def _run_command(self, command):
        process = subprocess.Popen(
            command,
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return process.communicate()

    def test_run_empty_suite(self):
        """
        Test for: https://github.com/mkorpela/pabot/issues/531

        Runs 3 passing test cases first and then runs --rerunfailed with --runemptysuite option.
        """
        self._write_tests(
        """
        *** Test Cases ***
        First Test
            Log  1

        Second Test
            Log  2

        Third Test
            Log  3
        """
        )
        command1 = [
            sys.executable,
            "-m" "pabot.pabot",
            "{}/test.robot".format(self.tmpdir),
        ]
        stdout, stderr = self._run_command(command1)
        self.assertEqual(b"", stderr)
        self.assertIn(b"3 tests, 3 passed, 0 failed, 0 skipped.", stdout)

        command2 = [
            sys.executable,
            "-m" "pabot.pabot",
            "--runemptysuite",
            "--rerunfailed",
            "output.xml",
            "{}/test.robot".format(self.tmpdir),
        ]
        stdout, stderr = self._run_command(command2)
        self.assertEqual(b"", stderr)
        if ROBOT_VERSION >= "5.0.1":
            self.assertIn(b"0 tests, 0 passed, 0 failed, 0 skipped.", stdout)
            self.assertIn(b"Log: ", stdout)
            self.assertIn(b"Report: ", stdout)
            self.assertNotIn(b"[ ERROR ]", stdout)
        else:
            self.assertIn(b"Collecting failed tests from 'output.xml' failed: All tests passed.", stdout)
