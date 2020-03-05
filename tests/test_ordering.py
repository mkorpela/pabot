import os
import sys
import tempfile
import textwrap
import unittest
import shutil
import subprocess


class PabotOrderingGroupTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        robot_file = open('{}/test.robot'.format(self.tmpdir), 'w')
        robot_file.write(textwrap.dedent(
        '''
        *** Variables ***
        ${SCALAR}  Hello, globe!

        *** Test Cases ***
        First Test
            Set Suite Variable	${SCALAR}	Hello, world!

        Second Test
            Should Be Equal  ${SCALAR}	Hello, world!

        Third Test
            Should Be Equal  ${SCALAR}	Hello, globe!
        '''))
        robot_file.close()

        with open('{}/order.dat'.format(self.tmpdir), 'w') as f:
            f.write(textwrap.dedent(
            '''
            {
            --test Test.First Test
            --test Test.Second Test
            }
            --test Test.Third Test
            '''))

        process = subprocess.Popen(
            [sys.executable, '-m' 'pabot.pabot', '--testlevelsplit','--ordering', '{}/order.dat'.format(self.tmpdir),
             '{}/test.robot'.format(self.tmpdir)],
            cwd=self.tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        self.stdout, self.stderr = process.communicate()

    def test_stdout_should_display_passed_test(self):
        if sys.version_info < (3, 0):
            self.assertIn('PASSED', self.stdout, self.stderr)
            self.assertNotIn('FAILED', self.stdout, self.stderr)
            self.assertEqual(self.stdout.count('PASSED'), 2)
        else:
            self.assertIn(b'PASSED', self.stdout, self.stderr)
            self.assertNotIn(b'FAILED', self.stdout, self.stderr)
            self.assertEqual(self.stdout.count(b'PASSED'), 2)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
