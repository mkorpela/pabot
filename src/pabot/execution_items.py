from functools import total_ordering
from typing import Dict, List, Optional, Tuple, Union

from robot import __version__ as ROBOT_VERSION
from robot.errors import DataError
from robot.utils import PY2, is_unicode

import re


def create_dependency_tree(items):  
    # type: (List[ExecutionItem]) -> List[List[ExecutionItem]]
    independent_tests = list(filter(lambda item: not item.depends, items))
    dependency_tree = [independent_tests]
    dependent_tests = list(filter(lambda item: item.depends, items))
    unknown_dependent_tests = dependent_tests
    while len(unknown_dependent_tests) > 0:
        run_in_this_stage, run_later = [], []
        for d in unknown_dependent_tests:
            stage_indexes = []
            for i, stage in enumerate(dependency_tree):
                for test in stage:
                    if test.name in d.depends:
                        stage_indexes.append(i)
            # All #DEPENDS test are already run:
            if len(stage_indexes) == len(d.depends):
                run_in_this_stage.append(d)
            else:
                run_later.append(d)
        unknown_dependent_tests = run_later
        if len(run_in_this_stage) == 0:
            text = "There are circular or unmet dependencies using #DEPENDS. Check this/these test(s): " + str(run_later)
            raise DataError(text)
        else:
            dependency_tree.append(run_in_this_stage)
    flattened_dependency_tree = sum(dependency_tree, [])
    if len(flattened_dependency_tree) != len(items):
        raise DataError(
            "Invalid test configuration: Circular or unmet dependencies detected between test suites. Please check your #DEPENDS definitions."
        )
    return dependency_tree


@total_ordering
class ExecutionItem(object):
    isWait = False
    type = None  # type: str
    name = None  # type: str
    sleep = 0  # type: int

    def top_name(self):
        # type: () -> str
        return self.name.split(".")[0]

    def contains(self, other):
        # type: (ExecutionItem) -> bool
        return False

    def difference(self, from_items):
        # type: (List[ExecutionItem]) -> List[ExecutionItem]
        return []

    def line(self):
        # type: () -> str
        return ""

    def set_sleep(self, sleep_time):
        # type: (int) -> None
        self.sleep = sleep_time

    def get_sleep(self):
        # type: () -> int
        return self.sleep

    def modify_options_for_executor(self, options):
        options[self.type] = self.name

    def __eq__(self, other):
        if isinstance(other, ExecutionItem):
            return (self.name, self.type) == (other.name, other.type)
        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return (self.name, self.type) < (other.name, other.type)

    def __hash__(self):
        return hash(self.name) | hash(self.type)

    def __repr__(self):
        return "<" + self.type + ":" + self.name + ">"


class HivedItem(ExecutionItem):
    type = "hived"

    def __init__(self, item, hive):
        self._item = item
        self._hive = hive

    def modify_options_for_executor(self, options):
        self._item.modify_options_for_executor(options)

    @property
    def name(self):
        return self._item.name


class GroupItem(ExecutionItem):
    type = "group"

    def __init__(self):
        self.name = "Group"
        self._items = []
        self._element_type = None

    def add(self, item):
        if item.isWait:
            raise DataError("[EXCEPTION] Ordering : Group can not contain #WAIT")
        if self._element_type and self._element_type != item.type:
            raise DataError(
                "[EXCEPTION] Ordering : Group can contain only test or suite elements. Not bouth"
            )
        if len(self._items) > 0:
            self.name += "_"
        if self.get_sleep() < item.get_sleep():
            self.set_sleep(item.get_sleep())
        self.name += item.name
        self._element_type = item.type
        self._items.append(item)
    
    def change_items_order_by_depends(self):
        ordered_name = "Group"
        dependency_tree = create_dependency_tree(self._items)
        ordered = [item for sublist in dependency_tree for item in sublist]
        for item in ordered:
            ordered_name += f"_{item.name}"
        self.name = ordered_name
        self._items = ordered

    def modify_options_for_executor(self, options):
        # Since a GroupItem contains either tests or suites, options are cleared
        # and only the Group's content is used to avoid duplicate execution.
        options['suite'] = []
        options['test'] = []
        for item in self._items:
            if item.type not in options:
                options[item.type] = []
            opts = {}
            item.modify_options_for_executor(opts)
            options[item.type].append(opts[item.type])


class RunnableItem(ExecutionItem):
    pass

    depends = None  # type: List[str]
    depends_keyword = "#DEPENDS"

    def _split_dependencies(self, line_name, depends_indexes):
        depends_lst = [] if len(depends_indexes) < 2 else [line_name[i + len(self.depends_keyword) : j].strip() for i, j in zip(depends_indexes, depends_indexes[1:])]
        depends_lst.append(line_name[depends_indexes[-1] + len(self.depends_keyword) : ].strip())
        return depends_lst

    def _merge_dependencies(self, line_start):
        output_line = line_start
        for d in self.depends:
            output_line = output_line + " " + self.depends_keyword + " " + d
        return output_line

    def set_name_and_depends(self, name):
        line_name = name.encode("utf-8") if PY2 and is_unicode(name) else name
        depends_indexes = [d.start() for d in re.finditer(self.depends_keyword, line_name)]
        self.name = (
            line_name
            if len(depends_indexes) == 0
            else line_name[0:depends_indexes[0]].strip()
        )
        assert len(self.name) != 0, f"Suite or test name cannot be empty and then contain #DEPENDS like: {name}"
        self.depends = (
            self._split_dependencies(line_name, depends_indexes)
            if len(depends_indexes) != 0
            else None
        )

    def line(self):
        # type: () -> str
        line_without_depends = "--" + self.type + " " + self.name
        return (
            self._merge_dependencies(line_without_depends)
            if self.depends
            else line_without_depends
        )


class SuiteItem(RunnableItem):
    type = "suite"

    def __init__(self, name, tests=None, suites=None, dynamictests=None):
        # type: (str, Optional[List[str]], Optional[List[str]], Optional[List[str]]) -> None
        assert (PY2 and isinstance(name, basestring)) or isinstance(name, str)
        self.set_name_and_depends(name)
        testslist = [
            TestItem(t) for t in tests or []
        ]  # type: List[Union[TestItem, DynamicTestItem]]
        dynamictestslist = [
            DynamicTestItem(t, self.name) for t in dynamictests or []
        ]  # type: List[Union[TestItem, DynamicTestItem]]
        self.tests = testslist + dynamictestslist
        self.suites = [SuiteItem(s) for s in suites or []]

    def difference(self, from_items):
        # type: (List[ExecutionItem]) -> List[ExecutionItem]
        if self.tests:
            return [t for t in self.tests if t not in from_items]
        if self.suites:
            return [s for s in self.suites if s not in from_items]
        return []

    def contains(self, other):
        # type: (ExecutionItem) -> bool
        if self == other:
            return True
        return other.name.startswith(self.name + ".")

    def __eq__(self, other):
        if not isinstance(other, SuiteItem):
            return False
        if self.name == other.name:
            return True
        if other.name.endswith("." + self.name):
            return True
        if self.name.endswith("." + other.name):
            return True
        return False

    def __hash__(self):
        return RunnableItem.__hash__(self)

    def tags(self):
        # TODO Make this happen
        return []


class TestItem(RunnableItem):
    type = "test"

    def __init__(self, name):
        # type: (str) -> None
        self.set_name_and_depends(name)

    if ROBOT_VERSION >= "3.1":

        def modify_options_for_executor(self, options):
            if "rerunfailed" in options:
                del options["rerunfailed"]
            if "rerunfailedsuites" in options:
                del options["rerunfailedsuites"]
            name = self.name
            for char in ["[", "?", "*"]:
                name = name.replace(char, "[" + char + "]")
            options[self.type] = name

    else:

        def modify_options_for_executor(self, options):
            if "rerunfailed" in options:
                del options["rerunfailed"]
            if "rerunfailedsuites" in options:
                del options["rerunfailedsuites"]

    def difference(self, from_items):
        # type: (List[ExecutionItem]) -> List[ExecutionItem]
        return []

    def contains(self, other):
        # type: (ExecutionItem) -> bool
        return self == other

    def tags(self):
        # TODO Make this happen
        return []


class DynamicSuiteItem(SuiteItem):
    type = "dynamicsuite"

    def __init__(self, name, variables):
        SuiteItem.__init__(self, name)
        self._variables = variables

    def modify_options_for_executor(self, options):
        variables = options.get("variable", [])[:]
        variables.extend(self._variables)
        options["variable"] = variables
        options["suite"] = self.name


class DynamicTestItem(ExecutionItem):
    type = "dynamictest"

    def __init__(self, name, suite):
        # type: (str, str) -> None
        self.name = name.encode("utf-8") if PY2 and is_unicode(name) else name
        self.suite = suite  # type:str

    def line(self):
        return "DYNAMICTEST %s :: %s" % (self.suite, self.name)

    def modify_options_for_executor(self, options):
        options["suite"] = self.suite
        variables = options.get("variable", [])[:]
        variables.append("DYNAMICTEST:" + self.name)
        options["variable"] = variables

    def difference(self, from_items):
        return []

    def contains(self, other):
        return self == other

    def tags(self):
        # TODO Make this happen
        return []


class WaitItem(ExecutionItem):
    type = "wait"
    isWait = True

    def __init__(self):
        self.name = "#WAIT"

    def line(self):
        return self.name


class SleepItem(ExecutionItem):
    type = "sleep"

    def __init__(self, time):
        try:
            assert 3600 >= int(time) >= 0  # 1 h max.
            self.name = time
            self.sleep = int(time)
        except ValueError:
            raise ValueError("#SLEEP value %s is not integer" % time)
        except AssertionError:
            raise ValueError("#SLEEP value %s is not in between 0 and 3600" % time)

    def line(self):
        return "#SLEEP " + self.name


class GroupStartItem(ExecutionItem):
    type = "group"

    def __init__(self):
        self.name = "#START"

    def line(self):
        return "{"


class GroupEndItem(ExecutionItem):
    type = "group"

    def __init__(self):
        self.name = "#END"

    def line(self):
        return "}"


class IncludeItem(ExecutionItem):
    type = "include"

    def __init__(self, tag):
        self.name = tag

    def line(self):
        return "--include " + self.name

    def contains(self, other):
        return self.name in other.tags()

    def tags(self):
        return [self.name]


class SuiteItems(ExecutionItem):
    type = "suite"

    def __init__(self, suites):
        self.suites = suites
        self.name = " ".join([suite.name for suite in suites])

    def modify_options_for_executor(self, options):
        options["suite"] = [suite.name for suite in self.suites]
