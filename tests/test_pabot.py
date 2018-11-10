import unittest
import time
import os
from pabot import pabot


class PabotTests(unittest.TestCase):

    def setUp(self):
        self._options, self._datasources, self._pabot_args, _ = pabot._parse_args(['--pabotlib',
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
        options, datasources, pabot_args, options_for_subprocesses = pabot._parse_args(
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
             '-A', 'tests/arguments.arg',
             'suite'])
        self.assertEqual(pabot_args['command'], ['my_own_command.sh'])
        self.assertEqual(pabot_args['processes'], 12)
        self.assertEqual(pabot_args['resourcefile'], 'resourcefile.ini')
        self.assertEqual(pabot_args['pabotlib'], True)
        self.assertEqual(pabot_args['pabotlibhost'], '123.123.233.123')
        self.assertEqual(pabot_args['pabotlibport'], 4562)
        self.assertEqual(pabot_args['suitesfrom'], 'some.xml')
        self.assertEqual(pabot_args['argumentfiles'], [('1', 'argfile1.txt'), ('2', 'argfile2.txt')])
        self.assertEqual(options['outputdir'], 'myoutputdir')
        self.assertFalse('outputdir' in options_for_subprocesses)
        self.assertEqual(datasources, ['suite'])

    def test_start_and_stop_remote_library(self):
        lib_process = pabot._start_remote_library(self._pabot_args)
        self.assertTrue(lib_process.poll() is None)
        time.sleep(1)
        pabot._stop_remote_library(lib_process)
        self.assertTrue(lib_process.poll() == 0)

    #TODO: DO I have a test case for suite order not changing file hash?

    def test_solve_suite_names_works_without_pabotsuitenames_file(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=self._pabot_args)
        self.assertEqual(['Fixtures.Suite One', 
        'Fixtures.Suite Second', 
        'Fixtures.Suite&(Specia|)Chars'],
                         suite_names)
        self.assertTrue(os.path.isfile(".pabotsuitenames"))
        expected = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'e3975df839ba56a167cbd81b30d800abbbfa26d9',
            'Fixtures.Suite One',
            'Fixtures.Suite Second',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def _psuitenames(self, dhash, clihash, sfhash, fhash, *suites):
        return [
            'datasources:%s\n' % dhash,
            'commandlineoptions:%s\n' % clihash,
            'suitesfrom:%s\n' % sfhash,
            'file:%s\n' % fhash
        ] + [s+'\n' for s in suites]

    def test_solve_suite_names_works_with_suitesfrom_option(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=pabot_args)
        self.assertEqual(['Fixtures.Suite Second', 
                          'Fixtures.Suite One',
                          'Fixtures.Suite&(Specia|)Chars'],
                         suite_names)
        expected = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'b8368a7a5e1574965abcbb975b7b3521b2b4496b',
            'b105a1b80434e0443d50637224b9611f188b8c48',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_when_suitesfrom_file_added(self):
        pabotsuitenames = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'c06f2afdfa35791e82e71618bf60415e927c41ae',
            'Fixtures.Suite One',
            'Fixtures.Suite Second',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                                  datasources=self._datasources,
                                                  options=self._options,
                                                  pabot_args=pabot_args)
        self.assertEqual(['Fixtures.Suite Second', 
                          'Fixtures.Suite One',
                          'Fixtures.Suite&(Specia|)Chars'],
                         suite_names)
        expected = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'b8368a7a5e1574965abcbb975b7b3521b2b4496b',
            'b105a1b80434e0443d50637224b9611f188b8c48',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_when_suitesfrom_file_added_and_directory(self):
        pabotsuitenames = self._psuitenames(
            'oldhashcode',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'c06f2afdfa35791e82e71618bf60415e927c41ae',
            'Fixtures.Suite One',
            'Fixtures.Suite Second',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                                  datasources=self._datasources,
                                                  options=self._options,
                                                  pabot_args=pabot_args)
        self.assertEqual(['Fixtures.Suite Second', 
                          'Fixtures.Suite One',
                          'Fixtures.Suite&(Specia|)Chars'],
                         suite_names)
        expected = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'b8368a7a5e1574965abcbb975b7b3521b2b4496b',
            'b105a1b80434e0443d50637224b9611f188b8c48',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_after_suitesfrom_file_removed(self):
        pabotsuitenames = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'b8368a7a5e1574965abcbb975b7b3521b2b4496b',
            '50d0c83b3c6b35ddc81c3289f5591d6574412c17',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        os.rename("tests/output.xml", "tests/output.xml.tmp")
        try:
            suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                                  datasources=self._datasources,
                                                  options=self._options,
                                                  pabot_args=pabot_args)
        finally:
            os.rename("tests/output.xml.tmp", "tests/output.xml")
        self.assertEqual(['Fixtures.Suite Second', 
                          'Fixtures.Suite One',
                          'Fixtures.Suite&(Specia|)Chars'],
                         suite_names)
        expected = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'da39a3ee5e6b4b0d3255bfef95601890afd80709',
            '301506c4c01f4be31dfaf597364213d3983f368b',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite&(Specia|)Chars')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_pabotsuitenames_file(self):
        pabotsuitenames = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'e3975df839ba56a167cbd81b30d800abbbfa26d9',
            'Fixtures.Suite&(Specia|)Chars',
            'Fixtures.Suite Second',
            'Fixtures.Suite One')
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
        pabotsuitenames_corrupted = self._psuitenames(
            'd8ce00e244006f271e86b62cc14702b45caf6c8b',
            '98e9291c98411e6583248f87168b79afdf76d064',
            'no-suites-from-optiosn',
            '4f2fc7af25040e0f3b9e2681b84594ccb0cdf9e',
            'Fixtures.Suite&(Specia|)Chars',
            'NoneExisting',
            'Fixtures.Suite Second')
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
        expected = self._psuitenames(
            'd8ce00e644006f271e86b62cc14702b45caf6c8b',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'e3975df839ba56a167cbd81b30d800abbbfa26d9',
            'Fixtures.Suite&(Specia|)Chars',
            'Fixtures.Suite Second',
            'Fixtures.Suite One')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

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
