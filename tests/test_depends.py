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
    test_03 = _string_convert(b"S1Test 03")
    test_04 = _string_convert(b"S1Test 04")
    test_05 = _string_convert(b"S1Test 05")
    test_06 = _string_convert(b"S1Test 06")
    test_07 = _string_convert(b"S1Test 07")
    test_08 = _string_convert(b"S1Test 08")
    test_09 = _string_convert(b"S1Test 09")
    test_10 = _string_convert(b"S1Test 10")
    test_11 = _string_convert(b"S1Test 11")
    test_12 = _string_convert(b"S1Test 12")

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

    def test_multiple_dependencies_ok(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 01
        --test Test.The Test S1Test 03 #DEPENDS Test.The Test S1Test 02
        --test Test.The Test S1Test 04
        --test Test.The Test S1Test 05 #DEPENDS Test.The Test S1Test 01 #DEPENDS Test.The Test S1Test 04
        --test Test.The Test S1Test 06 #DEPENDS Test.The Test S1Test 05
        --test Test.The Test S1Test 07
        --test Test.The Test S1Test 08
        --test Test.The Test S1Test 09 #DEPENDS Test.The Test S1Test 07 #DEPENDS Test.The Test S1Test 08 #DEPENDS Test.The Test S1Test 06
        --test Test.The Test S1Test 10 #DEPENDS Test.The Test S1Test 12
        --test Test.The Test S1Test 11 #DEPENDS Test.The Test S1Test 03 #DEPENDS Test.The Test S1Test 06 #DEPENDS Test.The Test S1Test 10 #DEPENDS Test.The Test S1Test 09
        --test Test.The Test S1Test 12
        """,
        )
        self.assertIn(self.passed, stdout, stderr)
        self.assertNotIn(self.failed, stdout, stderr)
        self.assertEqual(stdout.count(self.passed), 12)
        test_01_index = stdout.find(self.test_01)
        test_02_index = stdout.find(self.test_02)
        test_03_index = stdout.find(self.test_03)
        test_04_index = stdout.find(self.test_04)
        test_05_index = stdout.find(self.test_05)
        test_06_index = stdout.find(self.test_06)
        test_07_index = stdout.find(self.test_07)
        test_08_index = stdout.find(self.test_08)
        test_09_index = stdout.find(self.test_09)
        test_10_index = stdout.find(self.test_10)
        test_11_index = stdout.find(self.test_11)
        test_12_index = stdout.find(self.test_12)
        self.assertNotEqual(test_01_index, -1)
        self.assertNotEqual(test_02_index, -1)
        self.assertNotEqual(test_03_index, -1)
        self.assertNotEqual(test_04_index, -1)
        self.assertNotEqual(test_05_index, -1)
        self.assertNotEqual(test_06_index, -1)
        self.assertNotEqual(test_07_index, -1)
        self.assertNotEqual(test_08_index, -1)
        self.assertNotEqual(test_09_index, -1)
        self.assertNotEqual(test_10_index, -1)
        self.assertNotEqual(test_11_index, -1)
        self.assertNotEqual(test_12_index, -1)
        self.assertTrue(test_02_index > test_01_index)
        self.assertTrue(test_03_index > test_02_index)
        self.assertTrue(test_05_index > test_01_index)
        self.assertTrue(test_05_index > test_04_index)
        self.assertTrue(test_06_index > test_05_index)
        self.assertTrue(test_09_index > test_07_index)
        self.assertTrue(test_09_index > test_08_index)
        self.assertTrue(test_09_index > test_06_index)
        self.assertTrue(test_10_index > test_12_index)
        self.assertTrue(test_11_index > test_03_index)
        self.assertTrue(test_11_index > test_06_index)
        self.assertTrue(test_11_index > test_10_index)
        self.assertTrue(test_11_index > test_09_index)

    def test_circular_dependency(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01 #DEPENDS Test.The Test S1Test 02
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 01
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies using #DEPENDS. Check this/these test(s): [<test:Test.The Test S1Test 01>, <test:Test.The Test S1Test 02>]", stdout)
        self.assertEqual(b"", stderr)

    def test_circular_dependency_with_multiple_depends(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 01
        --test Test.The Test S1Test 03 #DEPENDS Test.The Test S1Test 01
        --test Test.The Test S1Test 08 #DEPENDS Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 03 #DEPENDS Test.The Test S1Test 09
        --test Test.The Test S1Test 09 #DEPENDS Test.The Test S1Test 01 #DEPENDS Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies using #DEPENDS. Check this/these test(s): [<test:Test.The Test S1Test 08>, <test:Test.The Test S1Test 09>]", stdout)
        self.assertEqual(b"", stderr)

    def test_unmet_dependency(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 23
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies using #DEPENDS. Check this/these test(s): [<test:Test.The Test S1Test 02>]", stdout)
        self.assertEqual(b"", stderr)

    def test_same_reference(self):
        stdout, stderr = self._run_tests_with(
            self.test_file,
            """
        --test Test.The Test S1Test 01
        --test Test.The Test S1Test 02 #DEPENDS Test.The Test S1Test 02
        --test Test.The Test S1Test 08
        """,
        )
        self.assertIn(b"circular or unmet dependencies using #DEPENDS. Check this/these test(s): [<test:Test.The Test S1Test 02>]", stdout)
        self.assertEqual(b"", stderr)

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
        self.assertIn(b"circular or unmet dependencies using #DEPENDS. Check this/these test(s): [<test:Test.The Test S1Test 02>]", stdout)
        self.assertEqual(b"", stderr)
