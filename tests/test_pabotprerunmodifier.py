import unittest
import tempfile
import textwrap
import shutil
import subprocess
import sys
import os
import re


class PabotPrerunModifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmpdir_name = (re.sub(r'(\d)([a-z])', lambda m: m.group(1) + m.group(2).upper(),
                                   " ".join(word.capitalize().strip() for word in os.path.basename(self.tmpdir).split("_")))).strip()

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
        with open(self.modifier_file_path, 'w') as modifier_file:
            modifier_file.write(
                textwrap.dedent("""
from robot.api import SuiteVisitor

class Modifier(SuiteVisitor):
    def __init__(self, tag):
        self.list_of_test_names = []
        self.tag = tag
 
    def start_suite(self, suite):
        if suite.tests:
            for test in suite.tests:
                if self.tag in test.tags:
                   self.list_of_test_names.append(test.full_name)
    
    def end_suite(self, suite):
        suite.tests = [t for t in suite.tests if t.full_name in self.list_of_test_names]
        suite.suites = [s for s in suite.suites if s.test_count > 0]              
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


    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmpdir)
