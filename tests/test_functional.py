import os
import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess


if os.name != "posix":
    raise unittest.SkipTest("Only posix test")


class PabotPassJsonUsingVariableOptionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        robot_file = open("{}/test.robot".format(self.tmpdir), "w")
        robot_file.write(
            textwrap.dedent(
                """
        *** Test Cases ***
        Test Passing Json With -v option
            Should Be Equal    ${custom_var}    {"key": "value"}
        """
            )
        )
        robot_file.close()

        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "-v",
                'custom_var:{"key": "value"}',
                "{}/test.robot".format(self.tmpdir),
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.stdout, self.stderr = process.communicate()

    def test_stdout_should_display_passed_test(self):
        if sys.version_info < (3, 0):
            self.assertIn("PASSED Test", self.stdout, self.stderr)
        else:
            self.assertIn(b"PASSED Test", self.stdout, self.stderr)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
