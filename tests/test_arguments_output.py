import os
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

    # copy all prepared files to temporary directory
    def _copy_files_to_tmp(self):
        for item in os.listdir("tests/argument_file"):
            src_item = os.path.join("tests/argument_file", item)
            dst_item = os.path.join(self.tmpdir, item)
            shutil.copy2(src_item, dst_item)

    # read file content
    def _read_output_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as output_file:
            content = output_file.read()
        return content.replace("=", "").encode("utf-8")

    def test_case_level_with_case_args_file(self):
        self._copy_files_to_tmp()

        process = subprocess.Popen(
          [
            sys.executable,
            "-m", "pabot.pabot",
            "--processes",
            "2",
            "--testlevelsplit",
            "--argumentfile",
            os.sep.join([self.tmpdir, "arg_case_options.txt"]),
            "--outputdir",
            self.tmpdir,
            self.tmpdir
          ],
          cwd=self.tmpdir,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        # validate the final output
        self.assertIn(b'2 tests, 2 passed, 0 failed, 0 skipped.', stdout)

        # validate the output for each process, there should be only one case for each process
        pabot_result_0 = "{}/pabot_results/0/robot_stdout.out".format(self.tmpdir)
        pabot_result_1 = "{}/pabot_results/1/robot_stdout.out".format(self.tmpdir)

        stdout_0 = self._read_output_file(pabot_result_0)
        stdout_1 = self._read_output_file(pabot_result_1)

        self.assertIn(b'1 test, 1 passed, 0 failed', stdout_0)
        self.assertIn(b'1 test, 1 passed, 0 failed', stdout_1)

    def test_suite_level_with_case_args_file(self):
        self._copy_files_to_tmp()

        process = subprocess.Popen(
          [
            sys.executable,
            "-m", "pabot.pabot",
            "--processes",
            "2",
            "--argumentfile",
            os.sep.join([self.tmpdir, "arg_case_options.txt"]),
            "--outputdir",
            self.tmpdir,
            self.tmpdir
          ],
          cwd=self.tmpdir,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        # validate the final output
        self.assertIn(b'2 tests, 2 passed, 0 failed, 0 skipped.', stdout)

        # validate the output for each process, there should be only one case for each process
        pabot_result_0 = "{}/pabot_results/0/robot_stdout.out".format(self.tmpdir)

        stdout_0 = self._read_output_file(pabot_result_0)

        self.assertIn(b'2 tests, 2 passed, 0 failed', stdout_0)

    def test_suite_level_with_suite_args_file(self):
        self._copy_files_to_tmp()

        process = subprocess.Popen(
          [
            sys.executable,
            "-m", "pabot.pabot",
            "--processes",
            "2",
            "-A",
            os.sep.join([self.tmpdir, "arg_suite_options.txt"]),
            "--outputdir",
            self.tmpdir,
            self.tmpdir
          ],
          cwd=self.tmpdir,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        # validate the final output
        self.assertIn(b'6 tests, 6 passed, 0 failed, 0 skipped.', stdout)

        # validate the output for each process, there should be only one case for each process
        pabot_result_0 = "{}/pabot_results/0/robot_stdout.out".format(self.tmpdir)
        pabot_result_1 = "{}/pabot_results/1/robot_stdout.out".format(self.tmpdir)

        stdout_0 = self._read_output_file(pabot_result_0)
        stdout_1 = self._read_output_file(pabot_result_1)

        self.assertIn(b'3 tests, 3 passed, 0 failed', stdout_0)
        self.assertIn(b'3 tests, 3 passed, 0 failed', stdout_1)

    def test_case_level_with_suite_args_file(self):
        self._copy_files_to_tmp()

        process = subprocess.Popen(
          [
            sys.executable,
            "-m", "pabot.pabot",
            "--processes",
            "2",
            "--testlevelsplit",
            "-A",
            os.sep.join([self.tmpdir, "arg_suite_options.txt"]),
            "--outputdir",
            self.tmpdir,
            self.tmpdir
          ],
          cwd=self.tmpdir,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        # validate the final output
        self.assertIn(b'6 tests, 6 passed, 0 failed, 0 skipped.', stdout)

        # validate the output for each process, there should be only one case for each process
        pabot_result_0 = "{}/pabot_results/0/robot_stdout.out".format(self.tmpdir)
        pabot_result_5 = "{}/pabot_results/5/robot_stdout.out".format(self.tmpdir)

        stdout_0 = self._read_output_file(pabot_result_0)
        stdout_5 = self._read_output_file(pabot_result_5)

        self.assertIn(b'1 test, 1 passed, 0 failed', stdout_0)
        self.assertIn(b'1 test, 1 passed, 0 failed', stdout_5)

    def test_suite_level_with_mixed_args_file(self):
        self._copy_files_to_tmp()

        process = subprocess.Popen(
          [
            sys.executable,
            "-m", "pabot.pabot",
            "--testlevelsplit",
            "--processes",
            "2",
            "--argumentfile",
            os.sep.join([self.tmpdir, "arg_mixed_options.txt"]),
            "--outputdir",
            self.tmpdir,
            self.tmpdir
          ],
          cwd=self.tmpdir,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        # validate the final output
        self.assertIn(b'2 tests, 2 passed, 0 failed, 0 skipped.', stdout)

        # validate the output for each process, there should be only one case for each process
        pabot_result_0 = "{}/pabot_results/0/robot_stdout.out".format(self.tmpdir)
        pabot_result_1 = "{}/pabot_results/1/robot_stdout.out".format(self.tmpdir)

        stdout_0 = self._read_output_file(pabot_result_0)
        stdout_1 = self._read_output_file(pabot_result_1)

        self.assertIn(b'1 test, 1 passed, 0 failed', stdout_0)
        self.assertIn(b'1 test, 1 passed, 0 failed', stdout_1)

        # validate if the --loglevel option works
        pabot_output_0 = "{}/pabot_results/0/output.xml".format(self.tmpdir)
        pabot_output_1 = "{}/pabot_results/1/output.xml".format(self.tmpdir)
        output_0 = self._read_output_file(pabot_output_0)
        output_1 = self._read_output_file(pabot_output_1)

        self.assertIn(b'debug message', output_0)
        self.assertIn(b'debug message', output_1)
