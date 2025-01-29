#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest
import time
import os
import tempfile
import shutil
import random

import pabot.execution_items as execution_items
from pabot import pabot, arguments
from robot.utils import PY2
from robot.errors import DataError
from robot import __version__ as ROBOT_VERSION

s = execution_items.SuiteItem
t = execution_items.TestItem
datasource_hash = "8bd7e5d3de0bf878df17c338ce72a5ab27575050"
file_hash = "19488a6a4a95f5ecb935ef87e07df9d10d81e3c0"


class PabotTests(unittest.TestCase):
    def setUp(self):
        self._options, self._datasources, self._pabot_args, _ = arguments.parse_args(
            [
                "--pabotlib",
                "--verbose",
                "--argumentfile1",
                "tests/passingarg.txt",
                "--argumentfile2",
                "tests/failingarg.txt",
                "--resourcefile",
                "tests/valueset.dat",
                "tests/fixtures",
            ]
        )
        self._outs_dir = pabot._output_dir(self._options)
        self._all_suites = [
            "Fixtures.Suite One",
            "Fixtures.Suite Second",
            "Fixtures.Suite Special",
            "Fixtures.Suite With Valueset Tags",
            "Fixtures.Test Copy Artifacts.Suite 1",
            "Fixtures.Test Copy Artifacts.Suite 2",
        ]
        self._all_with_suites = ["--suite " + s for s in self._all_suites]
        self._all_tests = [
            "Fixtures.Suite One.1.1 Test Case One",
            "Fixtures.Suite One.1.2 Test Case Two",
            "Fixtures.Suite One.1.3 Test Value Set",
            "Fixtures.Suite One.1.4 Testing arg file",
            "Fixtures.Suite Second.Testing Case One of Second with Scändic Chör",
            "Fixtures.Suite Second.Testing Case One and a half Of Second",
            "Fixtures.Suite Second.Testing Case Two of Second",
            "Fixtures.Suite Second.Testing 1",
            "Fixtures.Suite Second.Testing 2",
            "Fixtures.Suite Special.Passing test Case",
            "Fixtures.Suite With Valueset Tags.Laser value set",
            "Fixtures.Suite With Valueset Tags.Tachyon value set",
            "Fixtures.Suite With Valueset Tags.Common value set",
            "Fixtures.Suite With Valueset Tags.None existing",
            "Fixtures.Suite With Valueset Tags.Add value to set",
            "Fixtures.Test Copy Artifacts.Suite 1.Links to screenshot directly in output_dir",
            "Fixtures.Test Copy Artifacts.Suite 1.Links to screenshots in subfolder",
            "Fixtures.Test Copy Artifacts.Suite 1.Links to other file in subfolder",
            "Fixtures.Test Copy Artifacts.Suite 2.Links to screenshot directly in output_dir",
            "Fixtures.Test Copy Artifacts.Suite 2.Links to screenshots in subfolder",
            "Fixtures.Test Copy Artifacts.Suite 2.Links to other file in subfolder",
        ]
        self._all_with_tests = ["--test " + _t for _t in self._all_tests]

    def test_parse_args(self):
        (
            options,
            datasources,
            pabot_args,
            options_for_subprocesses,
        ) = arguments.parse_args(
            [
                "--command",
                "my_own_command.sh",
                "--end-command",
                "--processes",
                "12",
                "--verbose",
                "--resourcefile",
                "resourcefile.ini",
                "--testlevelsplit",
                "--pabotlibhost",
                "123.123.233.123",
                "--pabotlibport",
                "4562",
                "--suitesfrom",
                "some.xml",
                "--argumentfile1",
                "argfile1.txt",
                "--argumentfile2",
                "argfile2.txt",
                "-A",
                "tests/arguments.arg",
                "suite",
            ]
        )
        self.assertEqual(pabot_args["command"], ["my_own_command.sh"])
        self.assertEqual(pabot_args["processes"], 12)
        self.assertEqual(pabot_args["resourcefile"], "resourcefile.ini")
        self.assertEqual(pabot_args["pabotlib"], False)
        self.assertEqual(pabot_args["pabotlibhost"], "123.123.233.123")
        self.assertEqual(pabot_args["pabotlibport"], 4562)
        self.assertEqual(pabot_args["suitesfrom"], "some.xml")
        self.assertEqual(
            pabot_args["argumentfiles"], [("1", "argfile1.txt"), ("2", "argfile2.txt")]
        )
        self.assertEqual(options["outputdir"], "myoutputdir")
        self.assertFalse("outputdir" in options_for_subprocesses)
        self.assertTrue(pabot_args["testlevelsplit"])
        self.assertEqual(datasources, ["suite"])

    def test_start_and_stop_remote_library(self):
        lib_process = pabot._start_remote_library(self._pabot_args)
        self.assertTrue(lib_process.poll() is None)
        time.sleep(1)
        pabot._stop_remote_library(lib_process)
        self.assertTrue(lib_process.poll() == 0)

    def test_start_and_stop_remote_library_without_resourcefile(self):
        pabot_args = dict(self._pabot_args)
        pabot_args["resourcefile"] = None
        lib_process = pabot._start_remote_library(pabot_args)
        self.assertTrue(lib_process.poll() is None)
        time.sleep(1)
        pabot._stop_remote_library(lib_process)
        self.assertTrue(lib_process.poll() == 0)

    def test_hash_of_command(self):
        h1 = pabot.get_hash_of_command({}, {})
        h2 = pabot.get_hash_of_command({"key": "value"}, {})
        h3 = pabot.get_hash_of_command({"key2": [], "key": "value"}, {})
        h4 = pabot.get_hash_of_command({"pythonpath": "foobarzoo", "key": "value"}, {})
        h5 = pabot.get_hash_of_command({"key": "value", "key2": "value2"}, {})
        h6 = pabot.get_hash_of_command(
            {"key": "value", "key2": "value2"}, {"foo": "bar"}
        )
        h7 = pabot.get_hash_of_command(
            {"key": "value", "key2": "value2"}, {"testlevelsplit": True}
        )
        self.assertEqual("97d170e1550eee4afc0af065b78cda302a97674c", h1)
        self.assertNotEqual(h1, h2)
        self.assertEqual(h2, h3)
        self.assertEqual(h2, h4)
        self.assertNotEqual(h2, h5)
        self.assertEqual(h5, h6)
        self.assertNotEqual(h6, h7)

    def test_hash_of_dirs(self):
        test_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        h1 = pabot.get_hash_of_dirs([test_dir])
        h2 = pabot.get_hash_of_dirs([test_dir, test_dir])
        self.assertNotEqual(h1, h2)
        h3 = pabot.get_hash_of_dirs([os.path.join(test_dir, "suite_one.robot")])
        self.assertNotEqual(h1, h3)
        self.assertNotEqual(h2, h3)
        h4 = pabot.get_hash_of_dirs(
            [os.path.join("suite_one.robot"), os.path.join("suite_second.robot")]
        )
        self.assertNotEqual(h1, h4)
        self.assertNotEqual(h2, h4)
        self.assertNotEqual(h3, h4)

    def test_file_hash(self):
        h1 = pabot._file_hash(
            [
                "datasources:" + datasource_hash,
                "commandlineoptions:97d170e1550eee4afc0af065b78cda302a97674c",
                "suitesfrom:no-suites-from-option",
                "file:" + file_hash,
            ]
            + self._all_with_suites
        )
        self.assertEqual(h1, file_hash)
        h2 = pabot._file_hash(
            [
                "datasources:" + datasource_hash,
                "commandlineoptions:97d170e1550eee4afc0af065b78cda302a97674c",
                "suitesfrom:no-suites-from-option",
                "file:" + file_hash,
            ]
            + list(reversed(self._all_with_suites))
        )
        self.assertEqual(h1, h2)
        h3 = pabot._file_hash(
            [
                "datasources:" + datasource_hash,
                "commandlineoptions:97d170e1550eee4afc0af065b78cda302a97674c",
                "suitesfrom:no-suites-from-option",
                "file:whatever",
            ]
            + self._all_with_suites
            + ["--suite Fixtures.New Suite"]
        )
        self.assertNotEqual(h1, h3)

    def test_replace_base_name(self):
        opts = {
            "simplestring": "old.simple",
            "listofstrings": ["old.first", "old.second"],
        }
        pabot._replace_base_name("new", "old", opts, "simplestring")
        self.assertEqual(opts["simplestring"], "new.simple")
        pabot._replace_base_name("new", "old", opts, "listofstrings")
        self.assertEqual(opts["listofstrings"], ["new.first", "new.second"])
        pabot._replace_base_name("new", "old", opts, "nonexisting")
        self.assertTrue("nonexisting" not in opts)

    def test_solve_suite_names_works_without_pabotsuitenames_file(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=self._pabot_args,
        )
        self._assert_equal_names([self._all_suites], suite_names)
        self.assertTrue(os.path.isfile(".pabotsuitenames"))
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            *self._all_with_suites
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def _psuitenames(self, dhash, clihash, sfhash, fhash, *suites):
        return [
            "datasources:%s\n" % dhash,
            "commandlineoptions:%s\n" % clihash,
            "suitesfrom:%s\n" % sfhash,
            "file:%s\n" % fhash,
        ] + [_s + "\n" for _s in suites]

    def test_solve_suite_names_works_with_directory_suite(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "some-wrong-stuff",
            "no-suites-from-option",
            "this-is-wrong",
            "--suite Fixtures",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=self._pabot_args,
        )
        self._assert_equal_names([["Fixtures"]], suite_names)
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            "2543f14f62afd037bd3958bb719656fc315cbc9d",
            "--suite Fixtures",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def _suites(self, list_of_names):
        return [self._suites_element(name) for name in list_of_names]

    def _suites_element(self, name):
        if name == "#WAIT":
            return execution_items.WaitItem()
        if name == "{":
            return execution_items.GroupStartItem()
        if name == "}":
            return execution_items.GroupEndItem()
        return s(name)

    def _test_preserve_order(self, expected, new_suites, old_suites):
        self.assertEqual(
            self._suites(expected),
            pabot._preserve_order(self._suites(new_suites), self._suites(old_suites)),
        )

    def test_suite_ordering_with_group(self):
        self._test_preserve_order(
            ["s1", "{", "s2", "s3", "}", "s4"],
            ["s1", "s2", "s3", "s4"],
            ["s1", "{", "s2", "s3", "}"],
        )

    def test_suite_ordering_with_group_ignores_new_and_preserves_old_grouping(self):
        self._test_preserve_order(
            ["s1", "{", "s2", "s3", "s4", "}"],
            ["{", "s1", "s2", "}", "s3", "s4"],
            ["s1", "{", "s2", "s3", "s4", "}"],
        )

    def test_suite_ordering_group_is_removed_if_no_items(self):
        self._test_preserve_order(
            ["s1", "s4"], ["s1", "s4"], ["s1", "{", "s2", "s3", "}", "s4"]
        )

    def test_suite_ordering_adds_new_suite(self):
        self._test_preserve_order(["newSuite"], ["newSuite"], [])

    def test_suite_ordering_removes_old_suite(self):
        self._test_preserve_order(["newSuite"], ["newSuite"], ["oldSuite"])

    def test_suite_ordering_uses_old_order(self):
        self._test_preserve_order(
            ["suite2", "suite1"], ["suite1", "suite2"], ["suite2", "suite1"]
        )

    def test_suite_ordering_adds_new_suites_to_end(self):
        self._test_preserve_order(["s3", "s2", "s1"], ["s1", "s2", "s3"], ["s3", "s2"])

    def test_suite_ordering_preserves_directory_suites(self):
        self._test_preserve_order(
            ["s.sub", "s3"], ["s.sub.s1", "s.sub.s2", "s3"], ["s.sub"]
        )
        self._test_preserve_order(
            ["s.sub", "s3"], ["s.sub.s1", "s.sub.s2", "s3"], ["s.sub"]
        )

    def test_suite_ordering_splits_directory_suite(self):
        self._test_preserve_order(
            ["s.sub.s1", "s.sub.s2"], ["s.sub.s1", "s.sub.s2"], ["s.sub.s1", "s.sub"]
        )

    def test_suite_ordering_preserves_wait_command(self):
        self._test_preserve_order(
            ["s2", "#WAIT", "s1", "s3"], ["s1", "s2", "s3"], ["s2", "#WAIT", "s1"]
        )
        self._test_preserve_order(
            ["s2", "#WAIT", "s3"], ["s2", "s3"], ["s2", "#WAIT", "s1"]
        )

    def test_suite_ordering_removes_wait_command_if_it_would_be_first_element(self):
        self._test_preserve_order(["s1", "s3"], ["s1", "s3"], ["s2", "#WAIT", "s1"])

    def test_suite_ordering_removes_wait_command_if_it_would_be_last_element(self):
        self._test_preserve_order(["s2"], ["s2"], ["s2", "#WAIT", "s1"])

    def test_suite_ordering_removes_double_wait_command(self):
        self._test_preserve_order(
            ["s2", "#WAIT", "s3"], ["s3", "s2"], ["s2", "#WAIT", "s1", "#WAIT", "s3"]
        )

    def test_suite_ordering_stores_two_wait_commands(self):
        self._test_preserve_order(
            ["s2", "#WAIT", "s1", "#WAIT", "s3"],
            ["s3", "s2", "s1"],
            ["s2", "#WAIT", "s1", "#WAIT", "s3"],
        )

    def test_suite_ordering_removes_directory_suite_subsuites_also_from_old_list(self):
        self._test_preserve_order(
            ["s1", "sub", "s4", "subi"],
            ["s1", "sub.s2", "sub.s3", "s4", "subi"],
            ["s1", "sub", "sub.s3", "s4"],
        )

    def test_suite_ordering_removes_directory_suite_subsuites_also_from_old_list_2(
        self,
    ):
        self._test_preserve_order(["s"], ["s.s1", "s.sub.s2", "s.s3"], ["s", "s.sub"])

    def test_suite_ordering_removes_old_duplicate(self):
        self._test_preserve_order(["a"], ["a"], ["a", "a"])

    def test_test_item_name_replaces_pattern_chars(self):
        item = t("Test [WITH] *funny* name?")
        opts = {}
        item.modify_options_for_executor(opts)
        if ROBOT_VERSION >= "3.1":
            self.assertEqual(opts["test"], "Test [[]WITH] [*]funny[*] name[?]")
        else:
            self.assertEqual(opts["test"], "Test [WITH] *funny* name?")

    def test_test_item_removes_rerunfailed_option(self):
        item = t("Some test")
        opts = {"rerunfailed": []}
        item.modify_options_for_executor(opts)
        self.assertTrue("rerunfailed" not in opts)

    def test_fix_items_splits_to_tests_when_suite_after_test_from_that_suite(self):
        expected_items = [t("s.t1"), t("s.t2")]
        items = [t("s.t1"), s("s", tests=["s.t1", "s.t2"])]
        self.assertEqual(expected_items, pabot._fix_items(items))

    def test_fix_items_combines_to_suite_when_test_from_suite_after_suite(self):
        expected_items = [s("s", tests=["s.t1", "s.t2"])]
        items = [s("s", tests=["s.t1", "s.t2"]), t("s.t1")]
        self.assertEqual(expected_items, pabot._fix_items(items))

    def test_fix_items_combines_subsuites_when_after_containing_suite(self):
        self.assertEqual([s("s")], pabot._fix_items([s("s"), s("s.s1")]))

    def test_fix_items_split_containig_suite_when_subsuite_before(self):
        self.assertEqual(
            [s("s.s1"), s("s.s2")],
            pabot._fix_items([s("s.s1"), s("s", suites=["s.s1", "s.s2"])]),
        )

    def test_fix_items_removes_duplicates(self):
        self.assertEqual([t("t")], pabot._fix_items([t("t"), t("t")]))
        self.assertEqual([s("s")], pabot._fix_items([s("s"), s("s")]))

    def test_fix_works_with_waits(self):
        w = execution_items.WaitItem
        self.assertEqual([], pabot._fix_items([w()]))
        self.assertEqual([], pabot._fix_items([w(), w()]))
        self.assertEqual([s("s")], pabot._fix_items([w(), s("s")]))
        self.assertEqual([s("s")], pabot._fix_items([s("s"), w()]))
        self.assertEqual(
            [s("s1"), w(), s("s2")], pabot._fix_items([s("s1"), w(), s("s2")])
        )
        self.assertEqual(
            [s("s1"), w(), s("s2")], pabot._fix_items([s("s1"), w(), w(), s("s2")])
        )

    def test_solve_suite_names_with_testlevelsplit_option(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        pabot_args = dict(self._pabot_args)
        pabot_args["testlevelsplit"] = True
        test_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=pabot_args,
        )
        self._assert_equal_names([self._all_tests], test_names)
        expected = self._psuitenames(
            datasource_hash,
            "65f95c924ba97541f47949701c4e3c51192a5b43",
            "no-suites-from-option",
            "2e667c32eb50b41dffd9f3d97a5c3f442b52a1ca",
            *self._all_with_tests
        )
        with pabot._open_pabotsuitenames("r") as f:
            actual = f.readlines()
            if PY2:
                actual = [l.decode("utf-8") for l in actual]
        self.assertEqual(expected, actual)

    def test_solve_suite_names_with_testlevelsplit_option_added(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            *self._all_with_suites
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["testlevelsplit"] = True
        test_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=pabot_args,
        )
        self._assert_equal_names([self._all_tests], test_names)
        expected = self._psuitenames(
            datasource_hash,
            "65f95c924ba97541f47949701c4e3c51192a5b43",
            "no-suites-from-option",
            "2e667c32eb50b41dffd9f3d97a5c3f442b52a1ca",
            *self._all_with_tests
        )
        with pabot._open_pabotsuitenames("r") as f:
            actual = f.readlines()
            if PY2:
                actual = [l.decode("utf-8") for l in actual]
        self.assertEqual(expected, actual)

    def test_solve_suite_names_ignores_testlevelsplit_if_suites_and_tests(self):
        all_suites = [
            s for s in self._all_suites if "Suite With Valueset Tags" not in s
        ]
        all_tests = [t for t in self._all_tests if "Suite With Valueset Tags" in t]
        all_with_suites = [
            s for s in self._all_with_suites if "Suite With Valueset Tags" not in s
        ]
        all_with_tests = [
            t for t in self._all_with_tests if "Suite With Valueset Tags" in t
        ]
        all_with = all_with_suites + all_with_tests
        all_names = all_suites + all_tests
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            "1ac0e4ebf55ba472c813b5ac9f8d870dfbd97756",
            *all_with
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["testlevelsplit"] = True
        test_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=pabot_args,
        )
        self._assert_equal_names([all_names], test_names)
        expected = self._psuitenames(
            datasource_hash,
            "65f95c924ba97541f47949701c4e3c51192a5b43",
            "no-suites-from-option",
            "9bfb1cffcc5fe8b0dfa2ee5a1587655d5da00f53",
            *all_with
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_leaves_suites_and_tests(self):
        all_suites = [
            s for s in self._all_suites if "Suite With Valueset Tags" not in s
        ]
        all_tests = [t for t in self._all_tests if "Suite With Valueset Tags" in t]
        all_with_suites = [
            s for s in self._all_with_suites if "Suite With Valueset Tags" not in s
        ]
        all_with_tests = [
            t for t in self._all_with_tests if "Suite With Valueset Tags" in t
        ]
        all_with = all_with_suites + all_with_tests
        all_names = all_suites + all_tests
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "65f95c924ba97541f47949701c4e3c51192a5b43",
            "no-suites-from-option",
            "c08124c3319cbb938d12ae5da81f83ab297f7c9f",
            *all_with
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["testlevelsplit"] = False
        test_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=pabot_args,
        )
        self._assert_equal_names([all_names], test_names)
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            "7beb0f073adfba9b7c36db527e65b3bdb3d14001",
            *all_with
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_suitesfrom_option(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=pabot_args,
        )
        self._assert_equal_names(
            [["Fixtures.Suite Second", "Fixtures.Suite One", "Fixtures.Suite Special"]],
            suite_names,
        )
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "f57c1949d5137773e0b9f6ca34c439a27a22bcb0",
            "03b4e1ff17f3a3e4a7f5c6a1b3c480956bbd83d5",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite Special",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_when_suitesfrom_file_added(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            "c06f2afdfa35791e82e71618bf60415e927c41ae",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite Special",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=pabot_args,
        )
        self._assert_equal_names(
            [["Fixtures.Suite Second", "Fixtures.Suite One", "Fixtures.Suite Special"]],
            suite_names,
        )
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "f57c1949d5137773e0b9f6ca34c439a27a22bcb0",
            "03b4e1ff17f3a3e4a7f5c6a1b3c480956bbd83d5",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite Special",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_when_suitesfrom_file_added_and_directory(self):
        pabotsuitenames = self._psuitenames(
            "oldhashcode",
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            "3847234ae935c0dc8fc72cf3f0beefb81fac79bf",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=pabot_args,
        )
        self._assert_equal_names(
            [
                [
                    "Fixtures.Suite Second",
                    "Fixtures.Suite One",
                    "Fixtures.Suite Special",
                    "Fixtures.Suite With Valueset Tags",
                    "Fixtures.Test Copy Artifacts.Suite 1",
                    "Fixtures.Test Copy Artifacts.Suite 2",
                ]
            ],
            suite_names,
        )
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "f57c1949d5137773e0b9f6ca34c439a27a22bcb0",
            "e33ce1259a999afd6c09c190c717d4d98bf6d5be",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_after_suitesfrom_file_removed(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "f57c1949d5137773e0b9f6ca34c439a27a22bcb0",
            "50d0c83b3c6b35ddc81c3289f5591d6574412c17",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite With Valueset Tags",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        pabot_args = dict(self._pabot_args)
        pabot_args["suitesfrom"] = "tests/output.xml"
        os.rename("tests/output.xml", "tests/output.xml.tmp")
        try:
            suite_names = pabot.solve_suite_names(
                outs_dir=self._outs_dir,
                datasources=self._datasources,
                options=self._options,
                pabot_args=pabot_args,
            )
        finally:
            os.rename("tests/output.xml.tmp", "tests/output.xml")
        self._assert_equal_names(
            [
                [
                    "Fixtures.Suite Second",
                    "Fixtures.Suite One",
                    "Fixtures.Suite Special",
                    "Fixtures.Suite With Valueset Tags",
                    "Fixtures.Test Copy Artifacts.Suite 1",
                    "Fixtures.Test Copy Artifacts.Suite 2",
                ]
            ],
            suite_names,
        )
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "da39a3ee5e6b4b0d3255bfef95601890afd80709",
            "644c540a9c30544812b1f1170635d077806a2669",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_pabotsuitenames_file(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        original = pabot._regenerate
        pabot._regenerate = lambda *args: 1 / 0
        try:
            suite_names = pabot.solve_suite_names(
                outs_dir=self._outs_dir,
                datasources=self._datasources,
                options=self._options,
                pabot_args=self._pabot_args,
            )
        finally:
            pabot._regenerate = original
        self._assert_equal_names(
            [
                [
                    "Fixtures.Suite Special",
                    "Fixtures.Suite Second",
                    "Fixtures.Suite One",
                    "Fixtures.Suite With Valueset Tags",
                    "Fixtures.Test Copy Artifacts.Suite 1",
                    "Fixtures.Test Copy Artifacts.Suite 2",
                ]
            ],
            suite_names,
        )

    def test_solve_suite_names_file_is_not_changed_when_invalid_cli_opts(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        self._options["loglevel"] = "INVALID123"
        try:
            pabot.solve_suite_names(
                outs_dir=self._outs_dir,
                datasources=self._datasources,
                options=self._options,
                pabot_args=self._pabot_args,
            )
            self.fail("Should have thrown DataError")
        except DataError:
            pass
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(pabotsuitenames, actual)

    def test_solve_suite_names_transforms_old_suite_names_to_new_format(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            "c65865c6eac504bddb6bd3f8ddeb18bd49b53c37",
            "Fixtures.Suite Special",
            "Fixtures.Suite Second",
            "Fixtures.Suite One",
            "Fixtures.Suite With Valueset Tags",
            "Fixtures.Test Copy Artifacts.Suite 1",
            "Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=self._pabot_args,
        )
        self._assert_equal_names(
            [
                [
                    "Fixtures.Suite Special",
                    "Fixtures.Suite Second",
                    "Fixtures.Suite One",
                    "Fixtures.Suite With Valueset Tags",
                    "Fixtures.Test Copy Artifacts.Suite 1",
                    "Fixtures.Test Copy Artifacts.Suite 2",
                ]
            ],
            suite_names,
        )
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_works_with_pabotsuitenames_file_with_wait_command(self):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            "--suite Fixtures.Suite Special",
            "#WAIT",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        original = pabot._regenerate
        pabot._regenerate = lambda *args: 1 / 0
        try:
            suite_names = pabot.solve_suite_names(
                outs_dir=self._outs_dir,
                datasources=self._datasources,
                options=self._options,
                pabot_args=self._pabot_args,
            )
        finally:
            pabot._regenerate = original
        self._assert_equal_names(
            [
                ["Fixtures.Suite Special"],
                [
                    "Fixtures.Suite Second",
                    "Fixtures.Suite One",
                    "Fixtures.Suite With Valueset Tags",
                    "Fixtures.Test Copy Artifacts.Suite 1",
                    "Fixtures.Test Copy Artifacts.Suite 2",
                ],
            ],
            suite_names,
        )

    def _assert_equal_names(self, names, output):
        output_names = [
            [s.name.decode("utf-8") if PY2 else s.name for s in suites]
            for suites in pabot._group_by_wait(output)
        ]
        self.assertEqual(names, output_names)

    def test_solve_suite_names_works_with_pabotsuitenames_file_with_wait_command_when_cli_change(
        self,
    ):
        pabotsuitenames = self._psuitenames(
            datasource_hash,
            "old-command-line-options",
            "no-suites-from-option",
            file_hash,
            "--suite Fixtures.Suite Special",
            "#WAIT",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames)
        original = pabot._regenerate
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=self._pabot_args,
        )
        self._assert_equal_names(
            [
                ["Fixtures.Suite Special"],
                [
                    "Fixtures.Suite Second",
                    "Fixtures.Suite One",
                    "Fixtures.Suite With Valueset Tags",
                    "Fixtures.Test Copy Artifacts.Suite 1",
                    "Fixtures.Test Copy Artifacts.Suite 2",
                ],
            ],
            suite_names,
        )
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            "--suite Fixtures.Suite Special",
            "#WAIT",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite One",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_with_corrupted_pabotsuitenames_file(self):
        pabotsuitenames_corrupted = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            "4f2fc7af25040e0f3b9e2681b84594ccb0cdf9e",
            "--suite Fixtures.Suite Special",
            "--suite NoneExisting",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
        )
        with open(".pabotsuitenames", "w") as f:
            f.writelines(pabotsuitenames_corrupted)
        suite_names = pabot.solve_suite_names(
            outs_dir=self._outs_dir,
            datasources=self._datasources,
            options=self._options,
            pabot_args=self._pabot_args,
        )
        self._assert_equal_names(
            [
                [
                    "Fixtures.Suite Special",
                    "Fixtures.Suite Second",
                    "Fixtures.Suite With Valueset Tags",
                    "Fixtures.Test Copy Artifacts.Suite 1",
                    "Fixtures.Test Copy Artifacts.Suite 2",
                    "Fixtures.Suite One",
                ]
            ],
            suite_names,
        )
        expected = self._psuitenames(
            datasource_hash,
            "97d170e1550eee4afc0af065b78cda302a97674c",
            "no-suites-from-option",
            file_hash,
            "--suite Fixtures.Suite Special",
            "--suite Fixtures.Suite Second",
            "--suite Fixtures.Suite With Valueset Tags",
            "--suite Fixtures.Test Copy Artifacts.Suite 1",
            "--suite Fixtures.Test Copy Artifacts.Suite 2",
            "--suite Fixtures.Suite One",
        )
        with open(".pabotsuitenames", "r") as f:
            actual = f.readlines()
        self.assertEqual(expected, actual)

    def test_solve_suite_names_with_ioerror_pabotsuitenames(self):
        if os.path.isfile(".pabotsuitenames"):
            os.remove(".pabotsuitenames")
        os.mkdir(".pabotsuitenames")
        try:
            suite_names = pabot.solve_suite_names(
                outs_dir=self._outs_dir,
                datasources=self._datasources,
                options=self._options,
                pabot_args=self._pabot_args,
            )
            self._assert_equal_names([self._all_suites], suite_names)
        finally:
            os.rmdir(".pabotsuitenames")

    def test_rebot_conf(self):
        opt = self._options.copy()
        opt["suite"] = ["s1", "s2"]
        opt["test"] = ["t1", "t2"]
        opt["include"] = ["tag"]
        opt["exclude"] = ["nontag"]
        options = pabot._options_for_rebot(opt, "starttime", "endtime")
        self.assertEqual(options["suite"], [])
        self.assertEqual(options["test"], [])
        self.assertEqual(options["include"], [])
        self.assertEqual(options["exclude"], [])
        for key in self._options:
            if key in [
                "skip",
                "skiponfailure",
                "variable",
                "variablefile",
                "listener",
                "prerunmodifier",
                "monitorcolors",
                "language",
                "parser",
            ]:
                self.assertFalse(key in options, "%s should not be in options" % key)
            else:
                self.assertEqual(options[key], self._options[key])

    def test_greates_common_name(self):
        self.assertEqual(pabot._find_ending_level("foo.bar", ["a", "b"]), "foo")
        self.assertEqual(
            pabot._find_ending_level("foo.bar", ["foo.zoo", "b"]), "foo.bar"
        )
        self.assertEqual(pabot._find_ending_level("foo.bar", []), "")
        self.assertEqual(
            pabot._find_ending_level("foo.bar", ["foo.bar"]), "foo.bar.PABOT_noend"
        )
        self.assertEqual(
            pabot._find_ending_level("foo.bar.zoo", ["foo.bar.boo", "foo.zoo"]),
            "foo.bar.zoo",
        )

    def test_parallel_execution(self):
        dtemp = tempfile.mkdtemp()
        outs_dir = os.path.join(dtemp, "pabot_results")
        self._options["outputdir"] = dtemp
        self._pabot_args["pabotlibport"] = 4000 + random.randint(0, 1000)
        self._pabot_args["testlevelsplit"] = False
        lib_process = pabot._start_remote_library(self._pabot_args)
        pabot._initialize_queue_index()
        try:
            suite_names = [s(_s) for _s in self._all_suites]
            items = [
                pabot.QueueItem(
                    self._datasources,
                    outs_dir,
                    self._options,
                    suite,
                    self._pabot_args["command"],
                    self._pabot_args["verbose"],
                    argfile,
                )
                for suite in suite_names
                for argfile in self._pabot_args["argumentfiles"] or [("", None)]
            ]
            pabot._parallel_execute(
                items,
                self._pabot_args["processes"],
                self._datasources,
                outs_dir,
                self._options,
                self._pabot_args,
            )
            result_code = pabot._report_results(
                outs_dir,
                self._pabot_args,
                self._options,
                pabot._now(),
                pabot._get_suite_root_name([suite_names]),
            )
            self.assertEqual(10, result_code)
        finally:
            pabot._stop_remote_library(lib_process)
            shutil.rmtree(dtemp)

    def test_parallel_execution_with_testlevelsplit(self):
        dtemp = tempfile.mkdtemp()
        outs_dir = os.path.join(dtemp, "pabot_results")
        self._options["outputdir"] = dtemp
        self._pabot_args["pabotlibport"] = 4000 + random.randint(0, 1000)
        self._pabot_args["testlevelsplit"] = True
        lib_process = pabot._start_remote_library(self._pabot_args)
        pabot._initialize_queue_index()
        try:
            test_names = [t(_t) for _t in self._all_tests]
            items = [
                pabot.QueueItem(
                    self._datasources,
                    outs_dir,
                    self._options,
                    test,
                    self._pabot_args["command"],
                    self._pabot_args["verbose"],
                    argfile,
                )
                for test in test_names
                for argfile in self._pabot_args["argumentfiles"] or [("", None)]
            ]
            pabot._parallel_execute(
                items,
                self._pabot_args["processes"],
                self._datasources,
                outs_dir,
                self._options,
                self._pabot_args,
            )
            result_code = pabot._report_results(
                outs_dir,
                self._pabot_args,
                self._options,
                pabot._now(),
                pabot._get_suite_root_name([test_names]),
            )
            self.assertEqual(12, result_code)
        finally:
            pabot._stop_remote_library(lib_process)
            shutil.rmtree(dtemp)

    def test_suite_root_name(self):
        def t(l):
            return [[s(i) for i in suites] for suites in l]

        self.assertEqual(
            pabot._get_suite_root_name(t([["Foo.Bar", "Foo.Zoo"], ["Foo.Boo"]])), "Foo"
        )
        self.assertEqual(
            pabot._get_suite_root_name(t([["Foo.Bar", "Foo.Zoo"], ["Boo"]])), ""
        )
        self.assertEqual(
            pabot._get_suite_root_name(t([["Bar", "Foo.Zoo"], ["Foo.Boo"]])), ""
        )
        self.assertEqual(pabot._get_suite_root_name(t([[]])), "")

    def test_copy_output_artifacts_direct_screenshots_only(self):
        out_dir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "outputs/outputs_with_artifacts/out_dir",
        )
        _opts = {"outputdir": out_dir}
        pabot._copy_output_artifacts(options=_opts)
        files_should_be_copied = [
            "0-fake_screenshot_root.png",
            "1-fake_screenshot_root.png",
        ]

        for f in files_should_be_copied:
            file_path = os.path.join(_opts["outputdir"], f)
            self.assertTrue(os.path.isfile(file_path), "file not copied: {}".format(f))
            os.remove(file_path)  # clean up

        files_should_not_be_copied = [
            "screenshots/0-fake_screenshot_subfolder_1.png",
            "screenshots/0-fake_screenshot_subfolder_2.png"
            "screenshots/1-fake_screenshot_subfolder_1.png",
            "screenshots/2-fake_screenshot_subfolder_2.png",
            "other_artifacts/0-some_artifact.foo",
            "other_artifacts/0-another_artifact.bar",
            "other_artifacts/1-some_artifact.foo",
            "other_artifacts/1-another_artifact.bar",
        ]
        for f in files_should_not_be_copied:
            self.assertFalse(
                os.path.isfile(os.path.join(_opts["outputdir"], f)),
                "file copied wrongly: {}".format(f),
            )

    def test_copy_output_artifacts_include_subfolders(self):
        out_dir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "outputs/outputs_with_artifacts/out_dir",
        )
        _opts = {"outputdir": out_dir}
        pabot._copy_output_artifacts(
            options=_opts,
            file_extensions=["png", "foo", "bar"],
            include_subfolders=True,
        )
        files_should_be_copied = [
            "0-fake_screenshot_root.png",
            "1-fake_screenshot_root.png",
            "screenshots/0-fake_screenshot_subfolder_1.png",
            "screenshots/0-fake_screenshot_subfolder_2.png",
            "screenshots/1-fake_screenshot_subfolder_1.png",
            "screenshots/1-fake_screenshot_subfolder_2.png",
            "other_artifacts/0-some_artifact.foo",
            "other_artifacts/0-another_artifact.bar",
            "other_artifacts/1-some_artifact.foo",
            "other_artifacts/1-another_artifact.bar",
        ]
        for f in files_should_be_copied:
            file_path = os.path.join(_opts["outputdir"], f)
            self.assertTrue(os.path.isfile(file_path), "file not copied: {}".format(f))
            os.remove(file_path)  # clean up

    def test_merge_one_run_with_and_without_legacyoutput(self):
        dtemp = tempfile.mkdtemp()
        # Create the same directory structure as pabot
        test_outputs = os.path.join(dtemp, "outputs")
        os.makedirs(test_outputs)
        test_output = os.path.join(test_outputs, "output.xml")
        # Create a minimal but valid output.xml
        with open(test_output, "w") as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Rebot 7.1.1 (Python 3.11.7 on darwin)" generated="20241130 11:19:45.235" rpa="false" schemaversion="4">
<suite id="s1" name="Suites">
<suite id="s1-s1" name="Test" source="/Users/mkorpela/workspace/pabot/test.robot">
<test id="s1-s1-t1" name="Testing" line="5">
<kw name="Log" library="BuiltIn">
<msg timestamp="20241130 11:19:44.911" level="INFO">hello</msg>
<arg>hello</arg>
<doc>Logs the given message with the given level.</doc>
<status status="PASS" starttime="20241130 11:19:44.911" endtime="20241130 11:19:44.911"/>
</kw>
<status status="PASS" starttime="20241130 11:19:44.910" endtime="20241130 11:19:44.911"/>
</test>
<status status="PASS" starttime="20241130 11:19:44.909" endtime="20241130 11:19:44.914"/>
</suite>
<suite id="s1-s2" name="Test" source="/Users/mkorpela/workspace/pabot/test.robot">
<test id="s1-s2-t1" name="Testing" line="5">
<kw name="Log" library="BuiltIn">
<msg timestamp="20241130 11:19:44.913" level="INFO">hello</msg>
<arg>hello</arg>
<doc>Logs the given message with the given level.</doc>
<status status="PASS" starttime="20241130 11:19:44.913" endtime="20241130 11:19:44.913"/>
</kw>
<status status="PASS" starttime="20241130 11:19:44.913" endtime="20241130 11:19:44.913"/>
</test>
<status status="PASS" starttime="20241130 11:19:44.912" endtime="20241130 11:19:44.914"/>
</suite>
<doc>[https://pabot.org/?ref=log|Pabot] result from 1 executions.</doc>
<status status="PASS" starttime="20241130 11:19:44.893" endtime="20241130 11:19:44.914"/>
</suite>
<statistics>
<total>
<stat pass="2" fail="0" skip="0">All Tests</stat>
</total>
<tag>
</tag>
<suite>
<stat pass="2" fail="0" skip="0" id="s1" name="Suites">Suites</stat>
<stat pass="1" fail="0" skip="0" id="s1-s1" name="Test">Suites.Test</stat>
<stat pass="1" fail="0" skip="0" id="s1-s2" name="Test">Suites.Test</stat>
</suite>
</statistics>
<errors>
<msg timestamp="20241130 11:19:44.910" level="ERROR">Error in file '/Users/mkorpela/workspace/pabot/test.robot' on line 2: Library 'Easter' expected 0 arguments, got 1.</msg>
<msg timestamp="20241130 11:19:44.913" level="ERROR">Error in file '/Users/mkorpela/workspace/pabot/test.robot' on line 2: Library 'Easter' expected 0 arguments, got 1.</msg>
</errors>
</robot>"""
            )

        self._options["outputdir"] = dtemp
        if ROBOT_VERSION >= "7.0":
            self._options["legacyoutput"] = True
        try:
            output = pabot._merge_one_run(
                outs_dir=dtemp,
                options=self._options,
                tests_root_name="Test",  # Should match suite name in XML
                stats={
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                },
                copied_artifacts=[],
                outputfile="merged_output.xml",
            )  # Use different name to avoid confusion
            self.assertTrue(
                output, "merge_one_run returned empty string"
            )  # Verify we got output path
            with open(output, "r") as f:
                content = f.read()
                if ROBOT_VERSION >= "6.1":
                    self.assertIn('schemaversion="4"', content)
                elif ROBOT_VERSION >= "5.0":
                    self.assertIn('schemaversion="3"', content)
                elif ROBOT_VERSION >= "4.0":
                    self.assertIn('schemaversion="2"', content)
            if ROBOT_VERSION >= "7.0":
                del self._options["legacyoutput"]
                output = pabot._merge_one_run(
                    outs_dir=dtemp,
                    options=self._options,
                    tests_root_name="Test",  # Should match suite name in XML
                    stats={
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "skipped": 0,
                    },
                    copied_artifacts=[],
                    outputfile="merged_2_output.xml",
                )  # Use different name to avoid confusion
                self.assertTrue(
                    output, "merge_one_run returned empty string"
                )  # Verify we got output path
                with open(output, "r") as f:
                    content = f.read()
                self.assertIn('schemaversion="5"', content)
                self.assertNotIn('schemaversion="4"', content)
        finally:
            shutil.rmtree(dtemp)

    def test_parse_args_mixed_order(self):
        (
            options,
            datasources,
            pabot_args,
            options_for_subprocesses,
        ) = arguments.parse_args(
            [
                "--exitonfailure",
                "--processes",
                "12",
                "--outputdir",
                "mydir",
                "--verbose",
                "--pabotlib",
                "suite",
            ]
        )
        self.assertEqual(pabot_args["processes"], 12)
        self.assertEqual(pabot_args["verbose"], True)
        self.assertEqual(pabot_args["pabotlib"], True)
        self.assertEqual(options["outputdir"], "mydir")
        self.assertEqual(options["exitonfailure"], True)
        self.assertEqual(datasources, ["suite"])

    def test_parse_args_error_handling(self):
        with self.assertRaises(DataError) as cm:
            arguments.parse_args(["--processes"])
        self.assertIn("requires a value", str(cm.exception))

        with self.assertRaises(DataError) as cm:
            arguments.parse_args(["--processes", "invalid"])
        self.assertIn("Invalid value for --processes", str(cm.exception))

        with self.assertRaises(DataError) as cm:
            arguments.parse_args(["--command", "echo", "hello"])
        self.assertIn("requires matching --end-command", str(cm.exception))

    def test_parse_args_command_with_pabot_args(self):
        options, datasources, pabot_args, _ = arguments.parse_args(
            [
                "--command",
                "script.sh",
                "--processes",
                "5",
                "--end-command",
                "--verbose",
                "suite",
            ]
        )
        self.assertEqual(pabot_args["command"], ["script.sh", "--processes", "5"])
        self.assertEqual(pabot_args["verbose"], True)

    def test_pabotlib_defaults_to_enabled(self):
        options, _, pabot_args, _ = arguments.parse_args(["suite"])
        self.assertTrue(pabot_args["pabotlib"])
        self.assertFalse("no_pabotlib" in pabot_args)  # Ensure internal flag not leaked

    def test_no_pabotlib_disables_pabotlib(self):
        options, _, pabot_args, _ = arguments.parse_args(["--no-pabotlib", "suite"])
        self.assertFalse(pabot_args["pabotlib"])
        self.assertFalse("no_pabotlib" in pabot_args)  # Ensure internal flag not leaked

    def test_pabotlib_option_shows_warning(self):
        options, _, pabot_args, _ = arguments.parse_args(["--pabotlib", "suite"])
        self.assertTrue(pabot_args["pabotlib"])
        self.assertFalse("no_pabotlib" in pabot_args)  # Ensure internal flag not leaked

    def test_conflicting_pabotlib_options_raise_error(self):
        with self.assertRaises(DataError) as context:
            arguments.parse_args(["--pabotlib", "--no-pabotlib", "suite"])
        self.assertIn(
            "Cannot use both --pabotlib and --no-pabotlib", str(context.exception)
        )


if __name__ == "__main__":
    unittest.main()
