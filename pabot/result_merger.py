#  Copyright 2014->future! Mikko Korpela
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
from __future__ import absolute_import, print_function

import os, re

from robot import __version__ as ROBOT_VERSION
from robot.api import ExecutionResult
from robot.errors import DataError
from robot.conf import RebotSettings
from robot.result.executionresult import CombinedResult

try:
    from robot.result import TestSuite
except ImportError:
    from robot.result.testsuite import TestSuite

from robot.model import SuiteVisitor


class ResultMerger(SuiteVisitor):

    def __init__(self, result, tests_root_name):
        self.root = result.suite
        self.errors = result.errors
        self.current = None
        self._skip_until = None
        self._tests_root_name = tests_root_name
        self._prefix = ""

    def merge(self, merged):
        try:
            self._set_prefix(merged.source)
            merged.suite.visit(self)
            if self.errors!=merged.errors: self.errors.add(merged.errors)
        except:
            print('Error while merging result %s' % merged.source)
            raise

    def _set_prefix(self, source):
        self._prefix = prefix(source)

    def start_suite(self, suite):
        if self._skip_until and self._skip_until != suite:
            return
        if not self.current:
            self.current = self._find_root(suite)
            assert(self.current)
            if self.current is not suite:
                for keyword in suite.keywords:
                    self.current.keywords.append(keyword)
        else:
            next = self._find(self.current.suites, suite)
            if next is None:
                self.current.suites.append(suite)
                suite.parent = self.current
                self._skip_until = suite
            else:
                self.current = next
                if self.current is not suite:
                    for keyword in suite.keywords:
                        self.current.keywords.append(keyword)

    def _find_root(self, suite):
        if self.root.name != suite.name:
            raise ValueError('self.root.name "%s" != suite.name "%s"' %
                             (self.root.name, suite.name))
        return self.root

    def _find(self, items, suite):
        name = suite.name
        source = suite.source
        for item in items:
            if item.name == name and item.source == source:
                return item
        return None

    def end_suite(self, suite):
        if self._skip_until and self._skip_until != suite:
            return
        if self._skip_until == suite:
            self._skip_until = None
            return
        self.merge_missing_tests(suite)
        self.merge_time(suite)
        self.clean_pabotlib_waiting_keywords(self.current)
        self.current = self.current.parent

    if ROBOT_VERSION <= '3.0':

        def clean_pabotlib_waiting_keywords(self, suite):
            pass

    else:

        def clean_pabotlib_waiting_keywords(self, suite):
            for index, keyword in reversed(list(enumerate(suite.keywords))):
                if (keyword.libname == "pabot.PabotLib" and
                    keyword.kwname.startswith("Run") and
                    len(keyword.keywords) == 0):
                    suite.keywords.pop(index)

    def merge_missing_tests(self, suite):
        cur = self.current
        for test in suite.tests:
            if not any(t.longname == test.longname for t in cur.tests):
                test.parent = cur
                cur.tests.append(test)

    def merge_time(self, suite):
        cur = self.current
        cur.endtime = max([cur.endtime, suite.endtime])
        cur.starttime = min([cur.starttime, suite.starttime])

    def visit_message(self, msg):
        if msg.html and re.search(r'src="([^"]+\.png)"', msg.message):
            parent = msg.parent
            while not isinstance(parent, TestSuite):
                parent = parent.parent
            suites_names = parent.longname.split('.')
            if self._tests_root_name:
                suites_names[0] = self._tests_root_name
            msg.message = re.sub(r'"([^"]+\.png)"',
                                 r'"%s-\1"' % self._prefix, msg.message)


class ResultsCombiner(CombinedResult):

    def add_result(self, other):
        for suite in other.suite.suites:
            self.suite.suites.append(suite)
        self.errors.add(other.errors)


def prefix(source):
    try:
        return os.path.split(os.path.dirname(source))[1]
    except:
        return ""

def group_by_root(results, critical_tags, non_critical_tags, invalid_xml_callback):
    groups = {}
    for src in results:
        try:
            res = ExecutionResult(src)
        except DataError as err:
            print(err.message)
            print("Skipping '%s' from final result" % src)
            invalid_xml_callback()
            continue
        res.suite.set_criticality(critical_tags, non_critical_tags)
        groups[res.suite.name] = groups.get(res.suite.name, []) + [res]
    return groups


def merge_groups(results, critical_tags, non_critical_tags, tests_root_name, invalid_xml_callback):
    merged = []
    for group in group_by_root(results, critical_tags,
                               non_critical_tags, invalid_xml_callback).values():
        base = group[0]
        merger = ResultMerger(base, tests_root_name)
        for out in group:
            merger.merge(out)
        merged.append(base)
    return merged


def merge(result_files, rebot_options, tests_root_name, invalid_xml_callback=None):
    assert(len(result_files) > 0)
    if invalid_xml_callback is None:
        invalid_xml_callback = lambda:0
    settings = RebotSettings(rebot_options)
    merged = merge_groups(result_files, settings.critical_tags,
                          settings.non_critical_tags, tests_root_name,
                          invalid_xml_callback)
    if len(merged) == 1:
        if not merged[0].suite.doc:
            merged[0].suite.doc = '[https://pabot.org/?ref=log|Pabot] result from %d executions.' % len(result_files)
        return merged[0]
    else:
        return ResultsCombiner(merged)
