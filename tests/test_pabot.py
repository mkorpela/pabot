import unittest
import time
from pabot import pabot


class PabotTests(unittest.TestCase):

    def test_parse_args(self):
        options, datasources, pabot_args = pabot._parse_args(
            ['--command', 'my_own_command.sh', '--end-command',
             '--processes', '12',
             '--verbose',
             '--resourcefile', 'resourcefile.ini',
             '--pabotlib',
             '--pabotlibhost', '123.123.233.123',
             '--pabotlibport', '4562',
             '--suitesfrom', 'some.xml',
             'suite'])
        self.assertEqual(pabot_args['command'], ['my_own_command.sh'])
        self.assertEqual(pabot_args['processes'], 12)
        self.assertEqual(pabot_args['resourcefile'], 'resourcefile.ini')
        self.assertEqual(pabot_args['pabotlib'], True)
        self.assertEqual(pabot_args['pabotlibhost'], '123.123.233.123')
        self.assertEqual(pabot_args['pabotlibport'], 4562)
        self.assertEqual(pabot_args['suitesfrom'], 'some.xml')
        self.assertEqual(datasources, ['suite'])


    def test_start_and_stop_remote_library(self):
        lib_process = pabot._start_remote_library(
            {'pabotlib': True,
             'pabotlibhost': '127.0.0.1',
             'pabotlibport': 8270})
        self.assertTrue(lib_process.poll() is None)
        time.sleep(0.3)
        pabot._stop_remote_library(lib_process)
        self.assertTrue(lib_process.poll() == 0)


if __name__ == '__main__':
    unittest.main()
