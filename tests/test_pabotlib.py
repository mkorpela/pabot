import unittest
import os

from robot.errors import RobotError

from pabot import pabotlib
from pabot.SharedLibrary import SharedLibrary
from robot.running.context import EXECUTION_CONTEXTS
from robot.running.namespace import Namespace
from robot.running.model import TestSuite
from robot.variables import Variables
from robot import __version__ as ROBOT_VERSION


class PabotLibTests(unittest.TestCase):
    def setUp(self):
        builtinmock = lambda: 0
        builtinmock.get_variable_value = lambda *args: None
        self._runs = 0

        def runned(*args):
            self._runs += 1

        builtinmock.run_keyword = runned
        pabotlib.BuiltIn = lambda: builtinmock
        self.builtinmock = builtinmock

    def test_shared_library_with_args(self):
        try:
            self._create_ctx()  # Set up Robot Framework context
            lib = SharedLibrary("mylib", ["2"])
            self.assertIsNotNone(lib)
            lib._remote = None
            lib._lib.run_keyword("mykeyword", ["arg"], {})
        except Exception as e:
            self.fail(f"SharedLibrary initialization failed: {str(e)}")

    def test_pabotlib_listener_path(self):
        lib = pabotlib.PabotLib()
        lib._start_suite("Suite", {"longname": "Suite"})
        self.assertEqual(lib._path, "Suite")
        lib._start_test("Test", {"longname": "Suite.Test"})
        self.assertEqual(lib._path, "Suite.Test")
        lib._start_keyword("Keyword1", {})
        self.assertEqual(lib._path, "Suite.Test.0")
        lib._end_keyword("Keyword1", {})
        lib._start_keyword("Keyword2", {})
        self.assertEqual(lib._path, "Suite.Test.1")
        lib._end_keyword("Keyword2", {})
        self.assertEqual(lib._path, "Suite.Test")
        lib._end_test("Test", {"longname": "Suite.Test"})
        self.assertEqual(lib._path, "Suite")
        lib._end_suite("Suite", {"longname": "Suite"})
        self.assertEqual(lib._path, "")
        lib._close()

    def test_pabotlib_listener_when_dynamic_import_with_import_library(self):
        lib = pabotlib.PabotLib()
        lib._end_keyword("Import Library", {})
        self.assertEqual(lib._path, "0")
        lib._start_keyword("Some Keyword", {})
        self.assertEqual(lib._path, "0.1")
        lib._end_keyword("Some Keyword", {})
        self.assertEqual(lib._path, "0")
        lib._start_keyword("Some Keyword 2", {})
        self.assertEqual(lib._path, "0.2")
        lib._end_keyword("Some Keyword 2", {})
        self.assertEqual(lib._path, "0")
        lib._end_keyword("Big word", {})
        self.assertEqual(lib._path, "1")
        lib._start_keyword("Little word", {})
        self.assertEqual(lib._path, "1.1")
        lib._end_keyword("Little word", {})
        self.assertEqual(lib._path, "1")
        lib._end_test("Test", {"longname": "Suite.Test"})
        self.assertEqual(lib._path, "Suite")
        lib._end_suite("Suite", {"longname": "Suite"})
        self.assertEqual(lib._path, "")
        lib._close()

    def test_pabotlib_listener_from_start_keyword(self):
        lib = pabotlib.PabotLib()
        # Don't know if this is possible.
        lib._start_keyword("Some Keyword", {})
        self.assertEqual(lib._path, "0.0")
        lib._end_keyword("Some Keyword", {})
        self.assertEqual(lib._path, "0")
        lib._start_keyword("Some Keyword 2", {})
        self.assertEqual(lib._path, "0.1")
        lib._end_keyword("Some Keyword 2", {})
        self.assertEqual(lib._path, "0")
        lib._end_keyword("Big word", {})
        self.assertEqual(lib._path, "1")
        lib._start_keyword("Little word", {})
        self.assertEqual(lib._path, "1.1")
        lib._end_keyword("Little word", {})
        self.assertEqual(lib._path, "1")
        lib._end_test("Test", {"longname": "Suite.Test"})
        self.assertEqual(lib._path, "Suite")
        lib._end_suite("Suite", {"longname": "Suite"})
        self.assertEqual(lib._path, "")
        lib._close()

    def test_pabotlib_listener_from_end_keywords(self):
        lib = pabotlib.PabotLib()
        lib._end_keyword("Some Keyword", {})
        self.assertEqual(lib._path, "0")
        lib._end_keyword("Some Keyword 2", {})
        self.assertEqual(lib._path, "1")
        lib._end_keyword("Big word", {})
        self.assertEqual(lib._path, "2")
        lib._start_keyword("Little word", {})
        self.assertEqual(lib._path, "2.1")
        lib._end_keyword("Little word", {})
        self.assertEqual(lib._path, "2")
        lib._end_test("Test", {"longname": "Suite.Test"})
        self.assertEqual(lib._path, "Suite")
        lib._end_suite("Suite", {"longname": "Suite"})
        self.assertEqual(lib._path, "")
        lib._close()

    def test_pabotlib_set_get_parallel_value(self):
        lib = pabotlib.PabotLib()
        lib.set_parallel_value_for_key("key", 1)
        value = lib.get_parallel_value_for_key("key")
        self.assertEqual(value, 1)

    def test_pabotlib_run_only_once(self):
        lib = pabotlib.PabotLib()
        self.assertEqual(self._runs, 0)
        lib.run_only_once("keyword")
        self.assertEqual(self._runs, 1)
        lib.run_only_once("keyword")
        self.assertEqual(self._runs, 1)

    def test_pabotlib_run_on_last_process(self):
        lib = pabotlib.PabotLib()
        self.assertEqual(self._runs, 0)
        self.builtinmock.get_variable_value = lambda *args: "0"
        lib.run_on_last_process("keyword")
        self.assertEqual(self._runs, 0)
        self.builtinmock.get_variable_value = lambda *args: "1"
        lib.get_parallel_value_for_key = lambda *args: 1
        lib.run_on_last_process("keyword")
        self.assertEqual(self._runs, 1)

    def test_pabotlib_run_on_last_process_defaults_to_running(self):
        lib = pabotlib.PabotLib()
        self.assertEqual(self._runs, 0)
        lib.run_on_last_process("keyword")
        self.assertEqual(self._runs, 1)

    def test_acquire_and_release_lock(self):
        lib = pabotlib.PabotLib()
        self.assertTrue(lib.acquire_lock("lockname"))
        self.assertTrue(lib.acquire_lock("lock2"))
        lib.release_lock("lockname")
        self.assertTrue(lib.acquire_lock("lockname"))
        lib.release_lock("lock2")
        lib.release_lock("lockname")

    def test_releasing_lock_on_close(self):
        lib = pabotlib.PabotLib()
        self.assertTrue(lib.acquire_lock("somelock"))
        self.assertTrue(lib.acquire_lock("somelock2"))
        self.assertTrue("somelock" in lib._locks)
        self.assertTrue("somelock2" in lib._locks)
        lib._close()
        self.assertTrue("somelock" not in lib._locks)
        self.assertTrue("somelock2" not in lib._locks)

    def test_acquire_and_release_valueset(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(
            resourcefile=os.path.join("tests", "resourcefile.dat")
        )
        vals = lib.acquire_value_set()
        self.assertIn(
            vals, ["MyValueSet", "TestSystemWithLasers", "TestSystemWithTachyonCannon"]
        )
        value = lib.get_value_from_set("key")
        try:
            lib.get_value_from_set("nokey")
            raise RuntimeError("This should not go here")
        except AssertionError:
            pass
        lib.release_value_set()
        self.assertEqual(value, "someval")
        try:
            lib.get_value_from_set("key")
            raise RuntimeError("This should not go here")
        except AssertionError:
            pass

    def test_acquire_and_disable_valueset(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(
            resourcefile=os.path.join("tests", "resourcefile.dat")
        )
        vals = lib.acquire_value_set()
        self.assertIn(
            vals, ["MyValueSet", "TestSystemWithLasers", "TestSystemWithTachyonCannon"]
        )
        lib.disable_value_set()
        vals2 = lib.acquire_value_set()
        self.assertNotEqual(vals, vals2)
        lib.release_value_set()

    def test_add_to_valueset(self):
        lib = pabotlib.PabotLib()
        my_value_set_1 = {"key": "someVal1", "tags": "valueset1,common"}
        my_value_set_2 = {"key": "someVal2", "tags": "valueset2,common"}
        lib.add_value_to_set("MyValueSet1", my_value_set_1)
        lib.add_value_to_set("MyValueSet2", my_value_set_2)
        vals = lib.acquire_value_set("common")
        self.assertIn(vals, ["MyValueSet1", "MyValueSet2"])
        lib.release_value_set()
        lib.acquire_value_set("valueset1")
        self.assertEqual("someVal1", lib.get_value_from_set("key"))
        lib.release_value_set()
        lib.acquire_value_set("valueset2")
        self.assertEqual("someVal2", lib.get_value_from_set("key"))
        lib.release_value_set()

    def test_ignore_execution_will_not_run_special_keywords_after(self):
        lib = pabotlib.PabotLib()
        try:
            lib.ignore_execution()
            self.fail("Should have thrown an exception")
        except RobotError:
            pass
        self.assertEqual(self._runs, 0)
        lib.run_on_last_process("keyword")
        self.assertEqual(self._runs, 0)
        lib.run_only_once("keyword")
        self.assertEqual(self._runs, 0)
        lib.run_setup_only_once("keyword")
        self.assertEqual(self._runs, 0)
        lib.run_teardown_only_once("keyword")
        self.assertEqual(self._runs, 0)

    def test_acquire_and_release_valueset_with_tag(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(
            resourcefile=os.path.join("tests", "resourcefile.dat")
        )
        vals = lib.acquire_value_set("laser")
        self.assertEqual(vals, "TestSystemWithLasers")
        value = lib.get_value_from_set("noise")
        self.assertEqual(value, "zapp")
        lib.release_value_set()
        vals = lib.acquire_value_set("tachyon")
        self.assertEqual(vals, "TestSystemWithTachyonCannon")
        value = lib.get_value_from_set("noise")
        self.assertEqual(value, "zump")
        lib.release_value_set()

    def test_acquire_and_release_valueset_with_shared_tag(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(
            resourcefile=os.path.join("tests", "resourcefile.dat")
        )
        vals = lib.acquire_value_set("commontag")
        self.assertIn(vals, ["TestSystemWithLasers", "TestSystemWithTachyonCannon"])
        value = lib.get_value_from_set("commonval")
        lib.release_value_set()
        self.assertEqual(value, "true")

    def test_reacquire_valueset(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(
            resourcefile=os.path.join("tests", "resourcefile.dat")
        )
        lib.acquire_value_set()
        try:
            lib.acquire_value_set()
            self.fail("Should have thrown an exception")
        except ValueError:
            pass
        finally:
            lib.release_value_set()

    def test_trying_to_acquire_valueset_with_none_existing_tag(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(
            resourcefile=os.path.join("tests", "resourcefile.dat")
        )
        try:
            lib.acquire_value_set("none-existing-tag")
            self.fail("Should have thrown an exception")
        except ValueError:
            pass

    def _output(self):
        output = lambda: 0
        output.start_keyword = output.end_keyword = lambda *a: 0
        output.fail = output.debug = output.trace = lambda *a: 0
        return output

    def _create_ctx(self):
        suite = TestSuite()
        variables = Variables()
        EXECUTION_CONTEXTS._contexts = []
        if ROBOT_VERSION >= "6.0":
            EXECUTION_CONTEXTS.start_suite(
                suite, Namespace(variables, suite, suite.resource, []), self._output()
            )
        else:
            EXECUTION_CONTEXTS.start_suite(
                suite, Namespace(variables, suite, suite.resource), self._output()
            )


if __name__ == "__main__":
    unittest.main()
