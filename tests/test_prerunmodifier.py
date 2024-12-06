import unittest
import tempfile
import textwrap
import shutil
import subprocess
import sys


class PrerunModifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp()

        # robot case file
        self.robot_file_path = f'{self.tmpdir}/test.robot'
        with open(self.robot_file_path, 'w') as robot_file:
            robot_file.write(
                textwrap.dedent("""
*** Test Cases ***
Testing 1
   [Tags]  tag
   Log  hello

Testing 2
   [Tags]  tag
   Log  world
"""))

        # prerunmodifier script
        self.modifier_file_path = f'{self.tmpdir}/Modifier.py'
        with open(self.modifier_file_path, 'w') as modifier_file:
            modifier_file.write(
                textwrap.dedent("""
from robot.api import SuiteVisitor


class Modifier(SuiteVisitor):
    def start_suite(self, suite):
        if suite.tests:
            for test in suite.tests:
                if '1' in test.name:
                    name = 'new-name-1'
                    tag = 'tag1'
                else:
                    name = 'new-name-2'
                    tag = 'tag2'
                test.name = name
                test.tags.add([tag])
"""))

    def test_pre_run_with_new_tag(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--prerunmodifier",
                self.modifier_file_path,
                "--include",
                "tag2",
                self.robot_file_path
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        self.assertIn(b'1 tests, 1 passed, 0 failed, 0 skipped.', stdout)

    def test_pre_run_with_new_name(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--prerunmodifier",
                self.modifier_file_path,
                "--test",
                "new-name-1",
                self.robot_file_path
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        self.assertIn(b'1 tests, 1 passed, 0 failed, 0 skipped.', stdout)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmpdir)
        