import unittest
import time
import os
import tempfile
import shutil
import random
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
        self._all_suites = [
        'Fixtures.Suite One', 
        'Fixtures.Suite Second',
        'Fixtures.Suite Special',
        'Fixtures.Suite With Valueset Tags',
        ]
        self._all_with_suites = ['--suite '+s for s in self._all_suites]

    def test_dryrun_optimisation_works(self):
        outs_dir = "."
        opts = pabot._options_for_dryrun({}, outs_dir)
        with pabot._with_modified_robot():
            pabot.run("tests/recursion.robot", **opts)
        output = os.path.join(outs_dir, opts['output'])
        data = ""
        with open(output, "r") as f:
            data = f.read()
        self.assertTrue("No Operation" in data, data)
        self.assertFalse("Recursive" in data, data)

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

    def test_start_and_stop_remote_library_without_resourcefile(self):
        pabot_args = dict(self._pabot_args)
        pabot_args['resourcefile'] = None
        lib_process = pabot._start_remote_library(pabot_args)
        self.assertTrue(lib_process.poll() is None)
        time.sleep(1)
        pabot._stop_remote_library(lib_process)
        self.assertTrue(lib_process.poll() == 0)

    def test_hash_of_command(self):
        h1 = pabot.get_hash_of_command({})
        h2 = pabot.get_hash_of_command({"key":"value"})
        h3 = pabot.get_hash_of_command({"key2": [], "key":"value"})
        h4 = pabot.get_hash_of_command({"pythonpath":"foobarzoo", "key":"value"})
        h5 = pabot.get_hash_of_command({"key":"value", "key2": "value2"})
        self.assertEqual("97d170e1550eee4afc0af065b78cda302a97674c", h1)
        self.assertNotEqual(h1, h2)
        self.assertEqual(h2, h3)
        self.assertEqual(h2, h4)
        self.assertNotEqual(h2, h5)

    def test_hash_of_dirs(self):
        test_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        h1 = pabot.get_hash_of_dirs([test_dir])
        h2 = pabot.get_hash_of_dirs([test_dir, test_dir])
        self.assertNotEqual(h1, h2)
        h3 = pabot.get_hash_of_dirs([os.path.join(test_dir,"suite_one.robot")])
        self.assertNotEqual(h1, h3)
        self.assertNotEqual(h2, h3)
        h4 = pabot.get_hash_of_dirs([os.path.join("suite_one.robot"), os.path.join("suite_second.robot")])
        self.assertNotEqual(h1, h4)
        self.assertNotEqual(h2, h4)
        self.assertNotEqual(h3, h4)


    def test_file_hash(self):
        expected_hash = "075734d97edbd5237f241dfd3f18177d2c80b3be"
        h1 = pabot._file_hash([
            "datasources:4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6",
            "commandlineoptions:97d170e1550eee4afc0af065b78cda302a97674c",
            "suitesfrom:no-suites-from-option",
            "file:"+expected_hash] + self._all_with_suites)
        self.assertEqual(h1, expected_hash)
        h2 = pabot._file_hash([
            "datasources:4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6",
            "commandlineoptions:97d170e1550eee4afc0af065b78cda302a97674c",
            "suitesfrom:no-suites-from-option",
            "file:"+expected_hash] + list(reversed(self._all_with_suites)))
        self.assertEqual(h1, h2)
        h3 = pabot._file_hash([
            "datasources:4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6",
            "commandlineoptions:97d170e1550eee4afc0af065b78cda302a97674c",
            "suitesfrom:no-suites-from-option",
            "file:whatever"] + self._all_with_suites + ["--suite Fixtures.New Suite"])
        self.assertNotEqual(h1, h3)

    def test_solve_suite_names_works_without_pabotsuitenames_file(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=self._pabot_args)
        self._assert_equal_names([self._all_suites], suite_names)
        self.assertTrue(os.path.isfile(".pabotsuitenames"))
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            *self._all_with_suites)
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

    def test_solve_suite_names_works_with_directory_suite(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            'some-wrong-stuff',
            'no-suites-from-option',
            'this-is-wrong',
            '--suite Fixtures')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=self._pabot_args)
        self.assertEqual([['Fixtures']],
                         suite_names)
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '842b411d6e8a04bdd497c97b92a6c577dca7879a',
            '--suite Fixtures')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_suite_ordering_adds_new_suite(self):
        self.assertEqual(['newSuite'], pabot._preserve_order(['newSuite'], []))
    
    def test_suite_ordering_removes_old_suite(self):
        self.assertEqual(['newSuite'], pabot._preserve_order(['newSuite'], ['oldSuite']))

    def test_suite_ordering_uses_old_order(self):
        self.assertEqual(['suite2', 'suite1'], pabot._preserve_order(['suite1', 'suite2'], ['suite2', 'suite1']))

    def test_suite_ordering_adds_new_suites_to_end(self):
        self.assertEqual(['s3', 's2', 's1'], pabot._preserve_order(['s1', 's2', 's3'], ['s3', 's2']))

    def test_suite_ordering_preserves_directory_suites(self):
        self.assertEqual(['s.sub', 's3'], pabot._preserve_order(['s.sub.s1', 's.sub.s2', 's3'], ['s.sub']))

    def test_suite_ordering_preserves_wait_command(self):
        self.assertEqual(['s2', '#WAIT', 's1', 's3'], pabot._preserve_order(['s1', 's2', 's3'], ['s2', '#WAIT', 's1']))
        self.assertEqual(['s2', '#WAIT', 's3'], pabot._preserve_order(['s2', 's3'], ['s2', '#WAIT', 's1']))
    
    def test_suite_ordering_removes_wait_command_if_it_would_be_first_element(self):
        self.assertEqual(['s1', 's3'], pabot._preserve_order(['s1', 's3'], ['s2', '#WAIT', 's1']))

    def test_suite_ordering_removes_wait_command_if_it_would_be_last_element(self):
        self.assertEqual(['s2'], pabot._preserve_order(['s2'], ['s2', '#WAIT', 's1']))

    def test_suite_ordering_removes_double_wait_command(self):
        self.assertEqual(['s2', '#WAIT', 's3'], pabot._preserve_order(['s3','s2'], ['s2', '#WAIT', 's1', '#WAIT', 's3']))

    def test_suite_ordering_stores_two_wait_commands(self):
        self.assertEqual(['s2', '#WAIT', 's1', '#WAIT', 's3'], pabot._preserve_order(['s3','s2','s1'], ['s2', '#WAIT', 's1', '#WAIT', 's3']))

    def test_suite_ordering_removes_directory_suite_subsuites_also_from_old_list(self):
        self.assertEqual(['s1', 'sub', 's4', 'subi'],
            pabot._preserve_order(
                ['s1', 'sub.s2', 'sub.s3', 's4', 'subi'],
                ['s1', 'sub', 'sub.s3', 's4']))

    def test_suite_ordering_removes_directory_suite_subsuites_also_from_old_list(self):
        self.assertEqual(['s'],
            pabot._preserve_order(
                ['s.s1', 's.sub.s2', 's.s3'],
                ['s.sub', 's']))

    def test_suite_ordering_removes_old_duplicate(self):
        self.assertEqual(['s'],
            pabot._preserve_order(
                ['s'],
                ['s', 's']))

    def test_solve_suite_names_works_with_suitesfrom_option(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                              datasources=self._datasources,
                                              options=self._options,
                                              pabot_args=pabot_args)
        self._assert_equal_names([['Fixtures.Suite Second', 
                          'Fixtures.Suite One',
                          'Fixtures.Suite Special']],
                         suite_names)
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'f57c1949d5137773e0b9f6ca34c439a27a22bcb0',
            'd100d667803ab7e9a3ce39aade2a9a2179bbab5d',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite Special')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_when_suitesfrom_file_added(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'c06f2afdfa35791e82e71618bf60415e927c41ae',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite Special')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                                  datasources=self._datasources,
                                                  options=self._options,
                                                  pabot_args=pabot_args)
        self.assertEqual([['Fixtures.Suite Second', 
                          'Fixtures.Suite One',
                          'Fixtures.Suite Special']],
                         suite_names)
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'f57c1949d5137773e0b9f6ca34c439a27a22bcb0',
            'd100d667803ab7e9a3ce39aade2a9a2179bbab5d',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite Special')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_when_suitesfrom_file_added_and_directory(self):
        pabotsuitenames = self._psuitenames(
            'oldhashcode',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'c06f2afdfa35791e82e71618bf60415e927c41ae',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                                  datasources=self._datasources,
                                                  options=self._options,
                                                  pabot_args=pabot_args)
        self._assert_equal_names([['Fixtures.Suite Second', 
                          'Fixtures.Suite One',
                          'Fixtures.Suite Special',
                          'Fixtures.Suite With Valueset Tags']],
                         suite_names)
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'f57c1949d5137773e0b9f6ca34c439a27a22bcb0',
            '58a5f2a70e045d5a31ed0cc8515feeb6a3128a7f',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_after_suitesfrom_file_removed(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'f57c1949d5137773e0b9f6ca34c439a27a22bcb0',
            '50d0c83b3c6b35ddc81c3289f5591d6574412c17',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite With Valueset Tags')
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
        self.assertEqual([['Fixtures.Suite Second', 
                            'Fixtures.Suite One',
                            'Fixtures.Suite Special',
                            'Fixtures.Suite With Valueset Tags']],
                         [s.name for s in suite_names])
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'da39a3ee5e6b4b0d3255bfef95601890afd80709',
            '92c46b3609886b9fa7df57b3f903aa6664d549f1',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_pabotsuitenames_file(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite With Valueset Tags')
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
        self._assert_equal_names([[
            'Fixtures.Suite Special',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite With Valueset Tags'
        ]], suite_names)

    def test_solve_suite_names_file_is_not_changed_when_invalid_cli_opts(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        self._options["loglevel"] = "INVALID123"
        original = pabot._regenerate
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                            datasources=self._datasources,
                                            options=self._options,
                                            pabot_args=self._pabot_args)
        self.assertEqual([[]], suite_names)
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(pabotsuitenames, actual)

    def test_solve_suite_names_transforms_old_suite_names_to_new_format(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            'c65865c6eac504bddb6bd3f8ddeb18bd49b53c37',
            'Fixtures.Suite Special',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                            datasources=self._datasources,
                                            options=self._options,
                                            pabot_args=self._pabot_args)
        self._assert_equal_names([[
            'Fixtures.Suite Special',
            'Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite With Valueset Tags'
        ]], suite_names)
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_pabotsuitenames_file_with_wait_command(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            '--suite Fixtures.Suite Special',
            '#WAIT',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite With Valueset Tags')
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
        self._assert_equal_names([
            ['Fixtures.Suite Special'],
            ['Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite With Valueset Tags']], suite_names)

    def _assert_equal_names(self, names, output):
        output_names = [[s.name for s in suites] for suites in output]
        self.assertEqual(names, output_names)

    def test_solve_suite_names_works_with_pabotsuitenames_file_with_wait_command_when_cli_change(self):
        pabotsuitenames = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            'old-command-line-options',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            '--suite Fixtures.Suite Special',
            '#WAIT',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        original = pabot._regenerate
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                            datasources=self._datasources,
                                            options=self._options,
                                            pabot_args=self._pabot_args)
        self.assertEqual([
            ['Fixtures.Suite Special'],
            ['Fixtures.Suite Second',
            'Fixtures.Suite One',
            'Fixtures.Suite With Valueset Tags']], suite_names)
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            '--suite Fixtures.Suite Special',
            '#WAIT',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite One',
            '--suite Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_with_corrupted_pabotsuitenames_file(self):
        pabotsuitenames_corrupted = self._psuitenames(
            'd8ce00e244006f271e86b62cc14702b45caf6c8b',
            '98e9291c98411e6583248f87168b79afdf76d064',
            'no-suites-from-optiosn',
            '4f2fc7af25040e0f3b9e2681b84594ccb0cdf9e',
            '--suite Fixtures.Suite Special',
            '--suite NoneExisting',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite With Valueset Tags')
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames_corrupted)
        suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                            datasources=self._datasources,
                                            options=self._options,
                                            pabot_args=self._pabot_args)
        self.assertEqual([[
            'Fixtures.Suite Special',
            'Fixtures.Suite Second',
            'Fixtures.Suite With Valueset Tags',
            'Fixtures.Suite One', 
        ]], suite_names)
        expected = self._psuitenames(
            '4a1e9103a8b3239b18b63ebb8775b1ab2225f4b6',
            '97d170e1550eee4afc0af065b78cda302a97674c',
            'no-suites-from-option',
            '075734d97edbd5237f241dfd3f18177d2c80b3be',
            '--suite Fixtures.Suite Special',
            '--suite Fixtures.Suite Second',
            '--suite Fixtures.Suite With Valueset Tags',
            '--suite Fixtures.Suite One')
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_with_ioerror_pabotsuitenames(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        os.mkdir(".pabotsuitenames")
        try:
            suite_names = pabot.solve_suite_names(outs_dir=self._outs_dir,
                                                datasources=self._datasources,
                                                options=self._options,
                                                pabot_args=self._pabot_args)
            self.assertEqual([self._all_suites], suite_names)
        finally:
            os.rmdir(".pabotsuitenames")

    def test_parallel_execution(self):
        dtemp = tempfile.mkdtemp()
        outs_dir = os.path.join(dtemp, 'pabot_results')
        self._options['outputdir'] = dtemp
        self._pabot_args['pabotlibport'] = 4000+random.randint(0, 1000)
        lib_process = pabot._start_remote_library(self._pabot_args)
        try:
            suite_names = self._all_suites[:]
            pabot._parallel_execute(datasources=self._datasources,
                                    options=self._options,
                                    outs_dir=outs_dir,
                                    pabot_args=self._pabot_args,
                                    suite_names=suite_names)
            result_code = pabot._report_results(outs_dir,
                                                self._pabot_args,
                                                self._options,
                                                pabot._now(),
                                                pabot._get_suite_root_name(
                                                    [suite_names]))
            self.assertEqual(8, result_code)
        finally:
            pabot._stop_remote_library(lib_process)
            shutil.rmtree(dtemp)

    def test_suite_root_name(self):
        self.assertEqual(pabot._get_suite_root_name([["Foo.Bar", "Foo.Zoo"], ["Foo.Boo"]]), "Foo")
        self.assertEqual(pabot._get_suite_root_name([["Foo.Bar", "Foo.Zoo"], ["Boo"]]), "")
        self.assertEqual(pabot._get_suite_root_name([["Bar", "Foo.Zoo"], ["Foo.Boo"]]), "")
        self.assertEqual(pabot._get_suite_root_name([[]]), "")

if __name__ == '__main__':
    unittest.main()
