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
        self.tests = []

    def end_test(self, test):
        self.tests.append(test.longname)

class ResultMergerTests(unittest.TestCase):

    def test_something(self):
        result = result_merger.merge([
            'tests/outputs/first.xml',
            'tests/outputs/second.xml',
            'tests/outputs/third.xml'
        ], {}, "root")
        visitor = ResultStats()
        result.visit(visitor)
        self.assertEqual(
            ['Tmp.Tests.First', 'Tmp.Tests.Second', 'Tmp.Tests.Third'], 
            visitor.tests)


if __name__ == '__main__':
    unittest.main()
