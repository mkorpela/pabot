import unittest
import tempfile
import shutil
import subprocess
import sys
from pabot import __version__ as PABOT_VERSION

class PrerunModifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_pabot_version(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--version"
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        self.assertIn(f'Version {PABOT_VERSION}'.encode('utf-8'), stdout)
        self.assertEqual(b"", stderr)

    def test_pabot_help(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "pabot.pabot",
                "--help"
            ],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()
        self.assertIn(b'Reading information from:', stdout)
        self.assertEqual(b"", stderr)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmpdir)
        