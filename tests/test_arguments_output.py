import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess


class PabotArgumentsOutputsTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run_tests_with(self, testfile, arg1file, arg2file):
        robot_file = open("{}/test.robot".format(self.tmpdir), "w")
        robot_file.write(textwrap.dedent(testfile))
        robot_file.close()
        with open("{}/arg1.txt".format(self.tmpdir), "w") as f:
            f.write(textwrap.dedent(arg1file))
        with open("{}/arg2.txt".format(self.tmpdir), "w") as f:
            f.write(textwrap.dedent(arg2file))
        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "--processes",
                "2",
                "--argumentfile1",
                "{}/arg1.txt".format(self.tmpdir),
                "--argumentfile2",
                "{}/arg2.txt".format(self.tmpdir),
                "--outputdir",
                self.tmpdir,
                "--output",
                "test.xml",
                "{}/test.robot".format(self.tmpdir),
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return process.communicate(), process.returncode

    def test_argumentfile_outputs(self):
        (stdout, stderr), rc = self._run_tests_with(
            """
        *** Test Cases ***
        Test 1
            Log     ${VALUE}
            Should Be True  ${VALUE} == 2
        """,
            """
        --variable VALUE:1
        """,
            """
        --variable VALUE:2
        """,
        )
        self.assertEqual(rc, 1)
        if sys.version_info < (3, 0):
            self.assertIn("PASSED", stdout, stderr)
            self.assertIn("failed", stdout, stderr)
        else:
            self.assertIn(b"PASSED", stdout, stderr)
            self.assertIn(b"failed", stdout, stderr)
