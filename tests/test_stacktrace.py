import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess


class PabotStacktraceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        robot_file = open("{}/test.robot".format(self.tmpdir), "w")
        robot_file.write(
            textwrap.dedent(
                """
        *** Test Cases ***
        Testing
            ${d}=  Create Dictionary  x=a  y=b
            ${res}=  Set Variable  ${d.pop('x')}
        """
            )
        )
        robot_file.close()

        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "{}/test.robot".format(self.tmpdir),
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.stdout, self.stderr = process.communicate()

    def test_stdout_should_display_passed_test_and_not_side_effect(self):
        if sys.version_info < (3, 0):
            self.assertIn("PASSED Test", self.stdout, self.stderr)
        else:
            self.assertIn(b"PASSED Test", self.stdout, self.stderr)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
