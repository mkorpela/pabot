import os
import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess


class PabotPassJsonUsingVariableOptionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        file_path = f"{self.tmpdir}/test.robot"
        with open(file_path, "w") as robot_file:
            robot_file.write(
                textwrap.dedent(
                    """
*** Test Cases ***
Testing 1
   [Tags]  tag
   Log  hello

Testing 2
   [Tags]  tag
   Log  world
"""
                )
            )

        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "--testlevelsplit",
                "--verbose",
                "--include",
                "tag",
                f"{self.tmpdir}/test.robot",
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.stdout, self.stderr = process.communicate()

    def test_stdout_should_display_passed_test(self):
        first = b"Testing 1                                                             | PASS |"
        second = b"Testing 2                                                             | PASS |"
        self.assertEqual(self.stdout.count(first), 1, self.stdout)
        self.assertEqual(self.stdout.count(second), 1, self.stdout)
        self.assertIn(b"PASSED Test", self.stdout, self.stderr)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
