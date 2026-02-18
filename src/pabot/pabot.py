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

# Help documentation from README.md:
"""A parallel executor for Robot Framework test cases.
Version [PABOT_VERSION]

PLACEHOLDER_README.MD

Copyright 2022 Mikko Korpela - Apache 2 License
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
import copy
from collections import namedtuple
from contextlib import closing
from glob import glob
from io import BytesIO, StringIO
from multiprocessing.pool import ThreadPool
from pathlib import Path

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

from . import pabotlib, __version__ as PABOT_VERSION
from .arguments import (
    parse_args,
    parse_execution_item_line,
    _filter_argument_parser_options,
)
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
    RunnableItem,
    SleepItem,
    create_dependency_tree,
)
from .result_merger import merge
from .writer import get_writer, get_stdout_writer, get_stderr_writer, ThreadSafeWriter, MessageWriter

try:
    import queue  # type: ignore
except ImportError:
    import Queue as queue  # type: ignore

try:
    from shlex import quote  # type: ignore
except ImportError:
    from pipes import quote  # type: ignore

try:
    import importlib.metadata
    METADATA_AVAILABLE = True
except ImportError:
    METADATA_AVAILABLE = False

from typing import Any, Dict, List, Optional, Tuple, Union

CTRL_C_PRESSED = False
_PABOTLIBURI = "127.0.0.1:8270"
_PABOTLIBPROCESS = None  # type: Optional[subprocess.Popen]
_PABOTWRITER = None  # type: Optional[MessageWriter]
_PABOTLIBTHREAD = None  # type: Optional[threading.Thread]
_NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0
_ABNORMAL_EXIT_HAPPENED = False
_PABOTCONSOLE = "verbose"  # type: str
_USE_USER_COMMAND = False

_COMPLETED_LOCK = threading.Lock()
_NOT_COMPLETED_INDEXES = []  # type: List[int]

# Thread-local storage for tracking executor number assigned to each thread
_EXECUTOR_THREAD_LOCAL = threading.local()
# Next executor number to assign (incremented each time a task is submitted)
_EXECUTOR_COUNTER = 0
_EXECUTOR_COUNTER_LOCK = threading.Lock()
# Maximum number of executors (workers in the thread pool)
_MAX_EXECUTORS = 1

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

# Python version check for supporting importlib.metadata (requires Python 3.8+)
IS_PYTHON_3_8_OR_NEWER = sys.version_info >= (3, 8)

_PROCESS_MANAGER = None

def _ensure_process_manager():
    global _PROCESS_MANAGER
    if _PROCESS_MANAGER is None:
        from pabot.ProcessManager import ProcessManager
        _PROCESS_MANAGER = ProcessManager()
    return _PROCESS_MANAGER


def read_args_from_readme():
    """Reads a specific section from package METADATA or development README.md if available."""

    # 1. Try to read from METADATA (only if available and Python version is compatible)
    metadata_section = read_from_metadata()
    if metadata_section:
        return f"Extracted from METADATA:\n\n{metadata_section}"

    # 2. If METADATA is not available, fall back to development environment README.md
    dev_readme_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "README.md"))
    if os.path.exists(dev_readme_path):
        with open(dev_readme_path, encoding="utf-8") as f:
            lines = f.readlines()
            help_args = extract_section(lines)
            if help_args:
                return f"Extracted from README.md ({dev_readme_path}):\n\n{help_args}"

    if not IS_PYTHON_3_8_OR_NEWER:
        return (
            "Warning: Your Python version is too old and does not support importlib.metadata.\n"
            "Please consider upgrading to Python 3.8 or newer for better compatibility.\n\n"
            "To view any possible arguments, please kindly read the README.md here:\n"
            "https://github.com/mkorpela/pabot"
        )

    return (
        "Error: README.md or METADATA long_description not found.\n"
        "If you believe this is an issue, please report it at:\n"
        "https://github.com/mkorpela/pabot/issues"
    )


def read_from_metadata():
    """Reads the long_description section from package METADATA if available."""
    if not METADATA_AVAILABLE:
        return None

    try:
        metadata = importlib.metadata.metadata("robotframework-pabot")
        description = metadata.get("Description", "")

        if not description:
            return None

        lines = description.splitlines(True)
        return extract_section(lines)

    except importlib.metadata.PackageNotFoundError:
        return None


def extract_section(lines, start_marker="<!-- START DOCSTRING -->", end_marker="<!-- END DOCSTRING -->"):
    """Extracts content between two markers in a list of lines."""
    inside_section = False
    extracted_lines = []

    for line in lines:
        if start_marker in line:
            inside_section = True
            continue
        if end_marker in line:
            break
        if inside_section:
            extracted_lines.append(line)

    result = "".join(extracted_lines)

    # Remove Markdown hyperlinks but keep text
    result = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', result)
    # Remove Markdown section links but keep text
    result = re.sub(r'\[([^\]]+)\]\(#[^\)]+\)', r'\1', result)
    # Remove ** and backticks `
    result = re.sub(r'(\*\*|`)', '', result)

    return result.strip()


class Color:
    SUPPORTED_OSES = ["posix"]

    GREEN = "\033[92m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    YELLOW = "\033[93m"


def _get_next_executor_num():
    """Get the next executor number in round-robin fashion."""
    global _EXECUTOR_COUNTER, _MAX_EXECUTORS
    with _EXECUTOR_COUNTER_LOCK:
        executor_num = _EXECUTOR_COUNTER % _MAX_EXECUTORS
        _EXECUTOR_COUNTER += 1
    return executor_num


def _set_executor_num(executor_num):
    """Set the executor number for the current thread."""
    _EXECUTOR_THREAD_LOCAL.executor_num = executor_num


def _get_executor_num():
    """Get the executor number for the current thread."""
    return getattr(_EXECUTOR_THREAD_LOCAL, 'executor_num', 0)


def _execute_item_with_executor_tracking(item):
    """Wrapper to track executor number and call execute_and_wait_with."""
    executor_num = _get_next_executor_num()
    _set_executor_num(executor_num)
    return execute_and_wait_with(item)


def execute_and_wait_with(item):
    # type: ('QueueItem') -> int
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
        run_cmd, run_options = _create_command_for_execution(
            caller_id, datasources, is_last, item, outs_dir
        )
        rc = 0
        if item.hive:
            _hived_execute(
                item.hive,
                run_cmd + run_options,
                outs_dir,
                name,
                item.verbose,
                _get_executor_num(),
                caller_id,
                item.index,
            )
        else:
            rc = _try_execute_and_wait(
                run_cmd,
                run_options,
                outs_dir,
                name,
                item.verbose,
                _get_executor_num(),
                caller_id,
                item.index,
                item.execution_item.type != "test",
                process_timeout=item.timeout,
                sleep_before_start=item.sleep_before_start
            )
        outputxml_preprocessing(
            item.options, outs_dir, name, item.verbose, _get_executor_num(), caller_id, item.index
        )
    except:
        _write(traceback.format_exc(), level="error")
    return rc


def has_robot_stacktracer(min_version="0.4.1"):
    try:
        import RobotStackTracer  # type: ignore
        from packaging.version import Version
        return Version(RobotStackTracer.__version__) >= Version(min_version)  # type: ignore
    except (ImportError, ModuleNotFoundError, AttributeError):
        return False


def _create_command_for_execution(caller_id, datasources, is_last, item, outs_dir):
    options = item.options.copy()
    if item.command == ["robot"] and not options["listener"] and has_robot_stacktracer():
        options["listener"] = ["RobotStackTracer"]
    run_options = (
        _options_for_custom_executor(
            options,
            outs_dir,
            item.execution_item,
            item.argfile,
            caller_id,
            is_last,
            item.index,
            item.last_level,
            item.processes,
            item.skip,
        )
        + datasources
    )
    return item.command, run_options

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
        _write(traceback.format_exc(), level="error")
    if plib:
        _increase_completed(plib, my_index)


def _try_execute_and_wait(
    run_cmd,
    run_options,
    outs_dir,
    item_name,
    verbose,
    pool_id,
    caller_id,
    my_index=-1,
    show_stdout_on_failure=False,
    process_timeout=None,
    sleep_before_start=0
):
    # type: (List[str], List[str], str, str, bool, int, str, int, bool, Optional[int], int) -> int
    plib = None
    is_ignored = False
    if _pabotlib_in_use():
        plib = Remote(_PABOTLIBURI)

    command_name = _get_command_name(run_cmd[0])
    stdout_path = os.path.join(outs_dir, f"{command_name}_stdout.out")
    stderr_path = os.path.join(outs_dir, f"{command_name}_stderr.out")

    try:
        with open(stdout_path, "w", encoding="utf-8", buffering=1) as stdout, \
             open(stderr_path, "w", encoding="utf-8", buffering=1) as stderr:

            process, (rc, elapsed) = _run(
                run_cmd,
                run_options,
                stderr,
                stdout,
                item_name,
                verbose,
                pool_id,
                my_index,
                outs_dir,
                process_timeout,
                sleep_before_start
            )

            # Ensure writing
            stdout.flush()
            stderr.flush()
            os.fsync(stdout.fileno())
            os.fsync(stderr.fileno())

        if plib:
            _increase_completed(plib, my_index)
            is_ignored = _is_ignored(plib, caller_id)

        # Thread-safe list append
        _ALL_ELAPSED.append(elapsed)

        _result_to_stdout(
            elapsed=elapsed,
            is_ignored=is_ignored,
            item_name=item_name,
            my_index=my_index,
            pool_id=pool_id,
            process=process,
            rc=rc,
            stderr=stderr_path,
            stdout=stdout_path,
            verbose=verbose,
            show_stdout_on_failure=show_stdout_on_failure,
        )

        if is_ignored and os.path.isdir(outs_dir):
            _rmtree_with_path(outs_dir)
        return rc
    
    except:
        _write(traceback.format_exc(), level="error")
        return 252


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
            level="info_ignored",
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
            level="info_failed",
        )
    else:
        _write_with_id(
            process,
            pool_id,
            my_index,
            _execution_passed_message(item_name, stdout, stderr, elapsed, verbose),
            Color.GREEN,
            level="info_passed",
        )


def _is_ignored(plib, caller_id):  # type: (Remote, str) -> bool
    return plib.run_keyword("is_ignored_execution", [caller_id], {})


# optionally invoke rebot for output.xml preprocessing to get --RemoveKeywords
# and --flattenkeywords applied => result: much smaller output.xml files + faster merging + avoid MemoryErrors
def outputxml_preprocessing(options, outs_dir, item_name, verbose, pool_id, caller_id, item_id):
    # type: (Dict[str, Any], str, str, bool, int, str, int) -> None
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
        output_name = options.get("output", "output.xml")
        outputxmlfile = os.path.join(outs_dir, output_name)
        if not os.path.isfile(outputxmlfile):
            raise DataError(f"Preprosessing cannot be done because file {outputxmlfile} not exists.")
        oldsize = os.path.getsize(outputxmlfile)
        process_empty = ["--processemptysuite"] if options.get("runemptysuite") else []
        run_cmd = ["rebot"]
        run_options = (
            [
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
            + process_empty
            + remove_keywords_args
            + flatten_keywords_args
            + ["--output", outputxmlfile, outputxmlfile]
        )
        _try_execute_and_wait(
            run_cmd,
            run_options,
            outs_dir,
            f"preprocessing {output_name} on " + item_name,
            verbose,
            pool_id,
            caller_id,
            item_id,
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


def _write_with_id(process, pool_id, item_index, message, color=None, timestamp=None, level="debug"):
    timestamp = timestamp or datetime.datetime.now()
    _write(
        "%s [PID:%s] [%s] [ID:%s] %s"
        % (timestamp, process.pid, pool_id, item_index, message),
        color,
        level=level,
    )


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


def _write_internal_argument_file(cmd_args, filename):
    # type: (List[str], str) -> None
    """
    Writes a list of command-line arguments to a file.
    If an argument starts with '-' or '--', its value (the next item) is written on the same line.

    Example:
        ['--name', 'value', '--flag', '--other', 'x']
        becomes:
            --name value
            --flag
            --other x

    :param cmd_args: List of argument strings to write
    :param filename: Target filename
    """
    with open(filename, "w", encoding="utf-8") as f:
        i = 0
        while i < len(cmd_args):
            current = cmd_args[i]
            if current.startswith("-") and i + 1 < len(cmd_args) and not cmd_args[i + 1].startswith("-"):
                f.write(f"{current} {cmd_args[i + 1]}\n")
                i += 2
            else:
                f.write(f"{current}\n")
                i += 1


def _run(
    run_command,
    run_options,
    stderr,
    stdout,
    item_name,
    verbose,
    pool_id,
    item_index,
    outs_dir,
    process_timeout,
    sleep_before_start,
):
    timestamp = datetime.datetime.now()

    if sleep_before_start > 0:
        _write(f"{timestamp} [{pool_id}] [ID:{item_index}] SLEEPING {sleep_before_start} SECONDS BEFORE STARTING {item_name}")
        time.sleep(sleep_before_start)

    command_name = _get_command_name(run_command[0])
    argfile_path = os.path.join(outs_dir, f"{command_name}_argfile.txt")
    _write_internal_argument_file(run_options, filename=argfile_path)

    cmd = run_command + ['-A', argfile_path]
    my_env = os.environ.copy()
    syslog_file = my_env.get("ROBOT_SYSLOG_FILE", None)
    if syslog_file:
        my_env["ROBOT_SYSLOG_FILE"] = os.path.join(outs_dir, os.path.basename(syslog_file))

    log_path = os.path.join(outs_dir, f"{command_name}_{item_index}.log")

    manager = _ensure_process_manager()
    process, (rc, elapsed) = manager.run(
        cmd,
        env=my_env,
        stdout=stdout,
        stderr=stderr,
        timeout=process_timeout,
        verbose=verbose,
        item_name=item_name,
        log_file=log_path,
        pool_id=pool_id,
        item_index=item_index,
    )

    return process, (rc, elapsed)


def _read_file(file_handle):
    try:
        with open(file_handle, "r") as content_file:
            content = content_file.read()
        return content
    except Exception as e:
        return "Unable to read file %s, error: %s" % (os.path.abspath(file_handle), e)


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
    skip,
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
    pabotExecutionPoolId = "PABOTEXECUTIONPOOLID:%d" % _get_executor_num()
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
        _modify_options_for_argfile_use(argfile, options)
        options["argumentfile"] = argfile
    if options.get("test", False) and options.get("include", []):
        del options["include"]
    if skip:
        this_dir = os.path.dirname(os.path.abspath(__file__))
        listener_path = os.path.join(this_dir, "listener", "skip_listener.py")
        options["dryrun"] = True
        options["listener"].append(listener_path)
        options["exitonfailure"] = True
    return _set_terminal_coloring_options(options)


def _modify_options_for_argfile_use(argfile, options):
    argfile_opts, _ = ArgumentParser(
        USAGE,
        **_filter_argument_parser_options(
            auto_pythonpath=False,
            auto_argumentfile=True,
            env_options="ROBOT_OPTIONS",
        ),
    ).parse_args(["--argumentfile", argfile])
    if argfile_opts["name"]:
        new_name = argfile_opts["name"]
        _replace_base_name(new_name, options, "suite")
        if not options["suite"]:
            _replace_base_name(new_name, options, "test")
        if "name" in options:
            del options["name"]


def _replace_base_name(new_name, options, key):
    if isinstance(options.get(key), str):
        options[key] = f"{new_name}.{options[key].split('.', 1)[1]}" if '.' in options[key] else new_name
    elif key in options:
        options[key] = [
            f"{new_name}.{s.split('.', 1)[1]}" if '.' in s else new_name
            for s in options.get(key, [])
        ]


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
    # type: (List[ExecutionItem]) -> List[ExecutionItem]
    result = []
    group = None
    for token in tokens:
        if isinstance(token, GroupStartItem):
            if group is not None:
                raise DataError(
                    "Ordering: Group can not contain a group. Encoutered '{'"
                )
            group = GroupItem()
            group.set_sleep(token.get_sleep())
            result.append(group)
            continue
        if isinstance(token, GroupEndItem):
            if group is None:
                raise DataError(
                    "Ordering: Group end tag '}' encountered before start '{'"
                )
            group.change_items_order_by_depends()
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


def solve_shard_suites(suite_names, pabot_args):
    if pabot_args.get("shardcount", 1) <= 1:
        return suite_names
    if "shardindex" not in pabot_args:
        return suite_names
    shard_index = pabot_args["shardindex"]
    shard_count = pabot_args["shardcount"]
    if shard_index > shard_count:
        raise DataError(
            f"Shard index ({shard_index}) greater than shard count ({shard_count})."
        )
    items_count = len(suite_names)
    if items_count < shard_count:
        raise DataError(
            f"Not enought items ({items_count}) for shard cound ({shard_count})."
        )
    q, r = divmod(items_count, shard_count)
    return suite_names[
        (shard_index - 1) * q
        + min(shard_index - 1, r) : shard_index * q
        + min(shard_index, r)
    ]


def solve_suite_names(outs_dir, datasources, options, pabot_args):
    if pabot_args.get("pabotprerunmodifier"):
        options['prerunmodifier'].append(pabot_args['pabotprerunmodifier'])
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
            if corrupted or h != file_h or file_hash != hash_of_file or pabot_args.get("pabotprerunmodifier"):
                if file_h is not None and file_h[0] != h[0] and file_h[2] == h[2]:
                    suite_names = _levelsplit(
                        generate_suite_names_with_builder(outs_dir, datasources, options),
                        pabot_args,
                    )
                    store_suite_names(h, suite_names)
                    return suite_names
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
        # If there are no tests, it may be that --runemptysuite option is used, so fallback suites
        if tests:
            return tests
    return list(suites)


def _group_by_wait(lines):
    # type: (List[ExecutionItem]) -> List[List[ExecutionItem]]
    suites = [[]]
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
        suites = _suites_from_file(
            file_h, h, pabot_args, outs_dir, datasources, options, lines
        )
    else:
        suites = _suites_from_wrong_or_empty_file(
            pabot_args, outs_dir, datasources, options, lines
        )
    if suites:
        store_suite_names(h, suites)
    assert all(isinstance(s, ExecutionItem) for s in suites)
    return suites


def _suites_from_file(file_h, h, pabot_args, outs_dir, datasources, options, lines):
    suites = _suites_from_outputxml(pabot_args["suitesfrom"])
    if file_h is None or file_h.dirs != h.dirs:
        all_suites = generate_suite_names_with_builder(outs_dir, datasources, options)
    else:
        all_suites = [suite for suite in lines if suite]
    return _preserve_order(all_suites, suites)


def _suites_from_wrong_or_empty_file(pabot_args, outs_dir, datasources, options, lines):
    suites = _levelsplit(
        generate_suite_names_with_builder(outs_dir, datasources, options),
        pabot_args,
    )
    return _preserve_order(suites, [suite for suite in lines if suite])


def _contains_suite_and_test(suites):
    return any(isinstance(s, SuiteItem) for s in suites) and any(
        isinstance(t, TestItem) for t in suites
    )


def _preserve_order(new_items, old_items):
    assert all(isinstance(s, ExecutionItem) for s in new_items)
    if not old_items:
        return new_items
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
            + " ]: storing .pabotsuitenames failed", level="warning", 
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
    if "pythonpath" in opts:
        del opts["pythonpath"]
    settings = RobotSettings(opts)

    # Note: first argument (included_suites) is deprecated from RobotFramework 6.1
    if ROBOT_VERSION >= "6.1":
        builder = TestSuiteBuilder(
            included_extensions=settings.extension,
            included_files=settings.parse_include,
            rpa=settings.rpa,
            lang=opts.get("language"),
        )
    else:
        builder = TestSuiteBuilder(
            settings["SuiteNames"], settings.extension, rpa=settings.rpa
        )

    suite = builder.build(*datasources)

    if settings.pre_run_modifiers:
        _write.error = _write.warn = _write.info = _write.debug = _write.trace = _write
        suite.visit(
            ModelModifier(settings.pre_run_modifiers, settings.run_empty_suite, _write)
        )

    settings.rpa = builder.rpa
    suite.configure(**settings.suite_config)

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
                Color.YELLOW, level="warning",
            )
        stderr_value = opts["stderr"].getvalue()
        if stderr_value:
            _write(
                "[STDERR] from suite search:\n" + stderr_value + "[STDERR] end",
                Color.RED, level="error",
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


def _options_for_rebot(options, start_time_string, end_time_string, num_of_executions=0):
    rebot_options = options.copy()
    rebot_options["starttime"] = start_time_string
    rebot_options["endtime"] = end_time_string
    rebot_options["monitorcolors"] = "off"
    rebot_options["suite"] = []
    rebot_options["test"] = []
    rebot_options["exclude"] = []
    rebot_options["include"] = []
    rebot_options["metadata"].append(
        f"Pabot Info:[https://pabot.org/?ref=log|Pabot] result from {num_of_executions} executions."
    )
    rebot_options["metadata"].append(
        f"Pabot Version:{PABOT_VERSION}"
    )
    if rebot_options.get("runemptysuite"):
        rebot_options["processemptysuite"] = True
    if ROBOT_VERSION >= "2.8":
        options["monitormarkers"] = "off"
    for key in [
        "console",
        "consolemarkers",
        "consolewidth",
        "debugfile",
        "dotted",
        "dryrun",
        "exitonerror",
        "exitonfailure",
        "extension",
        "listener",
        "loglevel",
        "language",
        "maxassignlength",
        "maxerrorlines",
        "monitorcolors",
        "parser",
        "prerunmodifier",
        "quiet",
        "randomize",
        "runemptysuite",
        "rerunfailed",
        "rerunfailedsuites",
        "skip",
        "skiponfailure",
        "skipteardownonexit",
        "variable",
        "variablefile",
    ]:
        if key in rebot_options:
            del rebot_options[key]
    return rebot_options


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def _print_elapsed(start, end):
    _write(
        "Total testing: "
        + _time_string(sum(_ALL_ELAPSED)), level="info"
    )
    _write(
        "Elapsed time:  "
        + _time_string(end - start), level="info"
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
    # Notify ProcessManager to interrupt running processes
    if _PROCESS_MANAGER:
        _PROCESS_MANAGER.set_interrupted()
    if _PABOTWRITER:
        _write("[ INTERRUPT ] Ctrl+C pressed - initiating graceful shutdown...", Color.YELLOW, level="warning")
    else:
        print("[ INTERRUPT ] Ctrl+C pressed - initiating graceful shutdown...")


def _get_depends(item):
    return getattr(item.execution_item, "depends", [])


def _dependencies_satisfied(item, completed):
    """
    Check if all dependencies for an item are satisfied (completed).
    Uses unique names that include argfile_index when applicable.
    """
    for dep in _get_depends(item):
        # Build unique name for dependency with same argfile_index as the item
        if hasattr(item, 'argfile_index') and item.argfile_index:
            # Item has an argfile index, so check for dependency with same argfile index
            dep_unique_name = f"{item.argfile_index}:{dep}"
            if dep_unique_name not in completed:
                return False
        else:
            # No argfile index (single argumentfile case)
            if dep not in completed:
                return False
    
    return True


def _collect_transitive_dependents(failed_name, pending_items):
    """
    Returns all pending items that (directly or indirectly) depend on failed_name.
    Handles both regular names and unique names (with argfile_index).
    
    When failed_name is "1:Suite", it means Suite failed in argumentfile 1.
    We should only skip items in argumentfile 1 that depend on Suite,
    not items in other argumentfiles.
    """
    to_skip = set()
    queue = [failed_name]

    # Extract argfile_index from failed_name if it has one
    if ":" in failed_name:
        argfile_index, base_name = failed_name.split(":", 1)
    else:
        argfile_index = ""
        base_name = failed_name

    # Build dependency map: item unique name -> set of dependency base names
    depends_map = {
        _get_unique_execution_name(item): set(_get_depends(item))
        for item in pending_items
    }

    while queue:
        current = queue.pop(0)
        
        # Extract base name from current (e.g., "1:Suite" -> "Suite")
        if ":" in current:
            current_argfile, current_base = current.split(":", 1)
        else:
            current_argfile = ""
            current_base = current
        
        for item_name, deps in depends_map.items():
            # Only skip items from the same argumentfile
            # Check if item_name corresponds to the same argumentfile
            if ":" in item_name:
                item_argfile, _ = item_name.split(":", 1)
            else:
                item_argfile = ""
            
            # Only process if same argumentfile
            if item_argfile != argfile_index:
                continue
            
            # Check if this item depends on the current failed item
            if current_base in deps and item_name not in to_skip:
                to_skip.add(item_name)
                queue.append(item_name)

    return to_skip


def _get_unique_execution_name(item):
    """
    Create a unique identifier for an execution item that includes argfile index.
    This ensures that the same test run with different argumentfiles are treated as distinct items.
    """
    if item.argfile_index:
        return f"{item.argfile_index}:{item.execution_item.name}"
    return item.execution_item.name


def _parallel_execute_dynamic(
    items,
    processes,
    datasources,
    outs_dir,
    opts_for_run,
    pabot_args,
):
    # Signal handler is already set in main_program, no need to set it again
    # Just use the thread pool without managing signals
    global _MAX_EXECUTORS, _EXECUTOR_COUNTER

    max_processes = processes or len(items)
    _MAX_EXECUTORS = max_processes
    _EXECUTOR_COUNTER = 0  # Reset executor counter for each parallel execution batch
    pool = ThreadPool(max_processes)

    pending = set(items)
    running = {}
    completed = set()
    failed = set()

    failure_policy = pabot_args.get("ordering", {}).get("failure_policy", "run_all")
    lock = threading.Lock()

    def on_complete(it, rc):
        nonlocal pending, running, completed, failed

        with lock:
            running.pop(it, None)
            unique_name = _get_unique_execution_name(it)
            completed.add(unique_name)

            if rc != 0:
                failed.add(unique_name)

                if failure_policy == "skip":
                    to_skip_names = _collect_transitive_dependents(
                        unique_name,
                        pending,
                    )

                    for other in list(pending):
                        other_unique_name = _get_unique_execution_name(other)
                        if other_unique_name in to_skip_names:
                            # Only log skip once when first marking it as skipped
                            if not other.skip:
                                _write(
                                    f"Skipping '{other_unique_name}' because dependency "
                                    f"'{unique_name}' failed (transitive).",
                                    Color.YELLOW, level="debug"
                                )
                            other.skip = True

    try:
        while pending or running:
            with lock:
                ready = [
                    item for item in list(pending)
                    if _dependencies_satisfied(item, completed)
                ]

                while ready and len(running) < max_processes:
                    item = ready.pop(0)
                    pending.remove(item)

                    result = pool.apply_async(
                        _execute_item_with_executor_tracking,
                        (item,),
                        callback=lambda rc, it=item: on_complete(it, rc),
                    )
                    running[item] = result

            dynamic_items = _get_dynamically_created_execution_items(
                datasources, outs_dir, opts_for_run, pabot_args
            )
            if dynamic_items:
                with lock:
                    for di in dynamic_items:
                        pending.add(di)

            time.sleep(0.1)

    finally:
        pool.close()
        # Signal handler was set in main_program and will be restored there


def _parallel_execute(
    items, processes, datasources, outs_dir, opts_for_run, pabot_args
):
    # Signal handler is already set in main_program, no need to set it again
    global _MAX_EXECUTORS, _EXECUTOR_COUNTER
    max_workers = len(items) if processes is None else processes
    _MAX_EXECUTORS = max_workers
    _EXECUTOR_COUNTER = 0  # Reset executor counter for each parallel execution batch
    pool = ThreadPool(max_workers)
    results = [pool.map_async(_execute_item_with_executor_tracking, items, 1)]
    delayed_result_append = 0
    new_items = []
    while not all(result.ready() for result in results) or delayed_result_append > 0:
        # keyboard interrupt is executed in main thread
        # and needs this loop to get time to get executed
        try:
            time.sleep(0.1)
        except IOError:
            keyboard_interrupt()
        dynamic_items = _get_dynamically_created_execution_items(
            datasources, outs_dir, opts_for_run, pabot_args
        )
        if dynamic_items:
            new_items += dynamic_items
            # Because of last level construction, wait for more.
            delayed_result_append = 3
        delayed_result_append = max(0, delayed_result_append - 1)
        if new_items and delayed_result_append == 0:
            _construct_last_levels([new_items])
            results.append(pool.map_async(_execute_item_with_executor_tracking, new_items, 1))
            new_items = []
    pool.close()
    # Signal handler will be restored in main_program's finally block


def _output_dir(options, cleanup=True):
    outputdir = options.get("outputdir", ".")
    outpath = os.path.join(outputdir, "pabot_results")
    if cleanup and os.path.isdir(outpath):
        _rmtree_with_path(outpath)
    return outpath


def _rmtree_with_path(path):
    """
    Remove a directory tree and, if a PermissionError occurs,
    re-raise it with the absolute path included in the message.
    """
    try:
        shutil.rmtree(path)
    except PermissionError as e:
        abs_path = os.path.abspath(path)
        raise PermissionError(f"Failed to delete path {abs_path}") from e


def _get_timestamp_id(timestamp_str, add_timestamp):
    # type: (str, bool) -> Optional[str]
    if add_timestamp:
        return str(datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y%m%d_%H%M%S"))
    return None


def _copy_output_artifacts(options, timestamp_id=None, file_extensions=None, include_subfolders=False, index=None):
    file_extensions = file_extensions or ["png"]
    pabot_outputdir = _output_dir(options, cleanup=False)
    outputdir = options.get("outputdir", ".")
    copied_artifacts = []
    one_run_outputdir = pabot_outputdir
    if index:  # For argumentfileN option:
        one_run_outputdir = os.path.join(pabot_outputdir, index)
    for location, _, file_names in os.walk(one_run_outputdir):
        for file_name in file_names:
            file_ext = file_name.split(".")[-1]
            if file_ext in file_extensions:
                rel_path = os.path.relpath(location, one_run_outputdir)
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
                dst_file_name_parts = [timestamp_id, index, prefix, file_name]
                filtered_name = [str(p) for p in dst_file_name_parts if p is not None]
                dst_file_name = "-".join(filtered_name)
                shutil.copy2(
                    os.path.join(location, file_name),
                    os.path.join(dst_folder_path, dst_file_name),
                )
                copied_artifacts.append(file_name)
    return copied_artifacts


def _check_pabot_results_for_missing_xml(base_dir, command_list, output_xml_name='output.xml'):
    """
    Check for missing Robot Framework output XML files in pabot result directories,
    taking into account the optional timestamp added by the -T option.

    Args:
        base_dir: The root directory containing pabot subdirectories
        command_list: list of commands for starting subprocesses
        output_xml_name: Expected XML filename, e.g., 'output.xml'

    Returns:
        List of paths to stderr output files for directories where the XML is missing.
    """
    missing = []
    # Prepare regex to match timestamped filenames like output-YYYYMMDD-hhmmss.xml
    name_stem = os.path.splitext(output_xml_name)[0]
    name_suffix = os.path.splitext(output_xml_name)[1]
    pattern = re.compile(rf"^{re.escape(name_stem)}(-\d{{8}}-\d{{6}})?{re.escape(name_suffix)}$")

    for root, dirs, _ in os.walk(base_dir):
        if root == base_dir:
            for subdir in dirs:
                subdir_path = os.path.join(base_dir, subdir)
                # Check if any file matches the expected XML name or timestamped variant
                has_xml = any(pattern.match(fname) for fname in os.listdir(subdir_path))
                if not has_xml:
                    sanitized_cmd = _get_command_name(command_list[0])
                    missing.append(os.path.join(subdir_path, f"{sanitized_cmd}_stderr.out"))
            break  # only check immediate subdirectories
    return missing


def _get_command_name(command_name):
    global _USE_USER_COMMAND
    return "user_command" if _USE_USER_COMMAND else command_name


def _report_results(outs_dir, pabot_args, options, start_time_string, tests_root_name):
    if "pythonpath" in options:
        del options["pythonpath"]
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
    missing_outputs = []
    if pabot_args["argumentfiles"]:
        outputs = []  # type: List[str]
        total_num_of_executions = 0
        for index, _ in pabot_args["argumentfiles"]:
            copied_artifacts = _copy_output_artifacts(
                options, _get_timestamp_id(start_time_string, pabot_args["artifactstimestamps"]), pabot_args["artifacts"], pabot_args["artifactsinsubfolders"], index
            )
            output, num_of_executions = _merge_one_run(
                os.path.join(outs_dir, index),
                options,
                tests_root_name,
                stats,
                copied_artifacts,
                timestamp_id=_get_timestamp_id(start_time_string, pabot_args["artifactstimestamps"]),
                outputfile=os.path.join("pabot_results", "output%s.xml" % index),
            )
            outputs += [output]
            total_num_of_executions += num_of_executions
            missing_outputs.extend(_check_pabot_results_for_missing_xml(os.path.join(outs_dir, index), pabot_args.get('command')))
        if "output" not in options:
            options["output"] = "output.xml"
        _write_stats(stats)
        stdout_writer = get_stdout_writer()
        stderr_writer = get_stderr_writer(original_stderr_name='Internal Rebot')
        exit_code = rebot(*outputs, **_options_for_rebot(options, start_time_string, _now(), total_num_of_executions), stdout=stdout_writer, stderr=stderr_writer)
    else:
        exit_code = _report_results_for_one_run(
            outs_dir, pabot_args, options, start_time_string, tests_root_name, stats
        )
        missing_outputs.extend(_check_pabot_results_for_missing_xml(outs_dir, pabot_args.get('command')))
    if missing_outputs:
        _write(("[ " + _wrap_with(Color.YELLOW, 'WARNING') + " ] "
                "One or more subprocesses encountered an error and the "
                "internal .xml files could not be generated. Please check the "
                "following stderr files to identify the cause:"), level="warning")
        for missing in missing_outputs:
            _write(repr(missing), level="warning")
        _write((f"[ " + _wrap_with(Color.RED, 'ERROR') + " ] "
                "The output, log and report files produced by Pabot are "
                "incomplete and do not contain all test cases."), level="error")
    return exit_code if not missing_outputs else 252


def _write_stats(stats):
    if ROBOT_VERSION < "4.0":
        crit = stats["critical"]
        al = stats["all"]
        _write(
            "%d critical tests, %d passed, %d failed"
            % (crit["total"], crit["passed"], crit["failed"]), level="info"
        )
        _write(
            "%d tests total, %d passed, %d failed"
            % (al["total"], al["passed"], al["failed"]), level="info"
        )
    else:
        _write(
            "%d tests, %d passed, %d failed, %d skipped."
            % (stats["total"], stats["passed"], stats["failed"], stats["skipped"]), level="info"
        )
    _write("===================================================", level="info")


def add_timestamp_to_filename(file_path: str, timestamp: str) -> str:
    """
    Rename the given file by inserting a timestamp before the extension.
    Format: YYYYMMDD-hhmmss
    Example: output.xml -> output-20251222-152233.xml
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"{file_path} does not exist")

    new_name = f"{file_path.stem}-{timestamp}{file_path.suffix}"
    new_path = file_path.with_name(new_name)
    file_path.rename(new_path)
    return str(new_path)


def _report_results_for_one_run(
    outs_dir, pabot_args, options, start_time_string, tests_root_name, stats
):
    copied_artifacts = _copy_output_artifacts(
        options, _get_timestamp_id(start_time_string, pabot_args["artifactstimestamps"]), pabot_args["artifacts"], pabot_args["artifactsinsubfolders"]
    )
    output_path, num_of_executions = _merge_one_run(
        outs_dir, options, tests_root_name, stats, copied_artifacts, _get_timestamp_id(start_time_string, pabot_args["artifactstimestamps"])
    )
    _write_stats(stats)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if "timestampoutputs" in options and options["timestampoutputs"]:
        output_path = add_timestamp_to_filename(output_path, ts)
    if (
        "report" in options
        and options["report"].upper() == "NONE"
        and "log" in options
        and options["log"].upper() == "NONE"
    ):
        options[
            "output"
        ] = output_path  # REBOT will return error 252 if nothing is written
    else:
        _write("Output:  %s" % output_path, level="info")
        options["output"] = None  # Do not write output again with rebot
    stdout_writer = get_stdout_writer()
    stderr_writer = get_stderr_writer(original_stderr_name="Internal Rebot")
    exit_code = rebot(output_path, **_options_for_rebot(options, start_time_string, ts, num_of_executions), stdout=stdout_writer, stderr=stderr_writer)
    return exit_code


def _merge_one_run(
    outs_dir, options, tests_root_name, stats, copied_artifacts, timestamp_id, outputfile=None
):
    outputfile = outputfile or options.get("output", "output.xml")
    output_path = os.path.abspath(
        os.path.join(options.get("outputdir", "."), outputfile)
    )
    filename = "output.xml"
    base_name, ext = os.path.splitext(filename)
    # Glob all candidates
    candidate_files = glob(os.path.join(outs_dir, "**", f"*{base_name}*{ext}"), recursive=True)

    # Regex: basename or basename-YYYYMMDD-hhmmss.ext
    ts_pattern = re.compile(rf"^{re.escape(base_name)}(?:-\d{{8}}-\d{{6}})?{re.escape(ext)}$")

    files = [f for f in candidate_files if ts_pattern.search(os.path.basename(f))]

    # For sorting ./pabot_results/X/Y/output.xml paths without natsort library
    def natural_key(s):
        return [int(t) if t.isdigit() else t.casefold()
                for t in re.split(r'(\d+)', s)]

    files.sort(key=natural_key)

    if not files:
        _write('[ WARNING ]: No output files in "%s"' % outs_dir, Color.YELLOW, level="warning")
        return "", 0

    def invalid_xml_callback():
        global _ABNORMAL_EXIT_HAPPENED
        _ABNORMAL_EXIT_HAPPENED = True

    if PY2:
        files = [f.decode(SYSTEM_ENCODING) if not is_unicode(f) else f for f in files]
    resu = merge(
        files, options, tests_root_name, copied_artifacts, timestamp_id, invalid_xml_callback
    )
    _update_stats(resu, stats)
    if ROBOT_VERSION >= "7.0" and options.get("legacyoutput"):
        resu.save(output_path, legacy_output=True)
    else:
        resu.save(output_path)
    return output_path, len(files)


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


def _write(message, color=None, level="debug"):
    writer = get_writer()
    writer.write(message, color=color, level=level)


def _wrap_with(color, message):
    if _is_output_coloring_supported() and color:
        return "%s%s%s" % (color, message, Color.ENDC)
    return message


def _is_output_coloring_supported():
    return sys.stdout.isatty() and os.name in Color.SUPPORTED_OSES


def _is_port_available(port):
    """Check if a given port on localhost is available."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        try:
            s.bind(("localhost", port))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return True
        except OSError:
            return False


def _get_free_port():
    """Return a free TCP port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _start_remote_library(pabot_args):  # type: (dict) -> Optional[Tuple[subprocess.Popen, threading.Thread]]
    global _PABOTLIBURI
    # If pabotlib is not enabled, do nothing
    if not pabot_args.get("pabotlib"):
        return None, None

    host = pabot_args.get("pabotlibhost", "127.0.0.1")
    port = pabot_args.get("pabotlibport", 8270)

    # If host is default and user specified a non-zero port, check if it's available
    if host == "127.0.0.1" and port != 0 and not _is_port_available(port):
        _write(
            f"Warning: specified pabotlibport {port} is already in use. "
            "A free port will be assigned automatically.",
            Color.YELLOW, level="warning"
        )
        port = _get_free_port()

    # If host is default and port = 0, assign a free port
    if host == "127.0.0.1" and port == 0:
        port = _get_free_port()

    _PABOTLIBURI = f"{host}:{port}"
    resourcefile = pabot_args.get("resourcefile") or ""
    if resourcefile and not os.path.exists(resourcefile):
        _write(
            "Warning: specified resource file doesn't exist."
            " Some tests may fail or continue forever.",
            Color.YELLOW, level="warning"
        )
        resourcefile = ""
    cmd = [
        sys.executable,
        "-m", pabotlib.__name__,
        resourcefile,
        pabot_args["pabotlibhost"],
        str(port),
    ]
    # Start PabotLib in isolation so it doesn't receive CTRL+C when the main process is interrupted.
    # This allows graceful shutdown in finally block.
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
        "env": {**os.environ, "PYTHONUNBUFFERED": "1"},
    }
    if sys.platform.startswith('win'):
        # Windows: use CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        # Unix/Linux/macOS: use preexec_fn to create new session
        import os as os_module
        kwargs["preexec_fn"] = os_module.setsid
    
    process = subprocess.Popen(cmd, **kwargs)

    def _read_output(proc, writer):
        try:
            for line in proc.stdout:
                if line.strip():  # Skip empty lines
                    try:
                        writer.write(line.rstrip('\n') + '\n', level="info")
                        writer.flush()
                    except (RuntimeError, ValueError):
                        # Writer/stdout already closed during shutdown
                        break
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

    pabotlib_writer = ThreadSafeWriter(get_writer())
    thread = threading.Thread(
        target=_read_output,
        args=(process, pabotlib_writer),
        daemon=False,  # Non-daemon so output is captured before exit
    )
    thread.start()

    return process, thread


def _stop_remote_library(process):  # type: (subprocess.Popen) -> None
    _write("Stopping PabotLib process", level="debug")
    try:
        remoteLib = Remote(_PABOTLIBURI)
        remoteLib.run_keyword("stop_remote_libraries", [], {})
        remoteLib.run_keyword("stop_remote_server", [], {})
    except RuntimeError:
        _write("Could not connect to PabotLib - assuming stopped already", level="info")
    
    # Always wait for graceful shutdown, regardless of remote connection status
    i = 50
    while i > 0 and process.poll() is None:
        time.sleep(0.1)
        i -= 1
    
    # If still running after remote stop attempt, terminate it
    if process.poll() is None:
        _write(
            "Could not stop PabotLib Process in 5 seconds " "- calling terminate",
            Color.YELLOW, level="warning"
        )
        process.terminate()
        # Give it a moment to respond to SIGTERM
        time.sleep(0.5)
        if process.poll() is None:
            _write(
                "PabotLib Process did not respond to terminate - calling kill",
                Color.RED, level="error"
            )
            process.kill()
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
        timeout=None,
        skip=False,
    ):
        # type: (List[str], str, Dict[str, object], ExecutionItem, List[str], bool, Tuple[str, Optional[str]], Optional[str], int, Optional[int], bool) -> None
        self.datasources = datasources
        self.outs_dir = (
            outs_dir.encode("utf-8") if PY2 and is_unicode(outs_dir) else outs_dir
        )
        self.options = options
        self.options["output"] = "output.xml"  # This is hardcoded output.xml inside pabot_results, not the final output
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
        self.timeout = timeout
        self.sleep_before_start = execution_item.get_sleep()
        self.skip = skip

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
    suite_groups, datasources, outs_dir, options, opts_for_run, pabot_args
):
    is_dry_run = (
        options.get("dryrun")
        if ROBOT_VERSION >= "2.8"
        else options.get("runmode") == "DryRun"
    )
    if is_dry_run and not pabot_args.get("ordering"):
        all_items = _create_execution_items_for_dry_run(
            suite_groups, datasources, outs_dir, opts_for_run, pabot_args
        )
    else:
        all_items = _create_execution_items_for_run(
            suite_groups, datasources, outs_dir, options, opts_for_run, pabot_args
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
    suite_groups, datasources, outs_dir, options, opts_for_run, pabot_args
):
    global _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    all_items = []  # type: List[List[QueueItem]]
    _NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0
    for suite_group in suite_groups:
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


def _create_items(datasources, opts_for_run, outs_dir, pabot_args, suite_group, argfile=None):
    # If argfile is provided, use only that one. Otherwise, loop through all argumentfiles.
    argumentfiles = [argfile] if argfile is not None else (pabot_args["argumentfiles"] or [("", None)])
    return [
        QueueItem(
            datasources,
            outs_dir,
            opts_for_run,
            suite,
            pabot_args["command"],
            pabot_args["verbose"],
            af,
            pabot_args.get("hive"),
            pabot_args["processes"],
            pabot_args["processtimeout"],
        )
        for suite in suite_group
        for af in argumentfiles
    ]


def _create_execution_items_for_dry_run(
    suite_groups, datasources, outs_dir, opts_for_run, pabot_args
):
    global _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    all_items = []  # type: List[List[QueueItem]]
    _NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0
    processes_count = pabot_args["processes"]
    for suite_group in suite_groups:
        items = _create_items(
            datasources, opts_for_run, outs_dir, pabot_args, suite_group
        )
        chunk_size = (
            round(len(items) / processes_count) if len(items) > processes_count else 1
        )
        chunked_items = list(_chunk_items(items, chunk_size))
        _NUMBER_OF_ITEMS_TO_BE_EXECUTED += len(chunked_items)
        all_items.append(chunked_items)
    return all_items


def _chunk_items(items, chunk_size):
    for i in range(0, len(items), chunk_size):
        chunked_items = items[i : i + chunk_size]
        if not chunked_items:
            continue
        # For TestItem execution items, yield each item separately
        # For Suite items, combine them into one item
        base_item = chunked_items[0]
        if isinstance(base_item.execution_item, TestItem):
            for item in chunked_items:
                yield item
        else:
            # For suites, create a combined execution item with all suite execution items
            execution_items = SuiteItems([item.execution_item for item in chunked_items])
            # Reuse the base item but update its execution_item to the combined one
            base_item.execution_item = execution_items
            yield base_item


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
    index = 0
    for items in all_items:
        for item in items:
            if isinstance(item.execution_item, SuiteItems):
                for suite in item.execution_item.suites:
                    item.last_level = _find_ending_level(suite.name, names[index + 1 :])
            else:
                item.last_level = _find_ending_level(
                    item.execution_item.name, names[index + 1 :]
                )
            index += 1


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


def _get_dynamically_created_execution_items(
    datasources, outs_dir, opts_for_run, pabot_args
):
    global _COMPLETED_LOCK, _NOT_COMPLETED_INDEXES, _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    if not _pabotlib_in_use():
        return None
    plib = Remote(_PABOTLIBURI)
    try:
        new_suites = plib.run_keyword("get_added_suites", [], {})
    except RuntimeError as err:
        _write(
            "[ WARNING ] PabotLib unreachable during post-run phase, "
            "assuming no dynamically added suites. "
            "Original error: %s",
            err, level="warning"
        )
        new_suites = []
    if len(new_suites) == 0:
        return None
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
            pabot_args["processtimeout"],
        )
        for suite in suite_group
    ]
    with _COMPLETED_LOCK:
        _NUMBER_OF_ITEMS_TO_BE_EXECUTED += len(items)
        for item in items:
            _NOT_COMPLETED_INDEXES.append(item.index)
    return items


def main(args=None):
    return sys.exit(main_program(args))


def main_program(args):
    global _PABOTLIBPROCESS, _PABOTCONSOLE, _PABOTWRITER, _PABOTLIBTHREAD, _USE_USER_COMMAND
    outs_dir = None
    version_or_help_called = False
    args = args or sys.argv[1:]
    if len(args) == 0:
        print(
            "[ "
            + _wrap_with(Color.RED, "ERROR")
            + " ]: Expected at least 1 argument, got 0."
        )
        print("Try --help for usage information.")
        return 252
    start_time = time.time()
    start_time_string = _now()
    # NOTE: timeout option
    original_signal_handler = signal.default_int_handler  # Save default handler in case of early exit
    try:
        options, datasources, pabot_args, opts_for_run = parse_args(args)
        _USE_USER_COMMAND = pabot_args.get("use_user_command", False)
        _PABOTCONSOLE = pabot_args.get("pabotconsole", "verbose")
        if pabot_args["help"]:
            help_print = __doc__.replace(
                    "PLACEHOLDER_README.MD",
                    read_args_from_readme()
                )
            print(help_print.replace("[PABOT_VERSION]", PABOT_VERSION, 1))
            version_or_help_called = True
            return 251
        if len(datasources) == 0:
            print("[ " + _wrap_with(Color.RED, "ERROR") + " ]: No datasources given.")
            print("Try --help for usage information.")
            return 252
        outs_dir = _output_dir(options)

        # These ensure MessageWriter and ProcessManager are ready before any parallel execution.
        _PABOTWRITER = get_writer(log_dir=outs_dir, console_type=_PABOTCONSOLE)
        _ensure_process_manager()
        _write(f"Initialized logging in {outs_dir}", level="info")

        _PABOTLIBPROCESS, _PABOTLIBTHREAD = _start_remote_library(pabot_args)
        # Set up signal handler to keep PabotLib alive during CTRL+C
        # This ensures graceful shutdown in the finally block
        original_signal_handler = signal.signal(signal.SIGINT, keyboard_interrupt)
        if _pabotlib_in_use():
            _initialize_queue_index()

        suite_groups = _group_suites(outs_dir, datasources, options, pabot_args)
        if pabot_args["verbose"]:
            _write("Suite names resolved in %s seconds" % str(time.time() - start_time))
        if not suite_groups or suite_groups == [[]]:
            _write("No tests to execute", level="info")
            if not options.get("runemptysuite", False):
                return 252
        
        # Create execution items for all argumentfiles at once
        all_execution_items = _create_execution_items(
            suite_groups, datasources, outs_dir, options, opts_for_run, pabot_args
        )
        
        # Now execute all items from all argumentfiles in parallel
        if pabot_args.get("ordering", {}).get("mode") == "dynamic":
            # flatten stages
            flattened_items = []
            for stage in all_execution_items:
                flattened_items.extend(stage)
            _parallel_execute_dynamic(
                flattened_items,
                pabot_args["processes"],
                datasources,
                outs_dir,
                opts_for_run,
                pabot_args,
            )
        else:
            while all_execution_items:
                items = all_execution_items.pop(0)
                _parallel_execute(
                    items,
                    pabot_args["processes"],
                    datasources,
                    outs_dir,
                    opts_for_run,
                    pabot_args,
                    )
        if pabot_args["no-rebot"]:
            _write((
                "All tests were executed, but the --no-rebot argument was given, "
                "so the results were not compiled, and no summary was generated. "
                f"All results have been saved in the {outs_dir} folder."
            ), level="info")
            _write("===================================================", level="info")
            return 253
        result_code = _report_results(
            outs_dir,
            pabot_args,
            options,
            start_time_string,
            _get_suite_root_name(suite_groups),
        )
        # If CTRL+C was pressed during execution, raise KeyboardInterrupt now. 
        # This can happen without previous errors if test are for example almost ready.
        if CTRL_C_PRESSED:
            raise KeyboardInterrupt()
        return result_code if not _ABNORMAL_EXIT_HAPPENED else 252
    except Information as i:
        version_print = __doc__.replace("\nPLACEHOLDER_README.MD\n", "")
        print(version_print.replace("[PABOT_VERSION]", PABOT_VERSION))
        if _PABOTWRITER:
            _write(i.message, level="info")
        else:
            print(i.message)
        version_or_help_called = True
        return 251
    except DataError as err:
        if _PABOTWRITER:
            _write(err.message, Color.RED, level="error")
        else:
            print(err.message)
        return 252
    except (Exception, KeyboardInterrupt):
        if not CTRL_C_PRESSED:
            if _PABOTWRITER:
                _write("[ ERROR ] EXCEPTION RAISED DURING PABOT EXECUTION", Color.RED, level="error")
                _write(
                    "[ ERROR ] PLEASE CONSIDER REPORTING THIS ISSUE TO https://github.com/mkorpela/pabot/issues",
                    Color.RED, level="error"
                )
                _write("Pabot: %s" % PABOT_VERSION, level="info")
                _write("Python: %s" % sys.version, level="info")
                _write("Robot Framework: %s" % ROBOT_VERSION, level="info")
            else:
                print("[ ERROR ] EXCEPTION RAISED DURING PABOT EXECUTION")
                print("[ ERROR ] PLEASE CONSIDER REPORTING THIS ISSUE TO https://github.com/mkorpela/pabot/issues")
                print("Pabot: %s" % PABOT_VERSION)
                print("Python: %s" % sys.version)
                print("Robot Framework: %s" % ROBOT_VERSION)
            import traceback
            traceback.print_exc()
            return 255
        else:
            if _PABOTWRITER:
                _write("[ ERROR ] Execution stopped by user (Ctrl+C)", Color.RED, level="error")
            else:
                print("[ ERROR ] Execution stopped by user (Ctrl+C)")
            return 253
    finally:
        if not version_or_help_called and _PABOTWRITER:
            _write("Finalizing Pabot execution...", level="debug")
        
        # Restore original signal handler
        try:
            signal.signal(signal.SIGINT, original_signal_handler)
        except Exception as e:
            if _PABOTWRITER:
                _write(f"[ WARNING ] Could not restore signal handler: {e}", Color.YELLOW, level="warning")
            else:
                print(f"[ WARNING ] Could not restore signal handler: {e}")
        
        # First: Terminate all test subprocesses gracefully
        # This must happen BEFORE stopping PabotLib so test processes
        # can cleanly disconnect from the remote library
        try:
            if _PROCESS_MANAGER:
                _PROCESS_MANAGER.terminate_all()
        except Exception as e:
            if _PABOTWRITER:
                _write(f"[ WARNING ] Could not terminate test subprocesses: {e}", Color.YELLOW, level="warning")
            else:
                print(f"[ WARNING ] Could not terminate test subprocesses: {e}")
        
        # Then: Stop PabotLib after all test processes are gone
        # This ensures clean shutdown with no orphaned remote connections
        try:
            if _PABOTLIBPROCESS:
                _stop_remote_library(_PABOTLIBPROCESS)
        except Exception as e:
            if _PABOTWRITER:
                _write(f"[ WARNING ] Failed to stop remote library cleanly: {e}", Color.YELLOW, level="warning")
            else:
                print(f"[ WARNING ] Failed to stop remote library cleanly: {e}")
        
        # Print elapsed time
        try:
            if not version_or_help_called and _PABOTWRITER:
                _print_elapsed(start_time, time.time())
        except Exception as e:
            if _PABOTWRITER:
                _write(f"[ WARNING ] Failed to print elapsed time: {e}", Color.YELLOW, level="warning")
            else:
                print(f"[ WARNING ] Failed to print elapsed time: {e}")

        # Ensure pabotlib output reader thread has finished
        try:
            if _PABOTLIBTHREAD:
                _PABOTLIBTHREAD.join(timeout=5)
                if _PABOTLIBTHREAD.is_alive():
                    if _PABOTWRITER:
                        _write(
                            "[ WARNING ] PabotLib output thread did not finish before timeout",
                            Color.YELLOW,
                            level="warning"
                        )
                    else:
                        print("[ WARNING ] PabotLib output thread did not finish before timeout")
        except Exception as e:
            if _PABOTWRITER:
                _write(f"[ WARNING ] Could not join pabotlib output thread: {e}", Color.YELLOW, level="warning")
            else:
                print(f"[ WARNING ] Could not join pabotlib output thread: {e}")

        # Flush and stop writer
        try:
            if _PABOTWRITER:
                _PABOTWRITER.write("Logs flushed successfully.", level="debug")
                _PABOTWRITER.flush()
            elif not version_or_help_called:
                writer = get_writer()
                if writer:
                    writer.flush()
        except Exception as e:
            print(f"[ WARNING ] Could not flush writer: {e}")
        
        try:
            if _PABOTWRITER:
                _PABOTWRITER.stop()
            elif not version_or_help_called:
                writer = get_writer()
                if writer:
                    writer.stop()
        except Exception as e:
            print(f"[ WARNING ] Could not stop writer: {e}")


def _parse_ordering(filename):  # type: (str) -> List[ExecutionItem]
    try:
        with open(filename, "r") as orderingfile:
            return [
                parse_execution_item_line(line.strip())
                for line in orderingfile.readlines() if line.strip() != ""
            ]
    except FileNotFoundError:
        raise DataError("Error: File '%s' not found." % filename)
    except (ValueError, AssertionError) as e:
        raise DataError("Error in ordering file: %s: %s" % (filename, e))
    except Exception:
        raise DataError("Error parsing ordering file '%s'" % filename)


def _check_ordering(ordering_file, suite_names):  # type: (List[ExecutionItem], List[ExecutionItem]) -> None
    list_of_suite_names = [s.name for s in suite_names]
    skipped_runnable_items = []
    suite_and_test_names = []
    duplicates = []
    if ordering_file:
        for item in ordering_file:
            if item.type in ['suite', 'test']:
                if not any((s == item.name or s.endswith("." + item.name)) for s in list_of_suite_names):
                    # If test name is too long, it gets name ' Invalid', so skip that
                    # Additionally, the test is skipped also if the user wants a higher-level suite to be executed sequentially by using 
                    # the --suite option, and the given name is part of the full name of any test or suite.
                    if item.name != ' Invalid' and not (item.type == 'suite' and any((s == item.name or s.startswith(item.name + ".")) for s in list_of_suite_names)):
                        skipped_runnable_items.append(f"{item.type.title()} item: '{item.name}'")
                if item.name in suite_and_test_names:
                    duplicates.append(f"{item.type.title()} item: '{item.name}'")
                suite_and_test_names.append(item.name)
    if skipped_runnable_items:
        _write("Note: The ordering file contains test or suite items that are not included in the current test run. The following items will be ignored/skipped:", level="info")
        for item in skipped_runnable_items:
            _write(f"  - {item}", level="info")
    if duplicates:
        _write("Note: The ordering file contains duplicate suite or test items. Only the first occurrence is taken into account. These are duplicates:", level="info")
        for item in duplicates:
            _write(f"  - {item}", level="info")


def _group_suites(outs_dir, datasources, options, pabot_args):
    suite_names = solve_suite_names(outs_dir, datasources, options, pabot_args)
    _verify_depends(suite_names)
    ordering_arg = _parse_ordering(pabot_args.get("ordering").get("file")) if (pabot_args.get("ordering")) is not None else None
    if ordering_arg:
        _verify_depends(ordering_arg)
        if options.get("name"):
            ordering_arg = _update_ordering_names(ordering_arg, options['name'])
        _check_ordering(ordering_arg, suite_names)
    if pabot_args.get("testlevelsplit") and ordering_arg and any(item.type == 'suite' for item in ordering_arg):
        reduced_suite_names = _reduce_items(suite_names, ordering_arg)
        if options.get("runemptysuite") and not reduced_suite_names:
            return [suite_names]
        if reduced_suite_names:
            suite_names = reduced_suite_names
    ordering_arg_with_sleep = _set_sleep_times(ordering_arg)
    ordered_suites = _preserve_order(suite_names, ordering_arg_with_sleep)
    shard_suites = solve_shard_suites(ordered_suites, pabot_args)
    grouped_suites = (
        _chunked_suite_names(shard_suites, pabot_args.get("processes"))
        if pabot_args.get("chunk") and not pabot_args.get("ordering")
        else _group_by_wait(_group_by_groups(shard_suites))
    )
    grouped_by_depend = _all_grouped_suites_by_depend(grouped_suites)
    return grouped_by_depend


def _update_ordering_names(ordering, new_top_name):
    # type: (List[ExecutionItem], str) -> List[ExecutionItem]
    output = []
    for item in ordering:
        if item.type in ['suite', 'test']:
            splitted_name = item.name.split('.')
            splitted_name[0] = new_top_name
            item.name = '.'.join(splitted_name)

            # Replace dependencies too
            deps = []
            for d in item.depends:
                splitted_name = d.split('.')
                splitted_name[0] = new_top_name
                deps.append('.'.join(splitted_name))

            item.depends = deps

        output.append(item)
    return output


def _reduce_items(items, selected_suites):
    # type: (List[ExecutionItem], List[ExecutionItem]) -> List[ExecutionItem]
    """
    Reduce a list of test items by replacing covered test cases with suite items from selected_suites.
    Raises DataError if:
    - Any test is covered by more than one selected suite.
    """
    reduced = []
    suite_coverage = {}
    test_to_suite = {}

    for suite in selected_suites:
        if suite.type == 'suite':
            suite_name = str(suite.name)
            covered_tests = [
                item for item in items
                if item.type == "test" and str(item.name).startswith(suite_name + ".")
            ]

            if covered_tests:
                for test in covered_tests:
                    test_name = str(test.name)
                    if test_name in test_to_suite:
                        raise DataError(
                            f"Invalid test configuration: Test '{test_name}' is matched by multiple suites: "
                            f"'{test_to_suite[test_name]}' and '{suite_name}'."
                        )
                    test_to_suite[test_name] = suite_name

                suite_coverage[suite_name] = set(str(t.name) for t in covered_tests)
                reduced.append(suite)

    # Add tests not covered by any suite
    for item in items:
        if item.type == "test" and str(item.name) not in test_to_suite:
            reduced.append(item)

    return reduced


def _set_sleep_times(ordering_arg):
    # type: (List[ExecutionItem]) -> List[ExecutionItem]
    set_sleep_value = 0
    in_group = False
    output = copy.deepcopy(ordering_arg)
    if output is not None:
        if len(output) >= 2:
            for i in range(len(output) - 1):
                if isinstance(output[i], SleepItem):
                    set_sleep_value = output[i].get_sleep()
                else:
                    set_sleep_value = 0
                if isinstance(output[i], GroupStartItem):
                    in_group = True
                if isinstance(output[i], GroupEndItem):
                    in_group = False
                if isinstance(output[i + 1], GroupStartItem) and set_sleep_value > 0:
                    output[i + 1].set_sleep(set_sleep_value)
                if isinstance(output[i + 1], RunnableItem) and set_sleep_value > 0 and not in_group:
                    output[i + 1].set_sleep(set_sleep_value)
    return output


def _chunked_suite_names(suite_names, processes):
    q, r = divmod(len(suite_names), processes)
    result = []
    for index in range(processes):
        chunk = suite_names[
            (index) * q + min(index, r) : (index + 1) * q + min((index + 1), r)
        ]
        if len(chunk) == 0:
            continue
        grouped = GroupItem()
        for item in chunk:
            grouped.add(item)
        result.append(grouped)
    return [result]


def _verify_depends(suite_names):
    runnable_suites = list(
        filter(lambda suite: isinstance(suite, RunnableItem), suite_names)
    )
    suites_with_depends = list(filter(lambda suite: suite.depends, runnable_suites))
    suites_with_found_dependencies = list(
        filter(
            lambda suite: any(
                runnable_suite.name in suite.depends
                for runnable_suite in runnable_suites
            ),
            suites_with_depends,
        )
    )
    if suites_with_depends != suites_with_found_dependencies:
        raise DataError(
            "Invalid test configuration: Some test suites have dependencies (#DEPENDS) that cannot be found."
        )
    suites_with_circular_dependencies = list(
        filter(lambda suite: suite.name in suite.depends, suites_with_depends)
    )
    if suites_with_circular_dependencies:
        raise DataError(
            "Invalid test configuration: Test suites cannot depend on themselves."
        )


def _all_grouped_suites_by_depend(grouped_suites):
    # type: (List[List[ExecutionItem]]) -> List[List[ExecutionItem]]
    grouped_by_depend = []
    for group_suite in grouped_suites:  # These groups are divided by #WAIT
        grouped_by_depend.extend(create_dependency_tree(group_suite))
    return grouped_by_depend


if __name__ == "__main__":
    main()
