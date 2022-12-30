import subprocess
import sys
import textwrap
import shutil
import tempfile
import unittest


def _string_convert(byte_string):
    legacy_python = sys.version_info < (3, 0)
    return byte_string.decode() if legacy_python else byte_string


class DependsTest(unittest.TestCase):
    test_file = """
        *** Settings ***
        Test Template    Test1
        *** Test Cases ***
        The Test S1Test 01    1
        The Test S1Test 02    1
        The Test S1Test 03    1
        The Test S1Test 04    1
        The Test S1Test 05    1
        The Test S1Test 06    1
        The Test S1Test 07    1
        The Test S1Test 08    1
        The Test S1Test 09    1
        The Test S1Test 10    1
        The Test S1Test 11    1
        The Test S1Test 12    1
        *** Keywords ***
        Test1
            [Arguments]  ${arg}
            Log  Test
        """
    passed = _string_convert(b"PASSED")
    failed = _string_convert(b"FAILED")
    test_01 = _string_convert(b"S1Test 01")
    test_02 = _string_convert(b"S1Test 02")
    test_08 = _string_convert(b"S1Test 08")

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

    def test_dependency_ok(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01 #DEPENDS Test.The Test S1Test 02
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 08
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(self.passed, stdout, stderr)
        self.assertNotIn(self.failed, stdout, stderr)
        self.assertEqual(stdout.count(self.passed), 12)
        test_01_index = stdout.find(self.test_01)
        test_02_index = stdout.find(self.test_02)
        test_08_index = stdout.find(self.test_08)
        self.assertNotEqual(test_01_index, -1)
        self.assertNotEqual(test_02_index, -1)
        self.assertNotEqual(test_08_index, -1)
        self.assertTrue(test_08_index < test_02_index)
        self.assertTrue(test_02_index < test_01_index)

    def test_circular_dependency(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01 #DEPENDS Test.The Test S1Test 02
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 01
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies", stderr)

    def test_unmet_dependency(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 23
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies", stderr)

    def test_same_reference(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 02
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies", stderr)

    def test_wait(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 08
        #WAIT
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies", stderr)
