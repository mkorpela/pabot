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

import os
import re

from robot import __version__ as ROBOT_VERSION
from robot.api import ExecutionResult
from robot.conf import RobotSettings
from robot.errors import DataError
from robot.result.executionresult import CombinedResult

try:
    from robot.result import TestSuite
except ImportError:
    from robot.result.testsuite import TestSuite

from robot.model import SuiteVisitor


class ResultMerger(SuiteVisitor):
    def __init__(self, result, tests_root_name, out_dir, copied_artifacts, legacy_output):
        self.root = result.suite
        self.errors = result.errors
        self.current = None
        self._skip_until = None
        self._tests_root_name = tests_root_name
        self._prefix = ""
        self._out_dir = out_dir
        self.legacy_output = legacy_output

        self._patterns = []
        regexp_template = (
            r'(src|href)="(.*?[\\\/]+)?({})"'  # https://regex101.com/r/sBwbgN/5
        )
        for artifact in copied_artifacts:
            pattern = regexp_template.format(re.escape(artifact))
            self._patterns.append(re.compile(pattern))

    def merge(self, merged):
        try:
            self._set_prefix(merged.source)
            merged.suite.visit(self)
            self.root.metadata.update(merged.suite.metadata)
            if self.errors != merged.errors:
                self.errors.add(merged.errors)
        except:
            print("Error while merging result %s" % merged.source)
            raise

    def _set_prefix(self, source):
        self._prefix = prefix(source)

    def start_suite(self, suite):
        if self._skip_until and self._skip_until != suite:
            return
        if not self.current:
            self.current = self._find_root(suite)
            assert self.current
            if self.current is not suite:
                self._append_keywords(suite)
        else:
            next = self._find(self.current.suites, suite)
            if next is None:
                self.current.suites.append(suite)
                suite.parent = self.current
                self._skip_until = suite
            else:
                self.current = next
                if self.current is not suite:
                    self._append_keywords(suite)

    if ROBOT_VERSION < "4.0" or ROBOT_VERSION == "4.0b1":

        def _append_keywords(self, suite):
            for keyword in suite.keywords:
                self.current.keywords.append(keyword)

    else:

        def _append_keywords(self, suite):
            for keyword in suite.setup.body:
                self.current.setup.body.append(keyword)
            for keyword in suite.teardown.body:
                self.current.teardown.body.append(keyword)

    def _find_root(self, suite):
        if self.root.name != suite.name:
            raise ValueError(
                'self.root.name "%s" != suite.name "%s"' % (self.root.name, suite.name)
            )
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

    if ROBOT_VERSION <= "3.0" or ROBOT_VERSION >= "4.0":

        def clean_pabotlib_waiting_keywords(self, suite):
            pass

    else:

        def clean_pabotlib_waiting_keywords(self, suite):
            for index, keyword in reversed(list(enumerate(suite.keywords))):
                if (
                    keyword.libname == "pabot.PabotLib"
                    and keyword.kwname.startswith("Run")
                    and len(keyword.keywords) == 0
                ):
                    suite.keywords.pop(index)

    def merge_missing_tests(self, suite):
        cur = self.current
        for test in suite.tests:
            if not any(t.longname == test.longname for t in cur.tests):
                test.parent = cur
                cur.tests.append(test)

    def merge_time(self, suite):
        cur = self.current
        if ROBOT_VERSION >= "7.0" and not self.legacy_output:
            cur.elapsed_time = None
        cur.endtime = max([cur.endtime, suite.endtime])
        cur.starttime = min([cur.starttime, suite.starttime])

    def visit_message(self, msg):
        if not msg.html:  # no html -> no link -> no update needed
            return
        # fix links that go outside of result directory
        msg.message = msg.message.replace('src="../../', 'src="')
        msg.message = msg.message.replace('href="../../', 'href="')
        if not self._patterns:  # don't update links if no artifacts were copied
            return
        if not (
            "src=" in msg.message or "href=" in msg.message
        ):  # quick check before start search with complex regex
            return

        for pattern in self._patterns:
            all_matches = re.finditer(pattern, msg.message)
            offset = 0
            prefix_str = self._prefix + "-"
            for match in all_matches:
                filename_start = (
                    match.start(3) + offset
                )  # group 3 of regexp is the file name
                msg.message = (
                    msg.message[:filename_start]
                    + prefix_str
                    + msg.message[filename_start:]
                )
                offset += len(
                    prefix_str
                )  # the string has been changed but not the original match positions


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
        if ROBOT_VERSION < "4.0":
            res.suite.set_criticality(critical_tags, non_critical_tags)
        groups[res.suite.name] = groups.get(res.suite.name, []) + [res]
    return groups


def merge_groups(
    results,
    critical_tags,
    non_critical_tags,
    tests_root_name,
    invalid_xml_callback,
    out_dir,
    copied_artifacts,
    legacy_output
):
    merged = []
    for group in group_by_root(
        results, critical_tags, non_critical_tags, invalid_xml_callback
    ).values():
        base = group[0]
        merger = ResultMerger(base, tests_root_name, out_dir, copied_artifacts, legacy_output)
        for out in group:
            merger.merge(out)
        merged.append(base)
    return merged


def merge(
    result_files,
    rebot_options,
    tests_root_name,
    copied_artifacts,
    invalid_xml_callback=None,
):
    assert len(result_files) > 0
    if invalid_xml_callback is None:
        invalid_xml_callback = lambda: 0
    settings = RobotSettings(rebot_options).get_rebot_settings()
    critical_tags = []
    non_critical_tags = []
    if ROBOT_VERSION < "4.0":
        critical_tags = settings.critical_tags
        non_critical_tags = settings.non_critical_tags
    merged = merge_groups(
        result_files,
        critical_tags,
        non_critical_tags,
        tests_root_name,
        invalid_xml_callback,
        settings.output_directory,
        copied_artifacts,
        rebot_options.get('legacyoutput')
    )
    if len(merged) == 1:
        if not merged[0].suite.doc:
            merged[
                0
            ].suite.doc = "[https://pabot.org/?ref=log|Pabot] result from %d executions." % len(
                result_files
            )
        return merged[0]
    else:
        return ResultsCombiner(merged)
