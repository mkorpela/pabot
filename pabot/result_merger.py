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

import os
from robot.api import ExecutionResult
from robot.result.executionresult import CombinedResult
from robot.result.testsuite import TestSuite
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

    def visit_message(self, msg):
        if msg.html and "<img src=\"selenium-screenshot" in msg.message:
            item_p = msg.parent
            while not isinstance(item_p, TestSuite):
                item_p = item_p.parent

            suites_names = item_p.longname.split('.')
            top_name = os.getenv('TESTS_TOP_NAME', '')
            if top_name:
                suites_names[0] = top_name
            prefix = '.'.join(suites_names)
            msg.message = msg.message.replace('selenium-screenshot',
                                              prefix + '-selenium-screenshot')


class ResultsCombiner(CombinedResult):

    def add_result(self, other):
        for suite in other.suite.suites:
            self.suite.suites.append(suite)
        self.errors.add(other.errors)


def group_by_root(results):
    groups = {}
    for src in results:
        res = ExecutionResult(src)
        groups[res.suite.name] = groups.get(res.suite.name, []) + [res]
    return groups


def merge_groups(results):
    merged = []
    for group in group_by_root(results).values():
        base = group[0]
        merger = ResultMerger(base)
        for out in group:
            merger.merge(out)
        merged.append(base)
    return merged


def merge(*result_files):
    assert len(result_files) > 0
    merged = merge_groups(result_files)
    if len(merged) == 1:
        return merged[0]
    else:
        return ResultsCombiner(merged)
