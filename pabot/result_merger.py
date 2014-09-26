#  Copyright 2014 Mikko Korpela
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#  partly based on work by Pekka Klarck
#  by Nokia Solutions and Networks
#  that was licensed under Apache License Version 2.0

from robot.api import ExecutionResult
from robot.model import SuiteVisitor

class ResultMerger(SuiteVisitor):

    def __init__(self, result):
        self.root = result.suite
        self.current = None
        self._skip_until = None

    def merge(self, merged):
        try:
            merged.suite.visit(self)
        except:
            print 'Error while merging result %s' % merged.source
            raise

    def start_suite(self, suite):
        if self._skip_until and self._skip_until != suite:
            return
        if not self.current:
            self.current = self._find_root(suite)
            assert self.current
        else:
            next = self._find(self.current.suites, suite.name)
            if next is None:
                self.current.suites.append(suite)
                suite.parent = self.current
                self._skip_until = suite
            else:
                self.current = next


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

def merge(*result_files):
    assert len(result_files) > 0
    out = ExecutionResult(result_files[0])
    merger = ResultMerger(out)
    for result in result_files[1:]:
        merger.merge(ExecutionResult(result))
    return out

