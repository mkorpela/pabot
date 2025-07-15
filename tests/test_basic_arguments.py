import unittest
import tempfile
import shutil
import subprocess
import sys
import re

EXPECTED_VERSION_PATTERN = (
    rb"A parallel executor for Robot Framework test cases\.\r?\n"
    rb"Version \d+\.\d+\.\d+\r?\n\r?\n"
    rb"Copyright 20\d{2} Mikko Korpela - Apache 2 License"
)

EXPECTED_HELP_PATTERN = (
    rb"A parallel executor for Robot Framework test cases\.\r?\n"
    rb"Version \d+\.\d+\.\d+\r?\n\r?\n"
    rb"Extracted from "
)


class BasicArgumentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_pabot_version(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--version"
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        match = re.match(EXPECTED_VERSION_PATTERN, stdout)
        assert match, f"Version output does not match expected format, output: {repr(stdout)}"
        self.assertEqual(b"", stderr)

    def test_pabot_help(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--help"
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        match = re.match(EXPECTED_HELP_PATTERN, stdout)
        assert match, f"Help output does not match expected format, output: {repr(stdout)}"
        self.assertEqual(b"", stderr)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmpdir)
