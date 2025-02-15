from robot import __version__ as ROBOT_VERSION
import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess


class PabotOrderingGroupTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run_tests_with(self, testfile, orderfile):
        robot_file = open("{}/test.robot".format(self.tmpdir), "w")
        robot_file.write(textwrap.dedent(testfile))
        robot_file.close()
        with open("{}/order.dat".format(self.tmpdir), "w") as f:
            f.write(textwrap.dedent(orderfile))
        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "--testlevelsplit",
                "--ordering",
                "{}/order.dat".format(self.tmpdir),
                "{}/test.robot".format(self.tmpdir),
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return process.communicate()

    def test_orders(self):
        stdout, stderr = self._run_tests_with(
            """
        *** Variables ***
        ${SCALAR}  Hello, globe!

        *** Test Cases ***
        First Test
            Set Suite Variable	${SCALAR}	Hello, world!

        Second Test
            Should Be Equal  ${SCALAR}	Hello, world!

        Third Test
            Should Be Equal  ${SCALAR}	Hello, globe!
        """,
            """
        {
        --test Test.First Test
        --test Test.Second Test
        }
        --test Test.Third Test
        """,
        )
        if sys.version_info < (3, 0):
            self.assertIn("PASSED", stdout, stderr)
            self.assertNotIn("FAILED", stdout, stderr)
            self.assertEqual(stdout.count("PASSED"), 2)
        else:
            self.assertIn(b"PASSED", stdout, stderr)
            self.assertNotIn(b"FAILED", stdout, stderr)
            self.assertEqual(stdout.count(b"PASSED"), 2)

    def test_two_orders(self):
        stdout, stderr = self._run_tests_with(
            """
        *** Variables ***
        ${SCALAR}  Hello, globe!

        *** Test Cases ***
        First Test
            Set Suite Variable	${SCALAR}	Hello, world!

        Second Test
            Should Be Equal  ${SCALAR}	Hello, world!

        Second And Quarter
            Should Be Equal  ${SCALAR}	Hello, globe!

        Second And Half
            Should Be Equal  ${SCALAR}	Hello, globe!

        Third Test
            Should Be Equal  ${SCALAR}	Hello, globe!
        """,
            """
        {
        --test Test.First Test
        --test Test.Second Test
        }
        {
        --test Test.Second And Quarter
        --test Test.Second And Half
        }
        --test Test.Third Test
        """,
        )
        if sys.version_info < (3, 0):
            self.assertIn("PASSED", stdout, stderr)
            self.assertNotIn("FAILED", stdout, stderr)
            if ROBOT_VERSION < "4.0":
                expected_write = "5 critical tests, 5 passed, 0 failed"
            else:
                expected_write = "5 tests, 5 passed, 0 failed, 0 skipped."
            self.assertIn(expected_write, stdout, stderr)
            self.assertEqual(stdout.count("PASSED"), 3)
        else:
            self.assertIn(b"PASSED", stdout, stderr)
            self.assertNotIn(b"FAILED", stdout, stderr)
            if ROBOT_VERSION < "4.0":
                expected_write = b"5 critical tests, 5 passed, 0 failed"
            else:
                expected_write = b"5 tests, 5 passed, 0 failed, 0 skipped."
            self.assertIn(expected_write, stdout, stderr)
            self.assertEqual(stdout.count(b"PASSED"), 3)

    def test_too_big_testname(self):
        stdout, stderr = self._run_tests_with(
            """
        *** Test Cases ***
        Test Lorem ipsum dolor sit amet, consectetur adipiscing elit. Mauris eu velit nunc. Duis eget purus eget orci porta blandit sed ut tortor. Nunc vel nulla bibendum, auctor sem ac, molestie risus. Sed eu metus volutpat, hendrerit nibh in, auctor urna. Nunc a sodales.
            Log    Test

        """,
            """
        --test  Invalid
        """,
        )
        if sys.version_info < (3, 0):
            self.assertIn("PASSED", stdout, stderr)
            self.assertNotIn("FAILED", stdout, stderr)
            self.assertEqual(stdout.count("PASSED"), 1)
        else:
            self.assertIn(b"PASSED", stdout, stderr)
            self.assertNotIn(b"FAILED", stdout, stderr)
            self.assertEqual(stdout.count(b"PASSED"), 1)

    def test_longnames_in_tests(self):
        stdout, stderr = self._run_tests_with(
            """
        *** Settings ***
        Test Template    Test1
        *** Test Cases ***
        The Somewhat Long Name Of The Test S1Test 01    1
        The Somewhat Long Name Of The Test S1Test 02    1
        The Somewhat Long Name Of The Test S1Test 03    1
        The Somewhat Long Name Of The Test S1Test 04    1
        The Somewhat Long Name Of The Test S1Test 05    1
        The Somewhat Long Name Of The Test S1Test 06    1
        The Somewhat Long Name Of The Test S1Test 07    1
        The Somewhat Long Name Of The Test S1Test 08    1
        The Somewhat Long Name Of The Test S1Test 09    1
        The Somewhat Long Name Of The Test S1Test 10    1
        The Somewhat Long Name Of The Test S1Test 11    1
        The Somewhat Long Name Of The Test S1Test 12    1
        *** Keywords ***
        Test1
            [Arguments]  ${arg}
            Log  Test
        """,
            """
        {
        --test Test.The Somewhat Long Name Of The Test S1Test 01
        --test Test.The Somewhat Long Name Of The Test S1Test 02
        --test Test.The Somewhat Long Name Of The Test S1Test 03
        --test Test.The Somewhat Long Name Of The Test S1Test 04
        --test Test.The Somewhat Long Name Of The Test S1Test 05
        --test Test.The Somewhat Long Name Of The Test S1Test 06
        }
        {
        --test Test.The Somewhat Long Name Of The Test S1Test 07
        --test Test.The Somewhat Long Name Of The Test S1Test 08
        --test Test.The Somewhat Long Name Of The Test S1Test 09
        --test Test.The Somewhat Long Name Of The Test S1Test 10
        --test Test.The Somewhat Long Name Of The Test S1Test 11
        --test Test.The Somewhat Long Name Of The Test S1Test 12
        }
        """,
        )
        if sys.version_info < (3, 0):
            self.assertIn("PASSED", stdout, stderr)
            self.assertNotIn("FAILED", stdout, stderr)
            self.assertEqual(stdout.count("PASSED"), 2)
        else:
            self.assertIn(b"PASSED", stdout, stderr)
            self.assertNotIn(b"FAILED", stdout, stderr)
            self.assertEqual(stdout.count(b"PASSED"), 2)


class PabotOrderingSleepTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run_tests_with(self, testfile, orderfile):
        robot_file = open("{}/test.robot".format(self.tmpdir), "w")
        robot_file.write(textwrap.dedent(testfile))
        robot_file.close()
        with open("{}/order.dat".format(self.tmpdir), "w") as f:
            f.write(textwrap.dedent(orderfile))
        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "--testlevelsplit",
                "--ordering",
                "{}/order.dat".format(self.tmpdir),
                "{}/test.robot".format(self.tmpdir),
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return process.communicate()

    def test_sleep_test_cases_and_group(self):
        stdout, stderr = self._run_tests_with(
            """
        *** Test Cases ***
        Test Case A
           Log  Hello!

        Test Case B
           Log  Hello!

        Test Case C
           Log  Hello!

        Test Case D
            Log  Hello!
        """,
            """
        #SLEEP 1
        {
        #SLEEP 4
        --test Test.Test Case A
        #SLEEP 4
        --test Test.Test Case B
        #SLEEP 4
        }
        #SLEEP 4
        #SLEEP 3
        --test Test.Test Case C
        #SLEEP 2
        --test Test.Test Case D
        #SLEEP 4
        """,
        )
        self.assertIn(b"PASSED", stdout, stderr)
        self.assertNotIn(b"FAILED", stdout, stderr)
        self.assertEqual(stdout.count(b"PASSED"), 3)
        self.assertIn(b"SLEEPING 1 SECONDS BEFORE STARTING Group_Test.Test Case A_Test.Test Case B", stdout, stderr)
        self.assertIn(b"SLEEPING 3 SECONDS BEFORE STARTING Test.Test Case C", stdout, stderr)
        self.assertIn(b"SLEEPING 2 SECONDS BEFORE STARTING Test.Test Case D", stdout, stderr)
        self.assertNotIn(b"SLEEPING 4", stdout, stderr)
