import atexit
import multiprocessing
import os
import glob
import re
import tempfile
from typing import Dict, List, Optional, Tuple

from robot import __version__ as ROBOT_VERSION
from robot.errors import DataError
from robot.run import USAGE
from robot.utils import ArgumentParser

from .execution_items import (
    DynamicTestItem,
    ExecutionItem,
    GroupEndItem,
    GroupStartItem,
    IncludeItem,
    SuiteItem,
    TestItem,
    WaitItem,
    SleepItem,
)

ARGSMATCHER = re.compile(r"--argumentfile(\d+)")


def _processes_count():  # type: () -> int
    try:
        return max(multiprocessing.cpu_count(), 2)
    except NotImplementedError:
        return 2


def _filter_argument_parser_options(**options):
    # Note: auto_pythonpath is deprecated since RobotFramework 5.0, but only
    # communicated to users from 6.1
    if ROBOT_VERSION >= "5.0" and "auto_pythonpath" in options:
        del options["auto_pythonpath"]
    return options


def parse_args(
    args,
):  # type: (List[str]) -> Tuple[Dict[str, object], List[str], Dict[str, object], Dict[str, object]]
    args, pabot_args = _parse_pabot_args(args)
    options, datasources = ArgumentParser(
        USAGE,
        **_filter_argument_parser_options(
            auto_pythonpath=False,
            auto_argumentfile=True,
            env_options="ROBOT_OPTIONS",
        ),
    ).parse_args(args)
    options_for_subprocesses, sources_without_argfile = ArgumentParser(
        USAGE,
        **_filter_argument_parser_options(
            auto_pythonpath=False,
            auto_argumentfile=False,
            env_options="ROBOT_OPTIONS",
        ),
    ).parse_args(args)
    if len(datasources) != len(sources_without_argfile):
        raise DataError(
            "Pabot does not support datasources in argumentfiles.\nPlease move datasources to commandline."
        )
    if len(datasources) > 1 and options["name"] is None:
        options["name"] = "Suites"
        options_for_subprocesses["name"] = "Suites"
    opts = _delete_none_keys(options)
    opts_sub = _delete_none_keys(options_for_subprocesses)
    _replace_arg_files(pabot_args, opts_sub)
    return opts, datasources, pabot_args, opts_sub


# remove options from argumentfile according to different scenarios.
# -t/--test/--task shall be removed if --testlevelsplit options exists
# -s/--suite shall be removed if --testlevelsplit options does not exist
def _replace_arg_files(pabot_args, opts_sub):
    _cleanup_old_pabot_temp_files()
    if not opts_sub.get('argumentfile') or not opts_sub['argumentfile']:
        return
    arg_file_list = opts_sub['argumentfile']
    temp_file_list = []
    test_level = pabot_args.get('testlevelsplit')

    for arg_file_path in arg_file_list:
        with open(arg_file_path, 'r') as arg_file:
            arg_file_lines = arg_file.readlines()
        if not arg_file_lines:
            continue

        fd, temp_path = tempfile.mkstemp(prefix="pabot_temp_", suffix=".txt")
        with os.fdopen(fd, 'wb') as temp_file:
            for line in arg_file_lines:
                if test_level and _is_test_option(line):
                    continue
                elif not test_level and _is_suite_option(line):
                    continue
                temp_file.write(line.encode('utf-8'))

        temp_file_list.append(temp_path)

    opts_sub['argumentfile'] = temp_file_list
    atexit.register(cleanup_temp_file, temp_file_list)


def _is_suite_option(line):
    return line.startswith('-s ') or line.startswith('--suite ')


def _is_test_option(line):
    return line.startswith('-t ') or line.startswith('--test ') or line.startswith('--task ')


# clean the temp argument files before exiting the pabot process
def cleanup_temp_file(temp_file_list):
    for temp_file in temp_file_list:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


# Deletes all possible pabot_temp_ files from os temp directory
def _cleanup_old_pabot_temp_files():
    temp_dir = tempfile.gettempdir()
    pattern = os.path.join(temp_dir, "pabot_temp_*.txt")
    old_files = glob.glob(pattern)
    for file_path in old_files:
        try:
            os.remove(file_path)
        except Exception:
            pass


def _parse_shard(arg):
    # type: (str) -> Tuple[int, int]
    parts = arg.split("/")
    return int(parts[0]), int(parts[1])


def _parse_pabot_args(args):  # type: (List[str]) -> Tuple[List[str], Dict[str, object]]
    pabot_args = {
        "command": ["pybot" if ROBOT_VERSION < "3.1" else "robot"],
        "verbose": False,
        "help": False,
        "version": False,
        "testlevelsplit": False,
        "pabotlib": True,
        "pabotlibhost": "127.0.0.1",
        "pabotlibport": 8270,
        "processes": _processes_count(),
        "processtimeout": None,
        "artifacts": ["png"],
        "artifactsinsubfolders": False,
        "shardindex": 0,
        "shardcount": 1,
        "chunk": False,
        "no-rebot": False,
    }
    # Explicitly define argument types for validation
    flag_args = {
        "verbose",
        "help",
        "testlevelsplit",
        "pabotlib",
        "artifactsinsubfolders",
        "chunk",
        "no-rebot"
    }
    value_args = {
        "hive": str,
        "processes": lambda x: int(x) if x != "all" else None,
        "resourcefile": str,
        "pabotlibhost": str,
        "pabotlibport": int,
        "pabotprerunmodifier": str,
        "processtimeout": int,
        "ordering": str,
        "suitesfrom": str,
        "artifacts": lambda x: x.split(","),
        "shard": _parse_shard,
    }

    argumentfiles = []
    remaining_args = []
    i = 0

    # Track conflicting options during parsing
    saw_pabotlib_flag = False
    saw_no_pabotlib = False

    while i < len(args):
        arg = args[i]
        if not arg.startswith("--"):
            remaining_args.append(arg)
            i += 1
            continue

        arg_name = arg[2:]  # Strip '--'

        if arg_name == "no-pabotlib":
            saw_no_pabotlib = True
            pabot_args["pabotlib"] = False  # Just set the main flag
            args = args[1:]
            continue
        if arg_name == "pabotlib":
            saw_pabotlib_flag = True
            args = args[1:]
            continue

        # Special case for command
        if arg_name == "command":
            try:
                end_index = args.index("--end-command", i)
                pabot_args["command"] = args[i + 1 : end_index]
                i = end_index + 1
                continue
            except ValueError:
                raise DataError("--command requires matching --end-command")

        # Handle flag arguments
        if arg_name in flag_args:
            pabot_args[arg_name] = True
            i += 1
            continue

        # Handle value arguments
        if arg_name in value_args:
            if i + 1 >= len(args):
                raise DataError(f"--{arg_name} requires a value")
            try:
                value = value_args[arg_name](args[i + 1])
                if arg_name == "shard":
                    pabot_args["shardindex"], pabot_args["shardcount"] = value
                elif arg_name == "pabotlibhost":
                    pabot_args["pabotlib"] = False
                    pabot_args[arg_name] = value
                else:
                    pabot_args[arg_name] = value
                i += 2
                continue
            except (ValueError, TypeError) as e:
                raise DataError(f"Invalid value for --{arg_name}: {args[i + 1]}")

        # Handle argument files
        match = ARGSMATCHER.match(arg)
        if match:
            if i + 1 >= len(args):
                raise DataError(f"{arg} requires a value")
            argumentfiles.append((match.group(1), args[i + 1]))
            i += 2
            continue

        # If we get here, it's a non-pabot argument
        remaining_args.append(arg)
        i += 1

    if saw_pabotlib_flag and saw_no_pabotlib:
        raise DataError("Cannot use both --pabotlib and --no-pabotlib options together")

    pabot_args["argumentfiles"] = argumentfiles

    return remaining_args, pabot_args


def _delete_none_keys(d):  # type: (Dict[str, Optional[object]]) -> Dict[str, object]
    keys = set()
    for k in d:
        if d[k] is None:
            keys.add(k)
    for k in keys:
        del d[k]
    return d


def parse_execution_item_line(text):  # type: (str) -> ExecutionItem
    if text.startswith("--suite "):
        return SuiteItem(text[8:])
    if text.startswith("--test "):
        return TestItem(text[7:])
    if text.startswith("--include "):
        return IncludeItem(text[10:])
    if text.startswith("DYNAMICTEST"):
        suite, test = text[12:].split(" :: ")
        return DynamicTestItem(test, suite)
    if text.startswith("#SLEEP "):
        return SleepItem(text[7:])
    if text == "#WAIT":
        return WaitItem()
    if text == "{":
        return GroupStartItem()
    if text == "}":
        return GroupEndItem()
    # Assume old suite name
    return SuiteItem(text)
