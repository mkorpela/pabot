import unittest
import tempfile
import textwrap
import shutil
import subprocess
import sys
import os
import re
import robot


def check_robot_version_and_return_name():
    version = robot.__version__
    major_version = int(version.split('.')[0])

    if major_version >= 7:
        return "full_name"
    else:
        return "longname"


def get_tmpdir_name(input: str) -> str:
    # Remove everything before the first occurrence of two or more consecutive underscores,
    # while preserving underscores as spaces with the same count
    result = re.sub(r'^.*?(__+)', lambda m: ' ' * len(m.group(1)), input).strip()

    # Capitalize letters following space, underscores or digits (e.g. after ' ', '_', '1')
    result = re.sub(r'([ _\d])([a-z])', lambda m: m.group(1) + m.group(2).upper(), result)

    result = result.replace("_", " ").strip()
    # Capitalize the first letter of the result
    result = result[0].upper() + result[1:] if result else result

    return result.strip()


class PabotPrerunModifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmpdir_name = get_tmpdir_name(os.path.basename(self.tmpdir))

        # robot case file 1
        self.robot_file_path_1 = f'{self.tmpdir}/test_1.robot'
        with open(self.robot_file_path_1, 'w') as robot_file:
            robot_file.write(
                textwrap.dedent("""
*** Test Cases ***
Testing 1
   [Tags]  tag  test3
   Log  hello

Testing 2
   [Tags]  tag  test  test2  test3
   Log  world

Testing 3
   [Tags]  tag
   Log  world
"""))
            
        # robot case file 2
        self.robot_file_path_2 = f'{self.tmpdir}/test_2.robot'
        with open(self.robot_file_path_2, 'w') as robot_file:
            robot_file.write(
                textwrap.dedent("""
*** Test Cases ***
Testing 4
   [Tags]  tag
   Log  hello

Testing 5
   [Tags]  tag  test2  test3
   Log  world

Testing 6
   [Tags]  tag
   Log  world
"""))

        # pabotprerunmodifier script. Works like Robot Framework --include command
        self.modifier_file_path = f'{self.tmpdir}/Modifier.py'
        correct_full_name_call = check_robot_version_and_return_name()
        with open(self.modifier_file_path, 'w') as modifier_file:
            modifier_file.write(
                textwrap.dedent(f"""
from robot.api import SuiteVisitor

class Modifier(SuiteVisitor):
    def __init__(self, tag):
        self.list_of_test_names = []
        self.tag = tag
 
    def start_suite(self, suite):
        if suite.tests:
            for test in suite.tests:
                if self.tag in test.tags:
                   self.list_of_test_names.append(test.{correct_full_name_call})
    
    def end_suite(self, suite):
        suite.tests = [t for t in suite.tests if t.{correct_full_name_call} in self.list_of_test_names]
        suite.suites = [s for s in suite.suites if s.test_count > 0]              
"""))

        # prerunmodifier script
        self.modifier2_file_path = f'{self.tmpdir}/Modifier2.py'
        with open(self.modifier2_file_path, 'w') as modifier_file:
            modifier_file.write(
                textwrap.dedent("""
from robot.api import SuiteVisitor

class Modifier2(SuiteVisitor):
    def start_suite(self, suite):
        if suite.tests:
            for test in suite.tests:
                if '2' in test.name:
                    test.name = 'new-name-2'
                    test.tags.add(['tag2'])
"""))

        # ordering file
        self.ordering_file_path = f'{self.tmpdir}/ordering.txt'
        with open(self.ordering_file_path, 'w') as ordering_file:
            ordering_file.write(
                textwrap.dedent(f"""
{{
--test {self.tmpdir_name}.Test 1.Testing 2
--test {self.tmpdir_name}.Test 2.Testing 5
}}
--test {self.tmpdir_name}.Test 1.Testing 1
"""))


    # This is only for testing test tool
    """
    def test_get_tmpdir_name(self):
        # This is what get_tmpdir_name will return
        self.assertEqual(get_tmpdir_name("tmp3v__d5jk"), "D5Jk")
        self.assertEqual(get_tmpdir_name("abc__xyz__test123"), "Xyz  Test123")
        self.assertEqual(get_tmpdir_name("hello_world__test"), "Test")
        self.assertEqual(get_tmpdir_name("tmp__data__42a"), "Data  42A")
        self.assertEqual(get_tmpdir_name("2__1__g"), "1  G")
        self.assertEqual(get_tmpdir_name("abc___xyz__123"), "Xyz  123") #(three and two spaces)
        self.assertEqual(get_tmpdir_name("test__data__42a"), "Data  42A")
        self.assertEqual(get_tmpdir_name("__1___2__3__4"), "1   2  3  4")
        self.assertEqual(get_tmpdir_name("1___2__3__4"), "2  3  4")
        self.assertEqual(get_tmpdir_name("tmp_ddl9fmr"), "Tmp Ddl9Fmr")
        self.assertEqual(get_tmpdir_name("tmp1ddl9fmr"), "Tmp1Ddl9Fmr")
        self.assertEqual(get_tmpdir_name(" mpe 74cy0ty"), "Mpe 74Cy0Ty")
    """

    def test_pabotprerunmodifier(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--pabotprerunmodifier",
                self.modifier_file_path + ":test",
                self.tmpdir
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        # without testlevelsplit argument whole test suite 1 will be executed.
        self.assertIn(f'PASSED {self.tmpdir_name}.Test 1'.encode('utf-8'), stdout)
        self.assertIn(b'3 tests, 3 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)


    def test_pabotprerunmodifier_with_testlevelsplit(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--testlevelsplit",
                "--pabotprerunmodifier",
                self.modifier_file_path + ":test2",
                self.tmpdir
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        self.assertIn(f'PASSED {self.tmpdir_name}.Test 1.Testing 2'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED {self.tmpdir_name}.Test 2.Testing 5'.encode('utf-8'), stdout)
        self.assertIn(b'2 tests, 2 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)


    def test_pabotprerunmodifier_with_testlevelsplit_and_ordering(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--testlevelsplit",
                "--pabotprerunmodifier",
                self.modifier_file_path + ":test3",
                "--ordering",
                self.ordering_file_path,
                self.tmpdir
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        self.assertIn(f'PASSED Group_{self.tmpdir_name}.Test 1.Testing 2_{self.tmpdir_name}.Test 2.Testing 5'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED {self.tmpdir_name}.Test 1.Testing 1'.encode('utf-8'), stdout)
        self.assertIn(b'3 tests, 3 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)


    def test_pabotprerunmodifier_with_prerunmodifier(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--testlevelsplit",
                "--pabotprerunmodifier",
                self.modifier_file_path + ":tag2",
                "--prerunmodifier",
                self.modifier2_file_path,
                self.tmpdir
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        self.assertIn(f'PASSED {self.tmpdir_name}.Test 1.new-name-2'.encode('utf-8'), stdout)
        self.assertIn(b'1 tests, 1 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)


    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmpdir)
