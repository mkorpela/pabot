import unittest
import time
import os
import tempfile
import shutil
import random
import pabot.result_merger as result_merger
from robot.result.visitor import ResultVisitor


class ResultStats(ResultVisitor):
    def __init__(self):
        self.suites = []
        self.tests = []

    def end_test(self, test):
        self.tests.append(test.longname)

    def end_suite(self, suite):
        self.suites.append(suite.longname)


class ResultMergerTests(unittest.TestCase):
    def test_test_level_run_merge(self):
        result = result_merger.merge(
            [
                "tests/outputs/first.xml",
                "tests/outputs/second.xml",
                "tests/outputs/third.xml",
            ],
            {},
            "root",
            [],
        )
        visitor = ResultStats()
        result.visit(visitor)
        self.assertEqual(["Tmp.Tests", "Tmp"], visitor.suites)
        self.assertEqual(
            ["Tmp.Tests.First", "Tmp.Tests.Second", "Tmp.Tests.Third"], visitor.tests
        )

    def test_suite_level_run_merge(self):
        result = result_merger.merge(
            ["tests/outputs/tests.xml", "tests/outputs/tests2.xml"], {}, "root", []
        )
        visitor = ResultStats()
        result.visit(visitor)
        self.assertEqual(
            [
                "Tmp.Tests.First",
                "Tmp.Tests.Second",
                "Tmp.Tests.Third",
                "Tmp.Tests2.First 2",
                "Tmp.Tests2.Second 2",
                "Tmp.Tests2.Third 2",
            ],
            visitor.tests,
        )
        self.assertEqual(["Tmp.Tests", "Tmp.Tests2", "Tmp"], visitor.suites)

    def test_prefixing(self):
        self.assertEqual(
            result_merger.prefix(os.path.join("foo", "bar", "zoo", "ba2r.xml")), "zoo"
        )
        self.assertEqual(
            result_merger.prefix(os.path.join("/zoo", "baa", "floo.txt")), "baa"
        )
        self.assertEqual(result_merger.prefix(os.path.join("koo", "foo.bar")), "koo")
        self.assertEqual(result_merger.prefix("hui.txt"), "")


if __name__ == "__main__":
    unittest.main()
