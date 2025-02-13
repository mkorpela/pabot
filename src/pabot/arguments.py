import multiprocessing
import re
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
    return opts, datasources, pabot_args, opts_sub


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
