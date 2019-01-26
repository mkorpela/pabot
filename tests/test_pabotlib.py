import unittest
import time
import os
import tempfile
import shutil
import random
from pabot import pabotlib

class PabotLibTests(unittest.TestCase):

    def setUp(self):
        builtinmock = lambda:0
        builtinmock.get_variable_value = lambda *args:None
        self._runs = 0
        def runned(*args):
            self._runs += 1
        builtinmock.run_keyword = runned
        pabotlib.BuiltIn = lambda:builtinmock

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

    def test_acquire_and_release_lock(self):
        lib = pabotlib.PabotLib()
        self.assertTrue(lib.acquire_lock("lockname"))
        self.assertTrue(lib.acquire_lock("lock2"))
        lib.release_lock("lockname")
        self.assertTrue(lib.acquire_lock("lockname"))
        lib.release_lock("lock2")
        lib.release_lock("lockname")

    def test_acquire_and_release_valueset(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(resourcefile=os.path.join("tests", "resourcefile.dat"))
        vals = lib.acquire_value_set()
        self.assertIn(vals, ["MyValueSet", "TestSystemWithLasers", "TestSystemWithTachyonCannon"])
        value = lib.get_value_from_set("key")
        lib.release_value_set()
        self.assertEqual(value, "someval")

    def test_acquire_and_release_valueset_with_tag(self):
        lib = pabotlib.PabotLib()
        lib._values = lib._parse_values(resourcefile=os.path.join("tests", "resourcefile.dat"))
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


if __name__ == '__main__':
    unittest.main()