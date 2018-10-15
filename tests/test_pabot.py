import unittest
import time
import os
from pabot import pabot


class PabotTests(unittest.TestCase):

    def setUp(self):
        self._options, self._datasources, self._pabot_args = pabot._parse_args(['--pabotlib',
                                                                                '--verbose',
                                                                                '--argumentfile1',
                                                                                'tests/passingarg.txt',
                                                                                '--argumentfile2',
                                                                                'tests/failingarg.txt',
                                                                                '--resourcefile',
                                                                                'tests/valueset.dat',
                                                                                'tests/fixtures'])
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
             '--argumentfile1', 'argfile1.txt',
             '--argumentfile2', 'argfile2.txt',
             'suite'])
        self.assertEqual(pabot_args['command'], ['my_own_command.sh'])
        self.assertEqual(pabot_args['processes'], 12)
        self.assertEqual(pabot_args['resourcefile'], 'resourcefile.ini')
        self.assertEqual(pabot_args['pabotlib'], True)
        self.assertEqual(pabot_args['pabotlibhost'], '123.123.233.123')
        self.assertEqual(pabot_args['pabotlibport'], 4562)
        self.assertEqual(pabot_args['suitesfrom'], 'some.xml')
        self.assertEqual(pabot_args['argumentfiles'], [('1', 'argfile1.txt'), ('2', 'argfile2.txt')])
        self.assertEqual(datasources, ['suite'])

    def test_start_and_stop_remote_library(self):
        lib_process = pabot._start_remote_library(self._pabot_args)
        self.assertTrue(lib_process.poll() is None)
        time.sleep(1)
        pabot._stop_remote_library(lib_process)
        self.assertTrue(lib_process.poll() == 0)

    def test_solve_suite_names_works_without_pabotsuitenames_file(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=self._pabot_args)
        self.assertEqual(['Fixtures.Suite One', 'Fixtures.Suite Second', 'Fixtures.Suite&(Specia|)Chars'],
                         suite_names)
        self.assertTrue(os.path.isfile(".pabotsuitenames"))
        expected = [self._d('d8ce00e644006f271e86b62cc14702b45caf6c8b'),
        'commandlineoptions:e8a497f81418cc647bbdd88c2b999d6971aa6116\n',
        'suitesfrom:no-suites-from-option\n',
        'file:cb7b13c2fcfa5284c74c15cf42e37f62b0b7a7b8\n',
        'Fixtures.Suite One\n',
        'Fixtures.Suite Second\n',
        'Fixtures.Suite&(Specia|)Chars\n']
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_suitesfrom_option(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=pabot_args)
        expected = [self._d('d8ce00e644006f271e86b62cc14702b45caf6c8b'),
        'commandlineoptions:e8a497f81418cc647bbdd88c2b999d6971aa6116\n',
        'suitesfrom:b8368a7a5e1574965abcbb975b7b3521b2b4496b\n',
        'file:10b6a5e90bde819d56bc881a8311e748244cb25e\n',
        'Fixtures.Suite Second\n',
        'Fixtures.Suite One\n',
        'Fixtures.Suite&(Specia|)Chars\n']
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_pabotsuitenames_file(self):
        pabotsuitenames = [self._d('d8ce00e644006f271e86b62cc14702b45caf6c8b'),
        self._c('e8a497f81418cc647bbdd88c2b999d6971aa6116'),
        'suitesfrom:no-suites-from-option\n',
        'file:c06f2afdfa35791e82e71618bf60415e927c41ae\n',
        'Fixtures.Suite&(Specia|)Chars\n',
        'Fixtures.Suite Second\n',
        'Fixtures.Suite One\n'
        ]
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        original = pabot._regenerate
        pabot._regenerate = lambda *args: 1/0
        try:
            suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                                datasources=self._datasources,
                                                options=self._options,
                                                pabot_args=self._pabot_args)
        finally:
            pabot._regenerate = original
        self.assertEqual([
            'Fixtures.Suite&(Specia|)Chars',
            'Fixtures.Suite Second',
            'Fixtures.Suite One', 
        ], suite_names)

    def test_solve_suite_names_with_corrupted_pabotsuitenames_file(self):
        pabotsuitenames_corrupted = [self._d('d8ce00e244006f271e86b62cc14702b45caf6c8b'),
        self._c('98e9291c98411e6583248f87168b79afdf76d064'),
        'no-suites-from-optiosn\n',
        '4f2fc7af25040e0f3b9e2681b84594ccb0cdf9e\n',
        'Fixtures.Suite&(Specia|)Chars\n',
        'NoneExisting\n',
        'Fixtures.Suite Second\n']
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames_corrupted)
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                            datasources=self._datasources,
                                            options=self._options,
                                            pabot_args=self._pabot_args)
        self.assertEqual([
            'Fixtures.Suite&(Specia|)Chars',
            'Fixtures.Suite Second',
            'Fixtures.Suite One', 
        ], suite_names)
        expected = [self._d('d8ce00e644006f271e86b62cc14702b45caf6c8b'),
        self._c('e8a497f81418cc647bbdd88c2b999d6971aa6116'),
        'suitesfrom:no-suites-from-option\n',
        'file:cb7b13c2fcfa5284c74c15cf42e37f62b0b7a7b8\n',
        'Fixtures.Suite&(Specia|)Chars\n',
        'Fixtures.Suite Second\n',
        'Fixtures.Suite One\n'
        ]
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    #FIXME: Some way of knowing if we regenerated!!

    def _d(self, h):
        return 'datasources:%s\n' % h

    def _c(self, h):
        return 'commandlineoptions:%s\n' % h

    def test_parallel_execution(self):
        suite_names = ['Fixtures.Suite One',
                       'Fixtures.Suite Second',
                       'Fixtures.Suite&(Specia|)Chars']
        lib_process = pabot._start_remote_library(self._pabot_args)
        pabot._parallel_execute(datasources=self._datasources,
                                options=self._options,
                                outs_dir=self._outs_dir,
                                pabot_args=self._pabot_args,
                                suite_names=suite_names)
        result_code = pabot._report_results(self._outs_dir,
                                            self._pabot_args,
                                            self._options,
                                            pabot._now(),
                                            pabot._get_suite_root_name(
                                                suite_names))
        pabot._stop_remote_library(lib_process)
        self.assertEqual(5, result_code)


if __name__ == '__main__':
    unittest.main()
