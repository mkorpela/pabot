import unittest
import tempfile
import textwrap
import shutil
import subprocess
import sys
import os
from test_pabotprerunmodifier import get_tmpdir_name


class SuiteStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.tmpdir_name = get_tmpdir_name(os.path.basename(cls.tmpdir))

        # robot case files
        cls.robot_file_path_1 = f'{cls.tmpdir}/dir_1/suite_1.robot'
        cls.robot_file_path_2 = f'{cls.tmpdir}/dir_1/dir_2/suite_2.robot'
        cls.robot_file_path_3 = f'{cls.tmpdir}/dir_1/dir_2/dir_3/suite_3.robot'
        cls.robot_file_path_4 = f'{cls.tmpdir}/dir_1/dir_2/dir_3/dir_4/suite_4.robot'

        cls.robot_dir_1 = os.path.dirname(cls.robot_file_path_1)
        cls.robot_dir_2 = os.path.dirname(cls.robot_file_path_2)
        cls.robot_dir_3 = os.path.dirname(cls.robot_file_path_3)
        cls.robot_dir_4 = os.path.dirname(cls.robot_file_path_4)


        os.makedirs(os.path.dirname(cls.robot_file_path_4), exist_ok=True)
        with open(cls.robot_file_path_1, 'w') as robot_file:
            robot_file.write(
                textwrap.dedent("""
*** Test Cases ***
Testing 1 1
   Log  hello
"""))
            
        with open(cls.robot_file_path_2, 'w') as robot_file:
            robot_file.write(
                textwrap.dedent("""
*** Test Cases ***
Testing 2 1
   Log  hello
"""))
            
        with open(cls.robot_file_path_3, 'w') as robot_file:
            robot_file.write(
                textwrap.dedent("""
*** Test Cases ***
Testing 3 1
   Log  hello
"""))
            
        with open(cls.robot_file_path_4, 'w') as robot_file:
            robot_file.write(
                textwrap.dedent("""
*** Test Cases ***
Testing 4 1
   [Tags]  tag
   Log  hello
"""))
            
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir)


    def tearDown(self):
        """ Deletes .pabotsuitenames ja output.xml files between tests. """
        for filename in [".pabotsuitenames", "output.xml"]:
            file_path = os.path.join(self.tmpdir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)


    def test_run_root_then_suite_4_then_dir_1_then_dir_4(self):
        process_root_1 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.tmpdir
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_root_1.communicate()
        self.assertIn(b'4 tests, 4 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertIn(f'PASSED {self.tmpdir_name}.Dir 1.Suite 1'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED {self.tmpdir_name}.Dir 1.Dir 2.Suite 2'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED {self.tmpdir_name}.Dir 1.Dir 2.Dir 3.Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED {self.tmpdir_name}.Dir 1.Dir 2.Dir 3.Dir 4.Suite 4'.encode('utf-8'), stdout)

        process_suite_4 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.robot_file_path_4
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_suite_4.communicate()
        self.assertIn(b'1 tests, 1 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertNotIn(f'Suite 1'.encode('utf-8'), stdout)
        self.assertNotIn(f'Suite 2'.encode('utf-8'), stdout)
        self.assertNotIn(f'Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Suite 4'.encode('utf-8'), stdout)

        process_dir_1 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.robot_dir_1
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_dir_1.communicate()
        self.assertIn(b'4 tests, 4 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertIn(f'PASSED Dir 1.Suite 1'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 1.Dir 2.Suite 2'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 1.Dir 2.Dir 3.Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 1.Dir 2.Dir 3.Dir 4.Suite 4'.encode('utf-8'), stdout)

        process_dir_4 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.robot_dir_4
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_dir_4.communicate()
        self.assertIn(b'1 tests, 1 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertNotIn(f'Suite 1'.encode('utf-8'), stdout)
        self.assertNotIn(f'Suite 2'.encode('utf-8'), stdout)
        self.assertNotIn(f'Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 4.Suite 4'.encode('utf-8'), stdout)


    
    def test_run_dir_2_then_dir_3(self):
        process_dir_2 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.robot_dir_2
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_dir_2.communicate()
        self.assertIn(b'3 tests, 3 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertNotIn(f'Suite 1'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 2.Suite 2'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 2.Dir 3.Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 2.Dir 3.Dir 4.Suite 4'.encode('utf-8'), stdout)

        process_dir_3 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.robot_dir_3
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_dir_3.communicate()
        self.assertIn(b'2 tests, 2 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertNotIn(f'Suite 1'.encode('utf-8'), stdout)
        self.assertNotIn(f'Suite 2'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 3.Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 3.Dir 4.Suite 4'.encode('utf-8'), stdout)

    
    def test_run_dir_3_then_dir_2(self):
        process_dir_3 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.robot_dir_3
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_dir_3.communicate()
        self.assertIn(b'2 tests, 2 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertNotIn(f'Suite 1'.encode('utf-8'), stdout)
        self.assertNotIn(f'Suite 2'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 3.Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 3.Dir 4.Suite 4'.encode('utf-8'), stdout)

        process_dir_2 = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                self.robot_dir_2
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process_dir_2.communicate()
        self.assertIn(b'3 tests, 3 passed, 0 failed, 0 skipped.', stdout)
        self.assertEqual(b"", stderr)
        self.assertNotIn(f'Suite 1'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 2.Suite 2'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 2.Dir 3.Suite 3'.encode('utf-8'), stdout)
        self.assertIn(f'PASSED Dir 2.Dir 3.Dir 4.Suite 4'.encode('utf-8'), stdout)
