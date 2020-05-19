import multiprocessing
import re
from typing import Optional, List, Dict, Tuple

from robot import __version__ as ROBOT_VERSION
from robot.errors import DataError
from robot.run import USAGE
from robot.utils import ArgumentParser

from .execution_items import SuiteItem, TestItem, IncludeItem, DynamicTestItem, WaitItem, GroupStartItem, \
    GroupEndItem, ExecutionItem

ARGSMATCHER = re.compile(r'--argumentfile(\d+)')


def _processes_count():  # type: () -> int
    try:
        return max(multiprocessing.cpu_count(), 2)
    except NotImplementedError:
        return 2


def parse_args(args):  # type: (List[str]) -> Tuple[Dict[str, object], List[str], Dict[str, object], Dict[str, object]]
    args, pabot_args = _parse_pabot_args(args)
    options, datasources = ArgumentParser(USAGE,
                                          auto_pythonpath=False,
                                          auto_argumentfile=True,
                                          env_options='ROBOT_OPTIONS'). \
        parse_args(args)
    options_for_subprocesses, sources_without_argfile = ArgumentParser(USAGE,
                                          auto_pythonpath=False,
                                          auto_argumentfile=False,
                                          env_options='ROBOT_OPTIONS'). \
        parse_args(args)
    if len(datasources) != len(sources_without_argfile):
        raise DataError('Pabot does not support datasources in argumentfiles.\nPlease move datasources to commandline.')
    if len(datasources) > 1 and options['name'] is None:
        options['name'] = 'Suites'
        options_for_subprocesses['name'] = 'Suites'
    opts = _delete_none_keys(options)
    opts_sub = _delete_none_keys(options_for_subprocesses)
    return opts, datasources, pabot_args, opts_sub


def _parse_pabot_args(args):  # type: (List[str]) -> Tuple[List[str], Dict[str, object]]
    pabot_args = {'command': ['pybot' if ROBOT_VERSION < '3.1' else 'robot'],
                  'verbose': False,
                  'help': False,
                  'testlevelsplit': False,
                  'pabotlib': False,
                  'pabotlibhost': '127.0.0.1',
                  'pabotlibport': 8270,
                  'processes': _processes_count(),
                  'artifacts': ['png'],
                  'artifactsinsubfolders': False}
    argumentfiles = []
    while args and (args[0] in ['--' + param for param in ['hive',
                                                           'command',
                                                           'processes',
                                                           'verbose',
                                                           'resourcefile',
                                                           'testlevelsplit',
                                                           'pabotlib',
                                                           'pabotlibhost',
                                                           'pabotlibport',
                                                           'ordering',
                                                           'suitesfrom',
                                                           'artifacts',
                                                           'artifactsinsubfolders',
                                                           'help']] or
                    ARGSMATCHER.match(args[0])):
        if args[0] == '--hive':
            pabot_args['hive'] = args[1]
            args = args[2:]
            continue
        if args[0] == '--command':
            end_index = args.index('--end-command')
            pabot_args['command'] = args[1:end_index]
            args = args[end_index + 1:]
            continue
        if args[0] == '--processes':
            pabot_args['processes'] = int(args[1])
            args = args[2:]
            continue
        if args[0] == '--verbose':
            pabot_args['verbose'] = True
            args = args[1:]
            continue
        if args[0] == '--resourcefile':
            pabot_args['resourcefile'] = args[1]
            args = args[2:]
            continue
        if args[0] == '--pabotlib':
            pabot_args['pabotlib'] = True
            args = args[1:]
            continue
        if args[0] == '--ordering':
            pabot_args['ordering'] = _parse_ordering(args[1])
            args = args[2:]
            continue
        if args[0] == '--testlevelsplit':
            pabot_args['testlevelsplit'] = True
            args = args[1:]
            continue
        if args[0] == '--pabotlibhost':
            pabot_args['pabotlibhost'] = args[1]
            args = args[2:]
            continue
        if args[0] == '--pabotlibport':
            pabot_args['pabotlibport'] = int(args[1])
            args = args[2:]
            continue
        if args[0] == '--suitesfrom':
            pabot_args['suitesfrom'] = args[1]
            args = args[2:]
            continue
        if args[0] == '--artifacts':
            pabot_args['artifacts'] = args[1].split(',')
            args = args[2:]
            continue
        if args[0] == '--artifactsinsubfolders':
            pabot_args['artifactsinsubfolders'] = True
            args = args[1:]
            continue
        match = ARGSMATCHER.match(args[0])
        if match:
            argumentfiles += [(match.group(1), args[1])]
            args = args[2:]
            continue
        if args and args[0] == '--help':
            pabot_args['help'] = True
            args = args[1:]
    pabot_args['argumentfiles'] = argumentfiles
    return args, pabot_args


def _parse_ordering(filename):  # type: (str) -> List[ExecutionItem]
    try:
        with open(filename, "r") as orderingfile:
            return [parse_execution_item_line(line.strip()) for line in orderingfile.readlines()]
    except:
        raise DataError("Error parsing ordering file '%s'" % filename)


def _delete_none_keys(d):  # type: (Dict[str, Optional[object]]) -> Dict[str, object]
    keys = set()
    for k in d:
        if d[k] is None:
            keys.add(k)
    for k in keys:
        del d[k]
    return d


def parse_execution_item_line(text):  # type: (str) -> ExecutionItem
    if text.startswith('--suite '):
        return SuiteItem(text[8:])
    if text.startswith('--test '):
        return TestItem(text[7:])
    if text.startswith('--include '):
        return IncludeItem(text[10:])
    if text.startswith('DYNAMICTEST'):
        suite, test = text[12:].split(" :: ")
        return DynamicTestItem(test, suite)
    if text == "#WAIT":
        return WaitItem()
    if text == "{":
        return GroupStartItem()
    if text == "}":
        return GroupEndItem()
    # Assume old suite name
    return SuiteItem(text)