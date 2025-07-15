import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess
import os

from pabot import pabot


class PabotMissingSubProcessOutputTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run_tests_with(self, testfile):
        with open("{}/test.robot".format(self.tmpdir), "w") as robot_file:
            robot_file.write(textwrap.dedent(testfile))
        process = subprocess.Popen(
            [
                sys.executable,
                "-m" "pabot.pabot",
                "--testlevelsplit",
                "--no-rebot",
                "--output",
                "out.xml",
                "--outputdir",
                "results",
                "{}/test.robot".format(self.tmpdir),
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return process.communicate()
    
    def test_missing_subprocess_output_xml(self):
        """
        # Test for: https://github.com/mkorpela/pabot/issues/637

        Testing this is a bit tricky, as the creation of the XML in the subprocess is known to fail only on Windows (not posix system)
        — and only when CMD escaping doesn't work properly, for example when the test case name contains double quotes (").
        Runs tests with --no-rebot option first, changes one output xml file extension and then tries to report results.
        After that changes extension to orginal and tries again.
        """
        start_time = pabot._now()
        stdout, stderr = self._run_tests_with(
"""
*** Test Cases ***
Testing 1
   Log  1

Testing 2
   Log  2

Testing 3
   Log  3 
"""
        )
        self.assertIn((b"All tests were executed, but the --no-rebot argument was given, "
                       b"so the results were not compiled, and no summary was generated. "
                       b"All results have been saved in the"
                       ), stdout)
        self.assertEqual(b"", stderr)
        # Note: pabot._report_results() function does not need all of these pabot_args and options.
        pabot_args = {
            'command': ['robot'], 
            'verbose': False, 
            'help': False, 
            'version': False, 
            'testlevelsplit': True, 
            'pabotlib': True, 
            'pabotlibhost': '127.0.0.1', 
            'pabotlibport': 8270, 
            'processes': 3, 
            'processtimeout': None, 
            'artifacts': ['png'], 
            'artifactsinsubfolders': False, 
            'shardindex': 0, 
            'shardcount': 1, 
            'chunk': False, 
            'no-rebot': False, 
            'argumentfiles': []
        }
        options = {
            'metadata': [], 
            'settag': [], 
            'test': [], 
            'task': [], 
            'suite': [], 
            'include': [], 
            'exclude': [], 
            'skip': [], 
            'skiponfailure': [], 
            'variable': [], 
            'variablefile': [], 
            'outputdir': 'results', 
            'output': 'out.xml', 
            'tagstatinclude': [], 
            'tagstatexclude': [], 
            'tagstatcombine': [], 
            'tagdoc': [], 
            'tagstatlink': [], 
            'expandkeywords': [], 
            'removekeywords': [], 
            'flattenkeywords': [], 
            'listener': [], 
            'prerunmodifier': [], 
            'prerebotmodifier': [], 
            'pythonpath': [],
        }
        pabot_args2 = pabot_args.copy()  # Using copy, because pabot._report_results does minor modifications.
        options2 = options.copy()
        tests_root_name = "Test"  # This is from test.robot 

        # Change one subprocess output file extension from .xml to .not_xml
        file_path = "{}/results/pabot_results/0/out.xml".format(self.tmpdir)
        assert os.path.exists(file_path)
        os.rename(file_path, file_path.replace(".xml", ".not_xml"))
        
        prev_cmd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            # Checking that we see exit code 252 when some .xml is missing.
            self.assertIs(pabot._report_results("results/pabot_results", pabot_args, options, start_time, tests_root_name), 252)
            
            # Return .xml file extension and run same command again. Check exit code = 0
            os.rename(file_path.replace(".xml", ".not_xml"), file_path)
            self.assertIs(pabot._report_results("results/pabot_results", pabot_args2, options2, start_time, tests_root_name), 0)
        finally:
            os.chdir(prev_cmd)
