import unittest
import time
from pabot import pabot


class PabotTests(unittest.TestCase):

    def setUp(self):
        self._options, self._datasources, self._pabot_args = pabot._parse_args(['--pabotlib', 'tests/fixtures'])
        self._outs_dir = pabot._output_dir(self._options)

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
        lib_process = pabot._start_remote_library(self._pabot_args)
        self.assertTrue(lib_process.poll() is None)
        time.sleep(1)
        pabot._stop_remote_library(lib_process)
        self.assertTrue(lib_process.poll() == 0)

    def test_solve_suite_names(self):
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=self._pabot_args)
        self.assertEqual(['Fixtures.Suite One', 'Fixtures.Suite Second'],
                         suite_names)

    def test_parallel_execution(self):
        # datasources, options, outs_dir, pabot_args, suite_names
        suite_names = ['Fixtures.Suite One',
                       'Fixtures.Suite Second']
        pabot._parallel_execute(datasources=self._datasources,
                                options=self._options,
                                outs_dir=self._outs_dir,
                                pabot_args=self._pabot_args,
                                suite_names=suite_names)
        result_code = pabot._report_results(self._outs_dir,
                                            self._options,
                                            pabot._now(),
                                            pabot._get_suite_root_name(
                                                suite_names))
        self.assertEqual(2, result_code)


if __name__ == '__main__':
    unittest.main()
