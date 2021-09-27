#!/usr/bin/env python

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
#  partly based on work by Nokia Solutions and Networks Oyj
"""A parallel executor for Robot Framework test cases.
Version 2.0.1

Supports all Robot Framework command line options and also following
options (these must be before normal RF options):

--verbose
  more output

--command [ACTUAL COMMANDS TO START ROBOT EXECUTOR] --end-command
  RF script for situations where pybot is not used directly

--processes [NUMBER OF PROCESSES]
  How many parallel executors to use (default max of 2 and cpu count)

--testlevelsplit
  Split execution on test level instead of default suite level.
  If .pabotsuitenames contains both tests and suites then this
  will only affect new suites and split only them.
  Leaving this flag out when both suites and tests in
  .pabotsuitenames file will also only affect new suites and
  add them as suite files.

--resourcefile [FILEPATH]
  Indicator for a file that can contain shared variables for
  distributing resources.

--pabotlib
  Start PabotLib remote server. This enables locking and resource
  distribution between parallel test executions.

--pabotlibhost [HOSTNAME]
  Host name of the PabotLib remote server (default is 127.0.0.1)

--pabotlibport [PORT]
  Port number of the PabotLib remote server (default is 8270)

--ordering [FILE PATH]
  Optionally give execution order from a file.

--suitesfrom [FILEPATH TO OUTPUTXML]
  Optionally read suites from output.xml file. Failed suites will run
  first and longer running ones will be executed before shorter ones.

--argumentfile[INTEGER] [FILEPATH]
  Run same suite with multiple argumentfile options.
  For example "--argumentfile1 arg1.txt --argumentfile2 arg2.txt".

Copyright 2019 Mikko Korpela - Apache 2 License
"""

from __future__ import absolute_import, print_function

import datetime
import hashlib
import os
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import namedtuple
from contextlib import closing
from glob import glob
from io import BytesIO, StringIO
from multiprocessing.pool import ThreadPool

from robot import __version__ as ROBOT_VERSION
from robot import rebot
from robot.api import ExecutionResult
from robot.conf import RobotSettings
from robot.errors import DataError, Information
from robot.libraries.Remote import Remote
from robot.model import ModelModifier
from robot.result.visitor import ResultVisitor
from robot.run import USAGE
from robot.running import TestSuiteBuilder
from robot.utils import PY2, SYSTEM_ENCODING, ArgumentParser, is_unicode

from . import pabotlib
from .arguments import parse_args, parse_execution_item_line
from .clientwrapper import make_order
from .execution_items import (
    DynamicSuiteItem,
    ExecutionItem,
    GroupEndItem,
    GroupItem,
    GroupStartItem,
    HivedItem,
    SuiteItem,
    SuiteItems,
    TestItem,
)
from .result_merger import merge

try:
    import queue  # type: ignore
except ImportError:
    import Queue as queue  # type: ignore

try:
    from shlex import quote  # type: ignore
except ImportError:
    from pipes import quote  # type: ignore

from typing import IO, Any, Dict, List, Optional, Tuple, Union

CTRL_C_PRESSED = False
MESSAGE_QUEUE = queue.Queue()
EXECUTION_POOL_IDS = []  # type: List[int]
EXECUTION_POOL_ID_LOCK = threading.Lock()
POPEN_LOCK = threading.Lock()
_PABOTLIBURI = "127.0.0.1:8270"
_PABOTLIBPROCESS = None  # type: Optional[subprocess.Popen]
_BOURNELIKE_SHELL_BAD_CHARS_WITHOUT_DQUOTE = (
    "!#$^&*?[(){}<>~;'`\\|= \t\n"  # does not contain '"'
)
_BAD_CHARS_SET = set(_BOURNELIKE_SHELL_BAD_CHARS_WITHOUT_DQUOTE)
_NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0
_ABNORMAL_EXIT_HAPPENED = False

_COMPLETED_LOCK = threading.Lock()
_NOT_COMPLETED_INDEXES = []  # type: List[int]

_ROBOT_EXTENSIONS = [
    ".html",
    ".htm",
    ".xhtml",
    ".tsv",
    ".rst",
    ".rest",
    ".txt",
    ".robot",
]
_ALL_ELAPSED = []  # type: List[Union[int, float]]


class Color:
    SUPPORTED_OSES = ["posix"]

    GREEN = "\033[92m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    YELLOW = "\033[93m"


def _mapOptionalQuote(command_args):
    # type: (List[str]) -> List[str]
    if os.name == "posix":
        return [quote(arg) for arg in command_args]
    return [
        arg if set(arg).isdisjoint(_BAD_CHARS_SET) else '"%s"' % arg
        for arg in command_args
    ]


def execute_and_wait_with(item):
    # type: ('QueueItem') -> None
    global CTRL_C_PRESSED, _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    is_last = _NUMBER_OF_ITEMS_TO_BE_EXECUTED == 1
    _NUMBER_OF_ITEMS_TO_BE_EXECUTED -= 1
    if CTRL_C_PRESSED:
        # Keyboard interrupt has happened!
        return
    time.sleep(0)
    try:
        datasources = [
            d.encode("utf-8") if PY2 and is_unicode(d) else d for d in item.datasources
        ]
        caller_id = uuid.uuid4().hex
        name = item.display_name
        outs_dir = os.path.join(item.outs_dir, item.argfile_index, str(item.index))
        os.makedirs(outs_dir)
        cmd = _create_command_for_execution(
            caller_id, datasources, is_last, item, outs_dir
        )
        if item.hive:
            _hived_execute(
                item.hive,
                cmd,
                outs_dir,
                name,
                item.verbose,
                _make_id(),
                caller_id,
                item.index,
            )
        else:
            _try_execute_and_wait(
                cmd,
                outs_dir,
                name,
                item.verbose,
                _make_id(),
                caller_id,
                item.index,
                item.execution_item.type != "test",
            )
        outputxml_preprocessing(
            item.options, outs_dir, name, item.verbose, _make_id(), caller_id
        )
    except:
        _write(traceback.format_exc())


def _create_command_for_execution(caller_id, datasources, is_last, item, outs_dir):
    options = item.options.copy()
    if item.command == ['robot'] and not options["listener"]:
        options["listener"] = ["RobotStackTracer"]
    cmd = (
        item.command
        + _options_for_custom_executor(
            options,
            outs_dir,
            item.execution_item,
            item.argfile,
            caller_id,
            is_last,
            item.index,
            item.last_level,
            item.processes,
        )
        + datasources
    )
    return _mapOptionalQuote(cmd)


def _pabotlib_in_use():
    return _PABOTLIBPROCESS or _PABOTLIBURI != "127.0.0.1:8270"


def _hived_execute(
    hive, cmd, outs_dir, item_name, verbose, pool_id, caller_id, my_index=-1
):
    plib = None
    if _pabotlib_in_use():
        plib = Remote(_PABOTLIBURI)
    try:
        make_order(hive, " ".join(cmd), outs_dir)
    except:
        _write(traceback.format_exc())
    if plib:
        _increase_completed(plib, my_index)


def _try_execute_and_wait(
    cmd,
    outs_dir,
    item_name,
    verbose,
    pool_id,
    caller_id,
    my_index=-1,
    show_stdout_on_failure=False,
):
    # type: (List[str], str, str, bool, int, str, int, bool) -> None
    plib = None
    is_ignored = False
    if _pabotlib_in_use():
        plib = Remote(_PABOTLIBURI)
    try:
        with open(os.path.join(outs_dir, cmd[0] + "_stdout.out"), "w") as stdout:
            with open(os.path.join(outs_dir, cmd[0] + "_stderr.out"), "w") as stderr:
                process, (rc, elapsed) = _run(
                    cmd, stderr, stdout, item_name, verbose, pool_id, my_index
                )
    except:
        _write(traceback.format_exc())
    if plib:
        _increase_completed(plib, my_index)
        is_ignored = _is_ignored(plib, caller_id)
        if is_ignored and os.path.isdir(outs_dir):
            shutil.rmtree(outs_dir)
    # Thread-safe list append
    _ALL_ELAPSED.append(elapsed)
    _result_to_stdout(
        elapsed,
        is_ignored,
        item_name,
        my_index,
        pool_id,
        process,
        rc,
        stderr,
        stdout,
        verbose,
        show_stdout_on_failure,
    )


def _result_to_stdout(
    elapsed,
    is_ignored,
    item_name,
    my_index,
    pool_id,
    process,
    rc,
    stderr,
    stdout,
    verbose,
    show_stdout_on_failure,
):
    if is_ignored:
        _write_with_id(
            process,
            pool_id,
            my_index,
            _execution_ignored_message(item_name, stdout, stderr, elapsed, verbose),
        )
    elif rc != 0:
        _write_with_id(
            process,
            pool_id,
            my_index,
            _execution_failed_message(
                item_name, stdout, stderr, rc, verbose or show_stdout_on_failure
            ),
            Color.RED,
        )
    else:
        _write_with_id(
            process,
            pool_id,
            my_index,
            _execution_passed_message(item_name, stdout, stderr, elapsed, verbose),
            Color.GREEN,
        )


def _is_ignored(plib, caller_id):  # type: (Remote, str) -> bool
    return plib.run_keyword("is_ignored_execution", [caller_id], {})


# optionally invoke rebot for output.xml preprocessing to get --RemoveKeywords
# and --flattenkeywords applied => result: much smaller output.xml files + faster merging + avoid MemoryErrors
def outputxml_preprocessing(options, outs_dir, item_name, verbose, pool_id, caller_id):
    # type: (Dict[str, Any], str, str, bool, int, str) -> None
    try:
        remove_keywords = options["removekeywords"]
        flatten_keywords = options["flattenkeywords"]
        if not remove_keywords and not flatten_keywords:
            # => no preprocessing needed if no removekeywords or flattenkeywords present
            return
        remove_keywords_args = []  # type: List[str]
        flatten_keywords_args = []  # type: List[str]
        for k in remove_keywords:
            remove_keywords_args += ["--removekeywords", k]
        for k in flatten_keywords:
            flatten_keywords_args += ["--flattenkeywords", k]
        outputxmlfile = os.path.join(outs_dir, "output.xml")
        oldsize = os.path.getsize(outputxmlfile)
        cmd = (
            [
                "rebot",
                "--log",
                "NONE",
                "--report",
                "NONE",
                "--xunit",
                "NONE",
                "--consolecolors",
                "off",
                "--NoStatusRC",
            ]
            + remove_keywords_args
            + flatten_keywords_args
            + ["--output", outputxmlfile, outputxmlfile]
        )
        cmd = _mapOptionalQuote(cmd)
        _try_execute_and_wait(
            cmd,
            outs_dir,
            "preprocessing output.xml on " + item_name,
            verbose,
            pool_id,
            caller_id,
        )
        newsize = os.path.getsize(outputxmlfile)
        perc = 100 * newsize / oldsize
        if verbose:
            _write(
                "%s [main] [%s] Filesize reduced from %s to %s (%0.2f%%) for file %s"
                % (
                    datetime.datetime.now(),
                    pool_id,
                    oldsize,
                    newsize,
                    perc,
                    outputxmlfile,
                )
            )
    except:
        print(sys.exc_info())


def _write_with_id(process, pool_id, item_index, message, color=None, timestamp=None):
    timestamp = timestamp or datetime.datetime.now()
    _write(
        "%s [PID:%s] [%s] [ID:%s] %s"
        % (timestamp, process.pid, pool_id, item_index, message),
        color,
    )


def _make_id():  # type: () -> int
    global EXECUTION_POOL_IDS, EXECUTION_POOL_ID_LOCK
    thread_id = threading.current_thread().ident
    assert thread_id is not None
    with EXECUTION_POOL_ID_LOCK:
        if thread_id not in EXECUTION_POOL_IDS:
            EXECUTION_POOL_IDS += [thread_id]
        return EXECUTION_POOL_IDS.index(thread_id)


def _increase_completed(plib, my_index):
    # type: (Remote, int) -> None
    global _COMPLETED_LOCK, _NOT_COMPLETED_INDEXES
    with _COMPLETED_LOCK:
        if my_index not in _NOT_COMPLETED_INDEXES:
            return
        _NOT_COMPLETED_INDEXES.remove(my_index)
        if _NOT_COMPLETED_INDEXES:
            plib.run_keyword(
                "set_parallel_value_for_key",
                [
                    pabotlib.PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE,
                    _NOT_COMPLETED_INDEXES[0],
                ],
                {},
            )
        if len(_NOT_COMPLETED_INDEXES) == 1:
            plib.run_keyword(
                "set_parallel_value_for_key", ["pabot_only_last_executing", 1], {}
            )


def _run(command, stderr, stdout, item_name, verbose, pool_id, item_index):
    # type: (List[str], IO[Any], IO[Any], str, bool, int, int) -> Tuple[Union[subprocess.Popen[bytes], subprocess.Popen], Tuple[int, float]]
    timestamp = datetime.datetime.now()
    cmd = " ".join(command)
    if PY2:
        cmd = cmd.decode("utf-8").encode(SYSTEM_ENCODING)
    # avoid hitting https://bugs.python.org/issue10394
    with POPEN_LOCK:
        process = subprocess.Popen(cmd, shell=True, stderr=stderr, stdout=stdout)
    if verbose:
        _write_with_id(
            process,
            pool_id,
            item_index,
            "EXECUTING PARALLEL %s with command:\n%s" % (item_name, cmd),
            timestamp=timestamp,
        )
    else:
        _write_with_id(
            process,
            pool_id,
            item_index,
            "EXECUTING %s" % item_name,
            timestamp=timestamp,
        )
    return process, _wait_for_return_code(process, item_name, pool_id, item_index)


def _wait_for_return_code(process, item_name, pool_id, item_index):
    rc = None
    elapsed = 0
    ping_time = ping_interval = 150
    while rc is None:
        rc = process.poll()
        time.sleep(0.1)
        elapsed += 1
        if elapsed == ping_time:
            ping_interval += 50
            ping_time += ping_interval
            _write_with_id(
                process,
                pool_id,
                item_index,
                "still running %s after %s seconds" % (item_name, elapsed / 10.0),
            )
    return rc, elapsed / 10.0


def _read_file(file_handle):
    try:
        with open(file_handle.name, "r") as content_file:
            content = content_file.read()
        return content
    except:
        return "Unable to read file %s" % file_handle


def _execution_failed_message(suite_name, stdout, stderr, rc, verbose):
    if not verbose:
        return "FAILED %s" % suite_name
    return "Execution failed in %s with %d failing test(s)\n%s\n%s" % (
        suite_name,
        rc,
        _read_file(stdout),
        _read_file(stderr),
    )


def _execution_passed_message(suite_name, stdout, stderr, elapsed, verbose):
    if not verbose:
        return "PASSED %s in %s seconds" % (suite_name, elapsed)
    return "PASSED %s in %s seconds\n%s\n%s" % (
        suite_name,
        elapsed,
        _read_file(stdout),
        _read_file(stderr),
    )


def _execution_ignored_message(suite_name, stdout, stderr, elapsed, verbose):
    if not verbose:
        return "IGNORED %s" % suite_name
    return "IGNORED %s in %s seconds\n%s\n%s" % (
        suite_name,
        elapsed,
        _read_file(stdout),
        _read_file(stderr),
    )


def _options_for_custom_executor(*args):
    # type: (Any) -> List[str]
    return _options_to_cli_arguments(_options_for_executor(*args))


def _options_for_executor(
    options,
    outs_dir,
    execution_item,
    argfile,
    caller_id,
    is_last,
    queueIndex,
    last_level,
    processes,
):
    options = options.copy()
    options["log"] = "NONE"
    options["report"] = "NONE"
    options["xunit"] = "NONE"
    options["test"] = options.get("test", [])[:]
    options["suite"] = options.get("suite", [])[:]
    execution_item.modify_options_for_executor(options)
    options["outputdir"] = "%OUTPUTDIR%" if execution_item.type == "hived" else outs_dir
    options["variable"] = options.get("variable", [])[:]
    options["variable"].append("CALLER_ID:%s" % caller_id)
    pabotLibURIVar = "PABOTLIBURI:%s" % _PABOTLIBURI
    # Prevent multiple appending of PABOTLIBURI variable setting
    if pabotLibURIVar not in options["variable"]:
        options["variable"].append(pabotLibURIVar)
    pabotExecutionPoolId = "PABOTEXECUTIONPOOLID:%d" % _make_id()
    if pabotExecutionPoolId not in options["variable"]:
        options["variable"].append(pabotExecutionPoolId)
    pabotIsLast = "PABOTISLASTEXECUTIONINPOOL:%s" % ("1" if is_last else "0")
    if pabotIsLast not in options["variable"]:
        options["variable"].append(pabotIsLast)
    pabotProcesses = "PABOTNUMBEROFPROCESSES:%s" % str(processes)
    if pabotProcesses not in options["variable"]:
        options["variable"].append(pabotProcesses)
    pabotIndex = pabotlib.PABOT_QUEUE_INDEX + ":" + str(queueIndex)
    if pabotIndex not in options["variable"]:
        options["variable"].append(pabotIndex)
    if last_level is not None:
        pabotLastLevel = pabotlib.PABOT_LAST_LEVEL + ":" + str(last_level)
        if pabotLastLevel not in options["variable"]:
            options["variable"].append(pabotLastLevel)
    if argfile:
        _modify_options_for_argfile_use(argfile, options, execution_item.top_name())
        options["argumentfile"] = argfile
    return _set_terminal_coloring_options(options)


def _modify_options_for_argfile_use(argfile, options, root_name):
    argfile_opts, _ = ArgumentParser(
        USAGE,
        auto_pythonpath=False,
        auto_argumentfile=True,
        env_options="ROBOT_OPTIONS",
    ).parse_args(["--argumentfile", argfile])
    old_name = options.get("name", root_name)
    if argfile_opts["name"]:
        new_name = argfile_opts["name"]
        _replace_base_name(new_name, old_name, options, "suite")
        if not options["suite"]:
            _replace_base_name(new_name, old_name, options, "test")
        if "name" in options:
            del options["name"]


def _replace_base_name(new_name, old_name, options, key):
    if isinstance(options.get(key, None), str):
        options[key] = new_name + options[key][len(old_name) :]
    elif key in options:
        options[key] = [new_name + s[len(old_name) :] for s in options.get(key, [])]


def _set_terminal_coloring_options(options):
    if ROBOT_VERSION >= "2.9":
        options["consolecolors"] = "off"
        options["consolemarkers"] = "off"
    else:
        options["monitorcolors"] = "off"
    if ROBOT_VERSION >= "2.8" and ROBOT_VERSION < "2.9":
        options["monitormarkers"] = "off"
    return options


def _options_to_cli_arguments(opts):  # type: (dict) -> List[str]
    res = []  # type: List[str]
    for k, v in opts.items():
        if isinstance(v, str):
            res += ["--" + str(k), str(v)]
        elif PY2 and is_unicode(v):
            res += ["--" + str(k), v.encode("utf-8")]
        elif isinstance(v, bool) and (v is True):
            res += ["--" + str(k)]
        elif isinstance(v, list):
            for value in v:
                if PY2 and is_unicode(value):
                    res += ["--" + str(k), value.encode("utf-8")]
                else:
                    res += ["--" + str(k), str(value)]
    return res


def _group_by_groups(tokens):
    result = []
    group = None
    for token in tokens:
        if isinstance(token, GroupStartItem):
            if group is not None:
                raise DataError(
                    "Ordering: Group can not contain a group. Encoutered '{'"
                )
            group = GroupItem()
            result.append(group)
            continue
        if isinstance(token, GroupEndItem):
            if group is None:
                raise DataError(
                    "Ordering: Group end tag '}' encountered before start '{'"
                )
            group = None
            continue
        if group is not None:
            group.add(token)
        else:
            result.append(token)
    return result


def hash_directory(digest, path):
    if os.path.isfile(path):
        digest.update(_digest(_norm_path(path)))
        get_hash_of_file(path, digest)
        return
    for root, _, files in os.walk(path):
        for name in sorted(files):
            file_path = os.path.join(root, name)
            if os.path.isfile(file_path) and any(
                file_path.endswith(p) for p in _ROBOT_EXTENSIONS
            ):
                # DO NOT ALLOW CHANGE TO FILE LOCATION
                digest.update(_digest(_norm_path(root)))
                # DO THESE IN TWO PHASES BECAUSE SEPARATOR DIFFERS IN DIFFERENT OS
                digest.update(_digest(name))
                get_hash_of_file(file_path, digest)


def _norm_path(path):
    return "/".join(os.path.normpath(path).split(os.path.sep))


def _digest(text):
    text = text.decode("utf-8") if PY2 and not is_unicode(text) else text
    return hashlib.sha1(text.encode("utf-8")).digest()


def get_hash_of_file(filename, digest):
    if not os.path.isfile(filename):
        return
    with open(filename, "rb") as f_obj:
        while True:
            buf = f_obj.read(1024 * 1024)
            if not buf:
                break
            digest.update(buf)


def get_hash_of_dirs(directories):
    digest = hashlib.sha1()
    for directory in directories:
        hash_directory(digest, directory)
    return digest.hexdigest()


IGNORED_OPTIONS = [
    "pythonpath",
    "outputdir",
    "output",
    "log",
    "report",
    "removekeywords",
    "flattenkeywords",
    "tagstatinclude",
    "tagstatexclude",
    "tagstatcombine",
    "critical",
    "noncritical",
    "tagstatlink",
    "metadata",
    "tagdoc",
]


def get_hash_of_command(options, pabot_args):
    digest = hashlib.sha1()
    hopts = dict(options)
    for option in options:
        if option in IGNORED_OPTIONS or options[option] == []:
            del hopts[option]
    if pabot_args.get("testlevelsplit"):
        hopts["testlevelsplit"] = True
    digest.update(repr(sorted(hopts.items())).encode("utf-8"))
    return digest.hexdigest()


Hashes = namedtuple("Hashes", ["dirs", "cmd", "suitesfrom"])


def _suitesfrom_hash(pabot_args):
    if "suitesfrom" in pabot_args:
        digest = hashlib.sha1()
        get_hash_of_file(pabot_args["suitesfrom"], digest)
        return digest.hexdigest()
    else:
        return "no-suites-from-option"


if PY2:

    def _open_pabotsuitenames(mode):
        return open(".pabotsuitenames", mode)


else:

    def _open_pabotsuitenames(mode):
        return open(".pabotsuitenames", mode, encoding="utf-8")


def solve_suite_names(outs_dir, datasources, options, pabot_args):
    h = Hashes(
        dirs=get_hash_of_dirs(datasources),
        cmd=get_hash_of_command(options, pabot_args),
        suitesfrom=_suitesfrom_hash(pabot_args),
    )
    try:
        if not os.path.isfile(".pabotsuitenames"):
            suite_names = generate_suite_names(
                outs_dir, datasources, options, pabot_args
            )
            store_suite_names(h, suite_names)
            return suite_names
        with _open_pabotsuitenames("r") as suitenamesfile:
            lines = [line.strip() for line in suitenamesfile.readlines()]
            corrupted = len(lines) < 5
            file_h = None  # type: Optional[Hashes]
            file_hash = None  # type: Optional[str]
            hash_of_file = None  # type: Optional[str]
            if not corrupted:
                file_h = Hashes(
                    dirs=lines[0][len("datasources:") :],
                    cmd=lines[1][len("commandlineoptions:") :],
                    suitesfrom=lines[2][len("suitesfrom:") :],
                )
                file_hash = lines[3][len("file:") :]
                hash_of_file = _file_hash(lines)
            corrupted = corrupted or any(
                not l.startswith("--suite ")
                and not l.startswith("--test ")
                and l != "#WAIT"
                and l != "{"
                and l != "}"
                for l in lines[4:]
            )
            execution_item_lines = [parse_execution_item_line(l) for l in lines[4:]]
            if corrupted or h != file_h or file_hash != hash_of_file:
                return _regenerate(
                    file_h,
                    h,
                    pabot_args,
                    outs_dir,
                    datasources,
                    options,
                    execution_item_lines,
                )
        return execution_item_lines
    except IOError:
        return _levelsplit(
            generate_suite_names_with_builder(outs_dir, datasources, options),
            pabot_args,
        )


def _levelsplit(
    suites, pabot_args
):  # type: (List[SuiteItem], Dict[str, str]) -> List[ExecutionItem]
    if pabot_args.get("testlevelsplit"):
        tests = []  # type: List[ExecutionItem]
        for s in suites:
            tests.extend(s.tests)
        return tests
    return list(suites)


def _group_by_wait(lines):
    suites = [[]]  # type: List[List[ExecutionItem]]
    for suite in lines:
        if not suite.isWait:
            if suite:
                suites[-1].append(suite)
        else:
            suites.append([])
    return suites


def _regenerate(
    file_h, h, pabot_args, outs_dir, datasources, options, lines
):  # type: (Optional[Hashes], Hashes, Dict[str, str], str, List[str], Dict[str, str], List[ExecutionItem]) -> List[ExecutionItem]
    assert all(isinstance(s, ExecutionItem) for s in lines)
    if (
        (file_h is None or file_h.suitesfrom != h.suitesfrom)
        and "suitesfrom" in pabot_args
        and os.path.isfile(pabot_args["suitesfrom"])
    ):
        suites = _suites_from_outputxml(pabot_args["suitesfrom"])
        if file_h is None or file_h.dirs != h.dirs:
            all_suites = generate_suite_names_with_builder(
                outs_dir, datasources, options
            )
        else:
            all_suites = [suite for suite in lines if suite]
        suites = _preserve_order(all_suites, suites)
    else:
        suites = _levelsplit(
            generate_suite_names_with_builder(outs_dir, datasources, options),
            pabot_args,
        )
        suites = _preserve_order(suites, [suite for suite in lines if suite])
    if suites:
        store_suite_names(h, suites)
    assert all(isinstance(s, ExecutionItem) for s in suites)
    return suites


def _contains_suite_and_test(suites):
    return any(isinstance(s, SuiteItem) for s in suites) and any(
        isinstance(t, TestItem) for t in suites
    )


def _preserve_order(new_items, old_items):
    assert all(isinstance(s, ExecutionItem) for s in new_items)
    assert all(isinstance(s, ExecutionItem) for s in old_items)
    old_contains_tests = any(isinstance(t, TestItem) for t in old_items)
    old_contains_suites = any(isinstance(s, SuiteItem) for s in old_items)
    old_items = _fix_items(old_items)
    new_contains_tests = any(isinstance(t, TestItem) for t in new_items)
    if old_contains_tests and old_contains_suites and not new_contains_tests:
        new_items = _split_partially_to_tests(new_items, old_items)
    # TODO: Preserving order when suites => tests OR tests => suites
    preserve, ignorable = _get_preserve_and_ignore(
        new_items, old_items, old_contains_tests and old_contains_suites
    )
    exists_in_old_and_new = [
        s for s in old_items if (s in new_items and s not in ignorable) or s in preserve
    ]
    exists_only_in_new = [
        s for s in new_items if s not in old_items and s not in ignorable
    ]
    return _fix_items(exists_in_old_and_new + exists_only_in_new)


def _fix_items(items):  # type: (List[ExecutionItem]) -> List[ExecutionItem]
    assert all(isinstance(s, ExecutionItem) for s in items)
    to_be_removed = []  # type: List[int]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i].contains(items[j]):
                to_be_removed.append(j)
    items = [item for i, item in enumerate(items) if i not in to_be_removed]
    result = []  # type: List[ExecutionItem]
    to_be_splitted = {}  # type: Dict[int, List[ExecutionItem]]
    for i in range(len(items)):
        if i in to_be_splitted:
            result.extend(items[i].difference(to_be_splitted[i]))
        else:
            result.append(items[i])
        for j in range(i + 1, len(items)):
            if items[j].contains(items[i]):
                if j not in to_be_splitted:
                    to_be_splitted[j] = []
                to_be_splitted[j].append(items[i])
    _remove_double_waits(result)
    _remove_empty_groups(result)
    if result and result[0].isWait:
        result = result[1:]
    if result and result[-1].isWait:
        result = result[:-1]
    return result


def _get_preserve_and_ignore(new_items, old_items, old_contains_suites_and_tests):
    ignorable = []
    preserve = []
    for old_item in old_items:
        for new_item in new_items:
            if (
                old_item.contains(new_item)
                and new_item != old_item
                and (isinstance(new_item, SuiteItem) or old_contains_suites_and_tests)
            ):
                preserve.append(old_item)
                ignorable.append(new_item)
        if (
            old_item.isWait
            or isinstance(old_item, GroupStartItem)
            or isinstance(old_item, GroupEndItem)
        ):
            preserve.append(old_item)
    preserve = [
        new_item
        for new_item in preserve
        if not any([i.contains(new_item) and i != new_item for i in preserve])
    ]
    return preserve, ignorable


def _remove_double_waits(exists_in_old_and_new):  # type: (List[ExecutionItem]) -> None
    doubles = []
    for i, (j, k) in enumerate(zip(exists_in_old_and_new, exists_in_old_and_new[1:])):
        if j.isWait and k == j:
            doubles.append(i)
    for i in reversed(doubles):
        del exists_in_old_and_new[i]


def _remove_empty_groups(exists_in_old_and_new):  # type: (List[ExecutionItem]) -> None
    removables = []
    for i, (j, k) in enumerate(zip(exists_in_old_and_new, exists_in_old_and_new[1:])):
        if isinstance(j, GroupStartItem) and isinstance(k, GroupEndItem):
            removables.extend([i, i + 1])
    for i in reversed(removables):
        del exists_in_old_and_new[i]


def _split_partially_to_tests(
    new_suites, old_suites
):  # type: (List[SuiteItem], List[ExecutionItem]) -> List[ExecutionItem]
    suits = []  # type: List[ExecutionItem]
    for s in new_suites:
        split = False
        for old_test in old_suites:
            if isinstance(old_test, TestItem) and s.contains(old_test):
                split = True
        if split:
            suits.extend(s.tests)
        else:
            suits.append(s)
    return suits


def _file_hash(lines):
    digest = hashlib.sha1()
    digest.update(lines[0].encode())
    digest.update(lines[1].encode())
    digest.update(lines[2].encode())
    hashes = 0
    for line in lines[4:]:
        if line not in ("#WAIT", "{", "}"):
            line = line.decode("utf-8") if PY2 else line
            hashes ^= int(hashlib.sha1(line.encode("utf-8")).hexdigest(), 16)
    digest.update(str(hashes).encode())
    return digest.hexdigest()


def store_suite_names(hashes, suite_names):
    # type: (Hashes, List[ExecutionItem]) -> None
    assert all(isinstance(s, ExecutionItem) for s in suite_names)
    suite_lines = [s.line() for s in suite_names]
    _write("Storing .pabotsuitenames file")
    try:
        with _open_pabotsuitenames("w") as suitenamesfile:
            suitenamesfile.write("datasources:" + hashes.dirs + "\n")
            suitenamesfile.write("commandlineoptions:" + hashes.cmd + "\n")
            suitenamesfile.write("suitesfrom:" + hashes.suitesfrom + "\n")
            suitenamesfile.write(
                "file:"
                + _file_hash(
                    [
                        "datasources:" + hashes.dirs,
                        "commandlineoptions:" + hashes.cmd,
                        "suitesfrom:" + hashes.suitesfrom,
                        None,
                    ]
                    + suite_lines
                )
                + "\n"
            )
            suitenamesfile.writelines(
                (d + "\n").encode("utf-8") if PY2 and is_unicode(d) else d + "\n"
                for d in suite_lines
            )
    except IOError:

        _write(
            "[ "
            + _wrap_with(Color.YELLOW, "WARNING")
            + " ]: storing .pabotsuitenames failed"
        )


def generate_suite_names(
    outs_dir, datasources, options, pabot_args
):  # type: (object, object, object, Dict[str, str]) -> List[ExecutionItem]
    suites = []  # type: List[SuiteItem]
    if "suitesfrom" in pabot_args and os.path.isfile(pabot_args["suitesfrom"]):
        suites = _suites_from_outputxml(pabot_args["suitesfrom"])
    else:
        suites = generate_suite_names_with_builder(outs_dir, datasources, options)
    if pabot_args.get("testlevelsplit"):
        tests = []  # type: List[ExecutionItem]
        for s in suites:
            tests.extend(s.tests)
        return tests
    return list(suites)


def generate_suite_names_with_builder(outs_dir, datasources, options):
    opts = _options_for_dryrun(options, outs_dir)
    settings = RobotSettings(opts)
    builder = TestSuiteBuilder(
        settings["SuiteNames"], settings.extension, rpa=settings.rpa
    )
    suite = builder.build(*datasources)
    settings.rpa = builder.rpa
    suite.configure(**settings.suite_config)
    if settings.pre_run_modifiers:
        _write.error = _write
        suite.visit(
            ModelModifier(settings.pre_run_modifiers, settings.run_empty_suite, _write)
        )
    all_suites = (
        get_all_suites_from_main_suite(suite.suites) if suite.suites else [suite]
    )
    suite_names = [
        SuiteItem(
            suite.longname,
            tests=[test.longname for test in suite.tests],
            suites=suite.suites,
        )
        for suite in all_suites
    ]
    if not suite_names and not options.get("runemptysuite", False):
        stdout_value = opts["stdout"].getvalue()
        if stdout_value:
            _write(
                "[STDOUT] from suite search:\n" + stdout_value + "[STDOUT] end",
                Color.YELLOW,
            )
        stderr_value = opts["stderr"].getvalue()
        if stderr_value:
            _write(
                "[STDERR] from suite search:\n" + stderr_value + "[STDERR] end",
                Color.RED,
            )
    return list(sorted(set(suite_names)))


def get_all_suites_from_main_suite(suites):
    all_suites = []
    for suite in suites:
        if suite.suites:
            all_suites.extend(get_all_suites_from_main_suite(suite.suites))
        else:
            all_suites.append(suite)
    return all_suites


class SuiteNotPassingsAndTimes(ResultVisitor):
    def __init__(self):
        self.suites = []  # type: List[Tuple[bool, int, str]]

    def start_suite(self, suite):
        if len(suite.tests) > 0:
            self.suites.append((not suite.passed, suite.elapsedtime, suite.longname))


def _suites_from_outputxml(outputxml):
    res = ExecutionResult(outputxml)
    suite_times = SuiteNotPassingsAndTimes()
    res.visit(suite_times)
    return [SuiteItem(suite) for (_, _, suite) in reversed(sorted(suite_times.suites))]


def _options_for_dryrun(options, outs_dir):
    options = options.copy()
    options["log"] = "NONE"
    options["report"] = "NONE"
    options["xunit"] = "NONE"
    options["variable"] = options.get("variable", [])[:]
    options["variable"].append(pabotlib.PABOT_QUEUE_INDEX + ":-1")
    if ROBOT_VERSION >= "2.8":
        options["dryrun"] = True
    else:
        options["runmode"] = "DryRun"
    options["output"] = "suite_names.xml"
    # --timestampoutputs is not compatible with hard-coded suite_names.xml
    options["timestampoutputs"] = False
    options["outputdir"] = outs_dir
    if PY2:
        options["stdout"] = BytesIO()
        options["stderr"] = BytesIO()
    else:
        options["stdout"] = StringIO()
        options["stderr"] = StringIO()
    options["listener"] = []
    return _set_terminal_coloring_options(options)


def _options_for_rebot(options, start_time_string, end_time_string):
    rebot_options = options.copy()
    rebot_options["starttime"] = start_time_string
    rebot_options["endtime"] = end_time_string
    rebot_options["monitorcolors"] = "off"
    rebot_options["suite"] = []
    rebot_options["test"] = []
    rebot_options["exclude"] = []
    rebot_options["include"] = []
    if ROBOT_VERSION >= "2.8":
        options["monitormarkers"] = "off"
    return rebot_options


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def _print_elapsed(start, end):
    _write(
        "Total testing: "
        + _time_string(sum(_ALL_ELAPSED))
        + "\nElapsed time:  "
        + _time_string(end - start)
    )


def _time_string(elapsed):
    millis = int((elapsed * 100) % 100)
    seconds = int(elapsed) % 60
    elapsed_minutes = (int(elapsed) - seconds) / 60
    minutes = elapsed_minutes % 60
    elapsed_hours = (elapsed_minutes - minutes) / 60
    elapsed_string = ""
    if elapsed_hours > 0:
        plural = ""
        if elapsed_hours > 1:
            plural = "s"
        elapsed_string += ("%d hour" % elapsed_hours) + plural + " "
    if minutes > 0:
        plural = ""
        if minutes > 1:
            plural = "s"
        elapsed_string += ("%d minute" % minutes) + plural + " "
    return elapsed_string + "%d.%d seconds" % (seconds, millis)


def keyboard_interrupt(*args):
    global CTRL_C_PRESSED
    CTRL_C_PRESSED = True


def _parallel_execute(items, processes):
    original_signal_handler = signal.signal(signal.SIGINT, keyboard_interrupt)
    pool = ThreadPool(processes)
    result = pool.map_async(execute_and_wait_with, items, 1)
    pool.close()
    while not result.ready():
        # keyboard interrupt is executed in main thread
        # and needs this loop to get time to get executed
        try:
            time.sleep(0.1)
        except IOError:
            keyboard_interrupt()
    signal.signal(signal.SIGINT, original_signal_handler)


def _output_dir(options, cleanup=True):
    outputdir = options.get("outputdir", ".")
    outpath = os.path.join(outputdir, "pabot_results")
    if cleanup and os.path.isdir(outpath):
        shutil.rmtree(outpath)
    return outpath


def _copy_output_artifacts(options, file_extensions=None, include_subfolders=False):
    file_extensions = file_extensions or ["png"]
    pabot_outputdir = _output_dir(options, cleanup=False)
    outputdir = options.get("outputdir", ".")
    copied_artifacts = []
    for location, _, file_names in os.walk(pabot_outputdir):
        for file_name in file_names:
            file_ext = file_name.split(".")[-1]
            if file_ext in file_extensions:
                rel_path = os.path.relpath(location, pabot_outputdir)
                prefix = rel_path.split(os.sep)[0]  # folders named "process-id"
                dst_folder_path = outputdir
                # if it is a file from sub-folders of "location"
                if os.sep in rel_path:
                    if not include_subfolders:
                        continue
                    # create destination sub-folder
                    subfolder_path = rel_path[rel_path.index(os.sep) + 1 :]
                    dst_folder_path = os.path.join(outputdir, subfolder_path)
                    if not os.path.isdir(dst_folder_path):
                        os.makedirs(dst_folder_path)
                dst_file_name = "-".join([prefix, file_name])
                shutil.copyfile(
                    os.path.join(location, file_name),
                    os.path.join(dst_folder_path, dst_file_name),
                )
                copied_artifacts.append(file_name)
    return copied_artifacts


def _report_results(outs_dir, pabot_args, options, start_time_string, tests_root_name):
    if ROBOT_VERSION < "4.0":
        stats = {
            "critical": {"total": 0, "passed": 0, "failed": 0},
            "all": {"total": 0, "passed": 0, "failed": 0},
        }
    else:
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
        }
    if pabot_args["argumentfiles"]:
        outputs = []  # type: List[str]
        for index, _ in pabot_args["argumentfiles"]:
            copied_artifacts = _copy_output_artifacts(
                options, pabot_args["artifacts"], pabot_args["artifactsinsubfolders"]
            )
            outputs += [
                _merge_one_run(
                    os.path.join(outs_dir, index),
                    options,
                    tests_root_name,
                    stats,
                    copied_artifacts,
                    outputfile=os.path.join("pabot_results", "output%s.xml" % index),
                )
            ]
        if "output" not in options:
            options["output"] = "output.xml"
        _write_stats(stats)
        return rebot(*outputs, **_options_for_rebot(options, start_time_string, _now()))
    else:
        return _report_results_for_one_run(
            outs_dir, pabot_args, options, start_time_string, tests_root_name, stats
        )


def _write_stats(stats):
    if ROBOT_VERSION < "4.0":
        crit = stats["critical"]
        al = stats["all"]
        _write(
            "%d critical tests, %d passed, %d failed"
            % (crit["total"], crit["passed"], crit["failed"])
        )
        _write(
            "%d tests total, %d passed, %d failed"
            % (al["total"], al["passed"], al["failed"])
        )
    else:
        _write(
            "%d tests, %d passed, %d failed, %d skipped."
            % (stats["total"], stats["passed"], stats["failed"], stats["skipped"])
        )
    _write("===================================================")


def _report_results_for_one_run(
    outs_dir, pabot_args, options, start_time_string, tests_root_name, stats
):
    copied_artifacts = _copy_output_artifacts(
        options, pabot_args["artifacts"], pabot_args["artifactsinsubfolders"]
    )
    output_path = _merge_one_run(
        outs_dir, options, tests_root_name, stats, copied_artifacts
    )
    _write_stats(stats)
    if (
        "report" in options
        and options["report"] == "NONE"
        and "log" in options
        and options["log"] == "NONE"
    ):
        options[
            "output"
        ] = output_path  # REBOT will return error 252 if nothing is written
    else:
        _write("Output:  %s" % output_path)
        options["output"] = None  # Do not write output again with rebot
    return rebot(output_path, **_options_for_rebot(options, start_time_string, _now()))


def _merge_one_run(
    outs_dir, options, tests_root_name, stats, copied_artifacts, outputfile=None
):
    outputfile = outputfile or options.get("output", "output.xml")
    output_path = os.path.abspath(
        os.path.join(options.get("outputdir", "."), outputfile)
    )
    files = sorted(glob(os.path.join(_glob_escape(outs_dir), "**/*.xml")))
    if not files:
        _write('WARN: No output files in "%s"' % outs_dir, Color.YELLOW)
        return ""

    def invalid_xml_callback():
        global _ABNORMAL_EXIT_HAPPENED
        _ABNORMAL_EXIT_HAPPENED = True

    if PY2:
        files = [f.decode(SYSTEM_ENCODING) if not is_unicode(f) else f for f in files]
    resu = merge(
        files, options, tests_root_name, copied_artifacts, invalid_xml_callback
    )
    _update_stats(resu, stats)
    resu.save(output_path)
    return output_path


def _update_stats(result, stats):
    s = result.statistics
    if ROBOT_VERSION < "4.0":
        stats["critical"]["total"] += s.total.critical.total
        stats["critical"]["passed"] += s.total.critical.passed
        stats["critical"]["failed"] += s.total.critical.failed
        stats["all"]["total"] += s.total.all.total
        stats["all"]["passed"] += s.total.all.passed
        stats["all"]["failed"] += s.total.all.failed
    else:
        stats["total"] += s.total.total
        stats["passed"] += s.total.passed
        stats["failed"] += s.total.failed
        stats["skipped"] += s.total.skipped


# This is from https://github.com/django/django/blob/master/django/utils/glob.py
_magic_check = re.compile("([*?[])")


def _glob_escape(pathname):
    """
    Escape all special characters.
    """
    drive, pathname = os.path.splitdrive(pathname)
    pathname = _magic_check.sub(r"[\1]", pathname)
    return drive + pathname


def _writer():
    while True:
        message = MESSAGE_QUEUE.get()
        if message is None:
            MESSAGE_QUEUE.task_done()
            return
        print(message)
        sys.stdout.flush()
        MESSAGE_QUEUE.task_done()


def _write(message, color=None):
    MESSAGE_QUEUE.put(_wrap_with(color, message))


def _wrap_with(color, message):
    if _is_output_coloring_supported() and color:
        return "%s%s%s" % (color, message, Color.ENDC)
    return message


def _is_output_coloring_supported():
    return sys.stdout.isatty() and os.name in Color.SUPPORTED_OSES


def _start_message_writer():
    t = threading.Thread(target=_writer)
    t.start()


def _stop_message_writer():
    MESSAGE_QUEUE.put(None)
    MESSAGE_QUEUE.join()


def _get_free_port(pabot_args):
    if pabot_args["pabotlibport"] != 0:
        return pabot_args["pabotlibport"]
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _start_remote_library(pabot_args):  # type: (dict) -> Optional[subprocess.Popen]
    global _PABOTLIBURI
    free_port = _get_free_port(pabot_args)
    _PABOTLIBURI = "%s:%s" % (pabot_args["pabotlibhost"], free_port)
    if not pabot_args["pabotlib"]:
        return None
    if pabot_args.get("resourcefile") and not os.path.exists(
        pabot_args["resourcefile"]
    ):
        _write(
            "Warning: specified resource file doesn't exist."
            " Some tests may fail or continue forever.",
            Color.YELLOW,
        )
        pabot_args["resourcefile"] = None
    return subprocess.Popen(
        '"{python}" -m {pabotlibname} {resourcefile} {pabotlibhost} {pabotlibport}'.format(
            python=sys.executable,
            pabotlibname=pabotlib.__name__,
            resourcefile=pabot_args.get("resourcefile"),
            pabotlibhost=pabot_args["pabotlibhost"],
            pabotlibport=free_port,
        ),
        shell=True,
    )


def _stop_remote_library(process):  # type: (subprocess.Popen) -> None
    _write("Stopping PabotLib process")
    try:
        remoteLib = Remote(_PABOTLIBURI)
        remoteLib.run_keyword("stop_remote_libraries", [], {})
        remoteLib.run_keyword("stop_remote_server", [], {})
    except RuntimeError:
        _write("Could not connect to PabotLib - assuming stopped already")
        return
    i = 50
    while i > 0 and process.poll() is None:
        time.sleep(0.1)
        i -= 1
    if i == 0:
        _write(
            "Could not stop PabotLib Process in 5 seconds " "- calling terminate",
            Color.YELLOW,
        )
        process.terminate()
    else:
        _write("PabotLib process stopped")


def _get_suite_root_name(suite_names):
    top_names = [x.top_name() for group in suite_names for x in group]
    if top_names and top_names.count(top_names[0]) == len(top_names):
        return top_names[0]
    return ""


class QueueItem(object):

    _queue_index = 0

    def __init__(
        self,
        datasources,
        outs_dir,
        options,
        execution_item,
        command,
        verbose,
        argfile,
        hive=None,
        processes=0,
    ):
        # type: (List[str], str, Dict[str, object], ExecutionItem, List[str], bool, Tuple[str, Optional[str]], Optional[str], int) -> None
        self.datasources = datasources
        self.outs_dir = (
            outs_dir.encode("utf-8") if PY2 and is_unicode(outs_dir) else outs_dir
        )
        self.options = options
        self.execution_item = (
            execution_item if not hive else HivedItem(execution_item, hive)
        )
        self.command = command
        self.verbose = verbose
        self.argfile_index = argfile[0]
        self.argfile = argfile[1]
        self._index = QueueItem._queue_index
        QueueItem._queue_index += 1
        self.last_level = None
        self.hive = hive
        self.processes = processes

    @property
    def index(self):
        # type: () -> int
        return self._index

    @property
    def display_name(self):
        # type: () -> str
        if self.argfile:
            return "%s {%s}" % (self.execution_item.name, self.argfile)
        return self.execution_item.name


def _create_execution_items(
    suite_names, datasources, outs_dir, options, opts_for_run, pabot_args
):
    is_dry_run = (
        options.get("dryrun")
        if ROBOT_VERSION >= "2.8"
        else options.get("runmode") == "DryRun"
    )
    if is_dry_run:
        all_items = _create_execution_items_for_dry_run(
            suite_names, datasources, outs_dir, opts_for_run, pabot_args
        )
    else:
        all_items = _create_execution_items_for_run(
            suite_names, datasources, outs_dir, options, opts_for_run, pabot_args
        )
    _construct_index_and_completed_index(all_items)
    _construct_last_levels(all_items)
    return all_items


def _construct_index_and_completed_index(all_items):
    # type: (List[List[QueueItem]]) -> None
    global _COMPLETED_LOCK, _NOT_COMPLETED_INDEXES
    with _COMPLETED_LOCK:
        for item_group in all_items:
            for item in item_group:
                _NOT_COMPLETED_INDEXES.append(item.index)


def _create_execution_items_for_run(
    suite_names, datasources, outs_dir, options, opts_for_run, pabot_args
):
    global _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    all_items = []  # type: List[List[QueueItem]]
    _NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0
    for suite_group in suite_names:
        # TODO: Fix this better
        if (
            options.get("randomize") in ["all", "suites"]
            and "suitesfrom" not in pabot_args
        ):
            random.shuffle(suite_group)
        items = _create_items(
            datasources, opts_for_run, outs_dir, pabot_args, suite_group
        )
        _NUMBER_OF_ITEMS_TO_BE_EXECUTED += len(items)
        all_items.append(items)
    return all_items


def _create_items(datasources, opts_for_run, outs_dir, pabot_args, suite_group):
    return [
        QueueItem(
            datasources,
            outs_dir,
            opts_for_run,
            suite,
            pabot_args["command"],
            pabot_args["verbose"],
            argfile,
            pabot_args.get("hive"),
            pabot_args["processes"],
        )
        for suite in suite_group
        for argfile in pabot_args["argumentfiles"] or [("", None)]
    ]


def _create_execution_items_for_dry_run(
    suite_names, datasources, outs_dir, opts_for_run, pabot_args
):
    global _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    all_items = []  # type: List[List[QueueItem]]
    _NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0
    processes_count = pabot_args["processes"]
    for suite_group in suite_names:
        items = _create_items(
            datasources, opts_for_run, outs_dir, pabot_args, suite_group
        )
        chunk_size = (
            round(len(items) / processes_count)
            if len(items) > processes_count
            else len(items)
        )
        chunked_items = list(_chunk_items(items, chunk_size))
        _NUMBER_OF_ITEMS_TO_BE_EXECUTED += len(chunked_items)
        all_items.append(chunked_items)
    return all_items


def _chunk_items(items, chunk_size):
    for i in range(0, len(items), chunk_size):
        chunked_items = items[i : i + chunk_size]
        base_item = chunked_items[0]
        if not base_item:
            continue
        execution_items = SuiteItems([item.execution_item for item in chunked_items])
        chunked_item = QueueItem(
            base_item.datasources,
            base_item.outs_dir,
            base_item.options,
            execution_items,
            base_item.command,
            base_item.verbose,
            (base_item.argfile_index, base_item.argfile),
            processes=base_item.processes,
        )
        yield chunked_item


def _find_ending_level(name, group):
    n = name.split(".")
    level = -1
    for other in group:
        o = other.split(".")
        dif = [i for i in range(min(len(o), len(n))) if o[i] != n[i]]
        if dif:
            level = max(dif[0], level)
        else:
            return name + ".PABOT_noend"
    return ".".join(n[: (level + 1)])


def _construct_last_levels(all_items):
    names = []
    for items in all_items:
        for item in items:
            if isinstance(item.execution_item, SuiteItems):
                for suite in item.execution_item.suites:
                    names.append(suite.name)
            else:
                names.append(item.execution_item.name)
    for items in all_items:
        for item in items:
            if isinstance(item.execution_item, SuiteItems):
                for suite in item.execution_item.suites:
                    item.last_level = _find_ending_level(
                        suite.name, names[item.index + 1 :]
                    )
            else:
                item.last_level = _find_ending_level(
                    item.execution_item.name, names[item.index + 1 :]
                )


def _initialize_queue_index():
    global _PABOTLIBURI
    plib = Remote(_PABOTLIBURI)
    # INITIALISE PARALLEL QUEUE MIN INDEX
    for i in range(300):
        try:
            plib.run_keyword(
                "set_parallel_value_for_key",
                [pabotlib.PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE, 0],
                {},
            )
            return
        except RuntimeError as e:
            # REMOTE LIB NOT YET CONNECTED
            time.sleep(0.1)
    raise RuntimeError("Can not connect to PabotLib at %s" % _PABOTLIBURI)


def _add_dynamically_created_execution_items(
    execution_items, datasources, outs_dir, opts_for_run, pabot_args
):
    global _COMPLETED_LOCK, _NOT_COMPLETED_INDEXES, _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    if not _pabotlib_in_use():
        return
    plib = Remote(_PABOTLIBURI)
    new_suites = plib.run_keyword("get_added_suites", [], {})
    if len(new_suites) == 0:
        return
    suite_group = [DynamicSuiteItem(s, v) for s, v in new_suites]
    items = [
        QueueItem(
            datasources,
            outs_dir,
            opts_for_run,
            suite,
            pabot_args["command"],
            pabot_args["verbose"],
            ("", None),
            pabot_args.get("hive"),
            pabot_args["processes"],
        )
        for suite in suite_group
    ]
    with _COMPLETED_LOCK:
        _NUMBER_OF_ITEMS_TO_BE_EXECUTED += len(items)
        for item in items:
            _NOT_COMPLETED_INDEXES.append(item.index)
    execution_items.insert(0, items)


def main(args=None):
    global _PABOTLIBPROCESS
    args = args or sys.argv[1:]
    if len(args) == 0:
        print(
            "[ "
            + _wrap_with(Color.RED, "ERROR")
            + " ]: Expected at least 1 argument, got 0."
        )
        print("Try --help for usage information.")
        sys.exit(252)
    start_time = time.time()
    start_time_string = _now()
    # NOTE: timeout option
    try:
        _start_message_writer()
        options, datasources, pabot_args, opts_for_run = parse_args(args)
        if pabot_args["help"]:
            print(__doc__)
            sys.exit(0)
        if len(datasources) == 0:
            print("[ " + _wrap_with(Color.RED, "ERROR") + " ]: No datasources given.")
            print("Try --help for usage information.")
            sys.exit(252)
        _PABOTLIBPROCESS = _start_remote_library(pabot_args)
        if _pabotlib_in_use():
            _initialize_queue_index()
        outs_dir = _output_dir(options)
        suite_names = solve_suite_names(outs_dir, datasources, options, pabot_args)
        if pabot_args["verbose"]:
            _write("Suite names resolved in %s seconds" % str(time.time() - start_time))
        ordering = pabot_args.get("ordering")
        if ordering:
            suite_names = _preserve_order(suite_names, ordering)
        suite_names = _group_by_wait(_group_by_groups(suite_names))
        if not suite_names or suite_names == [[]]:
            _write("No tests to execute")
            if not options.get("runemptysuite", False):
                sys.exit(252)
        execution_items = _create_execution_items(
            suite_names, datasources, outs_dir, options, opts_for_run, pabot_args
        )
        while execution_items:
            items = execution_items.pop(0)
            _parallel_execute(items, pabot_args["processes"])
            _add_dynamically_created_execution_items(
                execution_items, datasources, outs_dir, opts_for_run, pabot_args
            )
        result_code = _report_results(
            outs_dir,
            pabot_args,
            options,
            start_time_string,
            _get_suite_root_name(suite_names),
        )
        sys.exit(result_code if not _ABNORMAL_EXIT_HAPPENED else 252)
    except Information as i:
        print(__doc__)
        print(i.message)
    except DataError as err:
        print(err.message)
        sys.exit(252)
    except Exception:
        _write("[ERROR] EXCEPTION RAISED DURING PABOT EXECUTION", Color.RED)
        _write(
            "[ERROR] PLEASE CONSIDER REPORTING THIS ISSUE TO https://github.com/mkorpela/pabot/issues",
            Color.RED,
        )
        raise
    finally:
        if _PABOTLIBPROCESS:
            _stop_remote_library(_PABOTLIBPROCESS)
        _print_elapsed(start_time, time.time())
        _stop_message_writer()


if __name__ == "__main__":
    main()
