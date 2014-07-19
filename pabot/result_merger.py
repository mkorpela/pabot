__author__ = 'mkorpela'
#  Copyright 2014 Mikko Korpela GPLv3
#  partly based on work by Nokia Solutions and Networks
#  that was licensed under Apache License Version 2.0

from robot.model import SuiteVisitor


class ResultMerger(SuiteVisitor):

    def __init__(self, result):
        self.root = result.suite
        self.current = None
        self._skip_until = None

    def merge(self, merged):
        merged.suite.visit(self)

    def start_suite(self, suite):
        if self._skip_until and self._skip_until != suite:
            return
        if not self.current:
            self.current = self._find_root(suite)
        else:
            next = self._find(self.current.suites, suite.name)
            if next is None:
                self.current.suites.append(suite)
                self._skip_until = suite

    def _find_root(self, suite):
        if self.root.name != suite.name:
            raise ValueError('self.root.name "%s" != suite.name "%s"' % (self.root.name, suite.name))
        return self.root

    def _find(self, items, name):
        for item in items:
            if item.name == name:
                return item
        return None

    def end_suite(self, suite):
        if self._skip_until and self._skip_until != suite:
            return
        if self._skip_until == suite:
            self._skip_until = None
            return
        self.current = self.current.parent

    def visit_test(self, test):
        pass

if __name__ == '__main__':
    from robot.api import ExecutionResult
    result1 = ExecutionResult('../tmp/passing.xml')
    result2 = ExecutionResult('../tmp/failing.xml')
    ResultMerger(result1).merge(result2)
    result1.save('../tmp/merged.xml')
