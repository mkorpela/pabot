import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from robot.api import ExecutionResult


class PabotTestlevelsplitOutputTaskOrderTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run_tests_with(self, testfile):
        robot_file = open("{}/test.robot".format(self.tmpdir), "w")
        robot_file.write(textwrap.dedent(testfile))
        robot_file.close()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "--testlevelsplit",
                "{}/test.robot".format(self.tmpdir),
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.wait()

    def test_testlevelsplit_output_task_order(self):
        self._run_tests_with(
            """
                *** Test Cases ***
                Test 1
                    Log    Executing test

                Test 2
                    Log    Executing test

                Test 3
                    Log    Executing test

                Test 4
                    Log    Executing test

                Test 5
                    Log    Executing test

                Test 6
                    Log    Executing test

                Test 7
                    Log    Executing test

                Test 8
                    Log    Executing test

                Test 9
                    Log    Executing test

                Test 10
                    Log    Executing test

                Test 11
                    Log    Executing test
            """
        )
        result = ExecutionResult("{}/output.xml".format(self.tmpdir))
        test_names = [test.name for test in result.suite.tests]
        self.assertEqual(
            [
                "Test 1",
                "Test 2",
                "Test 3",
                "Test 4",
                "Test 5",
                "Test 6",
                "Test 7",
                "Test 8",
                "Test 9",
                "Test 10",
                "Test 11",
            ],
            test_names,
        )
