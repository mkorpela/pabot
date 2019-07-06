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
Version 0.73.

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

--suitesfrom [FILEPATH TO OUTPUTXML]
  Optionally read suites from output.xml file. Failed suites will run
  first and longer running ones will be executed before shorter ones.

--argumentfile[INTEGER] [FILEPATH]
  Run same suite with multiple argumentfile options.
  For example "--argumentfile1 arg1.txt --argumentfile2 arg2.txt".

Copyright 2019 Mikko Korpela - Apache 2 License
"""

from __future__ import absolute_import, print_function

import os
import hashlib
import re
import sys
import time
import datetime
import multiprocessing
import uuid
import random
from glob import glob
from io import BytesIO, StringIO
from functools import total_ordering
import shutil
import subprocess
import threading
from contextlib import contextmanager
from robot import run, rebot
from robot import __version__ as ROBOT_VERSION
from robot.api import ExecutionResult
from robot.errors import Information, DataError
from robot.result.visitor import ResultVisitor
from robot.libraries.Remote import Remote
from multiprocessing.pool import ThreadPool
from robot.run import USAGE
from robot.utils import ArgumentParser, SYSTEM_ENCODING, is_unicode, PY2
import signal
from . import pabotlib
from .result_merger import merge

try:
    import queue
except ImportError:
    import Queue as queue

CTRL_C_PRESSED = False
MESSAGE_QUEUE = queue.Queue()
EXECUTION_POOL_IDS = []
EXECUTION_POOL_ID_LOCK = threading.Lock()
POPEN_LOCK = threading.Lock()
_PABOTLIBURI = '127.0.0.1:8270'
_PABOTLIBPROCESS = None
ARGSMATCHER = re.compile(r'--argumentfile(\d+)')
_BOURNELIKE_SHELL_BAD_CHARS_WITHOUT_DQUOTE = "!#$^&*?[(){}<>~;'`\\|= \t\n" # does not contain '"'
_BAD_CHARS_SET = set(_BOURNELIKE_SHELL_BAD_CHARS_WITHOUT_DQUOTE)
_NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0

_COMPLETED_LOCK = threading.Lock()
_NOT_COMPLETED_INDEXES = []

_ROBOT_EXTENSIONS = ['.html', '.htm', '.xhtml', '.tsv', '.rst', '.rest', '.txt', '.robot']
_ALL_ELAPSED = []

class Color:
    SUPPORTED_OSES = ['posix']

    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    YELLOW = '\033[93m'

def _mapOptionalQuote(cmdargs):
    return [arg if set(arg).isdisjoint(_BAD_CHARS_SET) else '"%s"'%arg for arg in cmdargs]
    

def execute_and_wait_with(item):
    global CTRL_C_PRESSED, _NUMBER_OF_ITEMS_TO_BE_EXECUTED
    is_last = _NUMBER_OF_ITEMS_TO_BE_EXECUTED == 1
    _NUMBER_OF_ITEMS_TO_BE_EXECUTED -= 1
    if CTRL_C_PRESSED:
        # Keyboard interrupt has happened!
        return
    time.sleep(0)
    datasources = [d.encode('utf-8') if PY2 and is_unicode(d) else d for d in item.datasources]
    
    outs_dir = os.path.join(item.outs_dir, item.argfile_index, item.execution_item.name)
    os.makedirs(outs_dir)
    
    caller_id = uuid.uuid4().hex
    cmd = item.command + _options_for_custom_executor(item.options, outs_dir, item.execution_item, item.argfile, caller_id, is_last, item.index, item.last_level) + datasources        
    cmd = _mapOptionalQuote(cmd)
    _try_execute_and_wait(cmd, outs_dir, item.execution_item.name, item.verbose, _make_id(), caller_id, item.index)
    outputxml_preprocessing(item.options, outs_dir, item.execution_item.name, item.verbose, _make_id(), caller_id)

def _try_execute_and_wait(cmd, outs_dir, item_name, verbose, pool_id, caller_id, my_index=-1):
    plib = None
    if _PABOTLIBPROCESS or _PABOTLIBURI != '127.0.0.1:8270':
        plib = Remote(_PABOTLIBURI)
    try:
        with open(os.path.join(outs_dir, cmd[0]+'_stdout.out'), 'w') as stdout:
            with open(os.path.join(outs_dir, cmd[0]+'_stderr.out'), 'w') as stderr:
                process, (rc, elapsed) = _run(cmd, stderr, stdout, item_name, verbose, pool_id)
    except:
        print(sys.exc_info()[0])
    if plib:
        _increase_completed(plib, my_index)
    # Thread-safe list append
    _ALL_ELAPSED.append(elapsed)
    if rc != 0:
        _write_with_id(process, pool_id, _execution_failed_message(item_name, stdout, stderr, rc, verbose), Color.RED)
    else:
        _write_with_id(process, pool_id, _execution_passed_message(item_name, stdout, stderr, elapsed, verbose), Color.GREEN)

        
# optionally invoke rebot for output.xml preprocessing to get --RemoveKeywords and --flattenkeywords applied => result: much smaller output.xml files + faster merging + avoid MemoryErrors
def outputxml_preprocessing(options, outs_dir, item_name, verbose, pool_id, caller_id):
    try:
        #print("debug preprocess options="+str(options))
        rk = options['removekeywords']
        fk = options['flattenkeywords']
        #print("debug preprocess rk="+str(rk)+"  fk="+str(fk))
        if not rk and not fk: return  #  => no preprocessing needed if no removekeywords or flattenkeywords present
        rkargs = []
        fkargs =  []
        for k in rk: rkargs+=['--removekeywords',k]
        for k in fk: fkargs+=['--flattenkeywords',k]
        outputxmlfile = os.path.join(outs_dir, 'output.xml')
        oldsize = os.path.getsize(outputxmlfile)
        cmd = ['rebot', '--log', 'NONE', '--report', 'NONE', '--xunit', 'NONE', '--consolecolors', 'off', '--NoStatusRC']+rkargs+fkargs+['--output', outputxmlfile, outputxmlfile]
        cmd = _mapOptionalQuote(cmd)
        
        pool_id = _make_id()
        _try_execute_and_wait(cmd, outs_dir, 'preprocessing output.xml on ' + item_name, verbose,  pool_id, caller_id)
        newsize = os.path.getsize(outputxmlfile)
        perc = 100*newsize/oldsize
        if verbose: _write("%s [main] [%s] Filesize reduced from %s to %s (%0.2f%%) for file %s" % (datetime.datetime.now(), pool_id, oldsize, newsize, perc, outputxmlfile))
    except:
        print(sys.exc_info())


def _write_with_id(process, pool_id, message, color=None, timestamp=None):
    timestamp = timestamp or datetime.datetime.now()
    _write("%s [PID:%s] [%s] %s" % (timestamp, process.pid, pool_id, message), color)


def _make_id():
    global EXECUTION_POOL_IDS, EXECUTION_POOL_ID_LOCK
    thread_id = threading.current_thread().ident
    with EXECUTION_POOL_ID_LOCK:
        if thread_id not in EXECUTION_POOL_IDS:
            EXECUTION_POOL_IDS += [thread_id]
        return EXECUTION_POOL_IDS.index(thread_id)

def _increase_completed(plib, my_index):
    global _COMPLETED_LOCK, _NOT_COMPLETED_INDEXES
    with _COMPLETED_LOCK:
        if my_index in _NOT_COMPLETED_INDEXES:
            _NOT_COMPLETED_INDEXES.remove(my_index)
        else:
            return
        if _NOT_COMPLETED_INDEXES:
            plib.run_keyword('set_parallel_value_for_key', 
            [pabotlib.PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE,
            _NOT_COMPLETED_INDEXES[0]],
            {})
        if len(_NOT_COMPLETED_INDEXES) == 1:
            plib.run_keyword('set_parallel_value_for_key', 
            ['pabot_only_last_executing', 1], {})

def _run(cmd, stderr, stdout, item_name, verbose, pool_id):
    timestamp = datetime.datetime.now()
    # isinstance(cmd,list)==True
    cmd = ' '.join(cmd)
    # isinstance(cmd,basestring if PY2 else str)==True
    if PY2:
        cmd = cmd.decode('utf-8').encode(SYSTEM_ENCODING)
    # avoid hitting https://bugs.python.org/issue10394
    with POPEN_LOCK:
        process = subprocess.Popen(cmd,
                                   shell=True,
                                   stderr=stderr,
                                   stdout=stdout)
    if verbose:
        _write_with_id(process, pool_id, 'EXECUTING PARALLEL %s with command:\n%s' % (item_name, cmd),timestamp=timestamp)
    else:
        _write_with_id(process, pool_id, 'EXECUTING %s' % item_name, timestamp=timestamp)
    return process, _wait_for_return_code(process, item_name, pool_id)


def _wait_for_return_code(process, item_name, pool_id):
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
            _write_with_id(process, pool_id, 'still running %s after %s seconds '
                                             '(next ping in %s seconds)'
                           % (item_name, elapsed / 10.0, ping_interval / 10.0))
    return rc, elapsed / 10.0

def _read_file(file_handle):
    try:
        with open(file_handle.name, 'r') as content_file:
            content = content_file.read()
        return content
    except:
        return 'Unable to read file %s' % file_handle

def _execution_failed_message(suite_name, stdout, stderr, rc, verbose):
    if not verbose:
        return 'FAILED %s' % suite_name
    return 'Execution failed in %s with %d failing test(s)\n%s\n%s' % (suite_name, rc, _read_file(stdout), _read_file(stderr))

def _execution_passed_message(suite_name, stdout, stderr, elapsed, verbose):
    if not verbose:
        return 'PASSED %s in %s seconds' % (suite_name, elapsed)
    return 'PASSED %s in %s seconds\n%s\n%s' % (suite_name, elapsed, _read_file(stdout), _read_file(stderr))

def _options_for_custom_executor(*args):
    return _options_to_cli_arguments(_options_for_executor(*args))


def _options_for_executor(options, outs_dir, execution_item, argfile, caller_id, is_last, queueIndex, last_level):
    options = options.copy()
    options['log'] = 'NONE'
    options['report'] = 'NONE'
    options['xunit'] = 'NONE'
    options[execution_item.type] = execution_item.name
    options['outputdir'] = outs_dir
    options['variable'] = options.get('variable')[:]
    options['variable'].append('CALLER_ID:%s' % caller_id)
    pabotLibURIVar = 'PABOTLIBURI:%s' % _PABOTLIBURI
    # Prevent multiple appending of PABOTLIBURI variable setting
    if pabotLibURIVar not in options['variable']:
        options['variable'].append(pabotLibURIVar)
    pabotExecutionPoolId = "PABOTEXECUTIONPOOLID:%d" % _make_id()
    if pabotExecutionPoolId not in options['variable']:
        options['variable'].append(pabotExecutionPoolId)
    pabotIsLast = 'PABOTISLASTEXECUTIONINPOOL:%s' % ('1' if is_last else '0')
    if pabotIsLast not in options['variable']:
        options['variable'].append(pabotIsLast)
    pabotIndex = pabotlib.PABOT_QUEUE_INDEX + ":" + str(queueIndex)
    if pabotIndex not in options['variable']:
        options['variable'].append(pabotIndex)
    if last_level is not None:
        pabotLastLevel = pabotlib.PABOT_LAST_LEVEL + ":" + str(last_level)
        if pabotLastLevel not in options['variable']:
            options['variable'].append(pabotLastLevel)
    if argfile:
        options['argumentfile'] = argfile
    return _set_terminal_coloring_options(options)


def _set_terminal_coloring_options(options):
    if ROBOT_VERSION >= '2.9':
        options['consolecolors'] = 'off'
        options['consolemarkers'] = 'off'
    else:
        options['monitorcolors'] = 'off'
    if ROBOT_VERSION >= '2.8' and ROBOT_VERSION < '2.9':
        options['monitormarkers'] = 'off'
    return options


def _options_to_cli_arguments(opts):
    res = []
    for k, v in opts.items():
        if isinstance(v, str):
            res += ['--' + str(k), str(v)]
        elif PY2 and is_unicode(v):
            res += ['--' + str(k), v.encode('utf-8')]
        elif isinstance(v, bool) and (v is True):
            res += ['--' + str(k)]
        elif isinstance(v, list):
            for value in v:
                if PY2 and is_unicode(value):
                    res += ['--' + str(k), value.encode('utf-8')]
                else:
                    res += ['--' + str(k), str(value)]
    return res


class GatherSuiteNames(ResultVisitor):
    def __init__(self):
        self.result = []

    def end_suite(self, suite):
        if len(suite.tests):
            self.result.append(SuiteItem(suite.longname, tests=[t.longname for t in suite.tests]))


def get_suite_names(output_file):
    if not os.path.isfile(output_file):
        print("get_suite_names: output_file='%s' does not exist" % output_file)
        return []
    try:
        e = ExecutionResult(output_file)
        gatherer = GatherSuiteNames()
        e.visit(gatherer)
        return gatherer.result
    except:
        print("Exception in get_suite_names!")
        return []


def _processes_count():
    try:
        return max(multiprocessing.cpu_count(), 2)
    except NotImplementedError:
        return 2


def _parse_args(args):
    pabot_args = {'command': ['pybot' if ROBOT_VERSION < '3.1' else 'robot'],
                  'verbose': False,
                  'tutorial': False,
                  'help': False,
                  'testlevelsplit': False,
                  'pabotlib': False,
                  'pabotlibhost': '127.0.0.1',
                  'pabotlibport': 8270,
                  'processes': _processes_count(),
                  'argumentfiles': []}
    while args and (args[0] in ['--' + param for param in ['command',
                                                           'processes',
                                                           'verbose',
                                                           'tutorial',
                                                           'resourcefile',
                                                           'testlevelsplit',
                                                           'pabotlib',
                                                           'pabotlibhost',
                                                           'pabotlibport',
                                                           'suitesfrom',
                                                           'help']] or
                        ARGSMATCHER.match(args[0])):
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
        match = ARGSMATCHER.match(args[0])
        if ARGSMATCHER.match(args[0]):
            pabot_args['argumentfiles'] += [(match.group(1), args[1])]
            args = args[2:]
            continue
        if args[0] == '--tutorial':
            pabot_args['tutorial'] = True
            args = args[1:]
            continue
        if args and args[0] == '--help':
            pabot_args['help'] = True
            args = args[1:]
    options, datasources = ArgumentParser(USAGE,
                                          auto_pythonpath=False,
                                          auto_argumentfile=True,
                                          env_options='ROBOT_OPTIONS'). \
        parse_args(args)
    options_for_subprocesses, _ = ArgumentParser(USAGE,
                                          auto_pythonpath=False,
                                          auto_argumentfile=False,
                                          env_options='ROBOT_OPTIONS'). \
        parse_args(args)
    if len(datasources) > 1 and options['name'] is None:
        options['name'] = 'Suites'
        options_for_subprocesses['name'] = 'Suites'
    _delete_none_keys(options)
    _delete_none_keys(options_for_subprocesses)
    return options, datasources, pabot_args, options_for_subprocesses

def _delete_none_keys(d):
    keys = set()
    for k in d:
        if d[k] is None:
            keys.add(k)
    for k in keys:
        del d[k]

def hash_directory(digest, path):
    if os.path.isfile(path):
        digest.update(hashlib.sha1(path.encode()).digest())
        get_hash_of_file(path, digest)
        return
    for root, _, files in os.walk(path):
        for name in sorted(files):
            file_path = os.path.join(root, name)
            if os.path.isfile(file_path) and \
                any(file_path.endswith(p) for p in _ROBOT_EXTENSIONS):
                # DO NOT ALLOW CHANGE TO FILE LOCATION
                digest.update(hashlib.sha1(root.encode()).digest())
                # DO THESE IN TWO PHASES BECAUSE SEPARATOR DIFFERS IN DIFFERENT OS
                digest.update(hashlib.sha1(name.encode()).digest())
                get_hash_of_file(file_path, digest)

def get_hash_of_file(filename, digest):
    if not os.path.isfile(filename):
        return
    with open(filename, 'rb') as f_obj:
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
    "tagdoc"
]

def get_hash_of_command(options, pabot_args):
    digest = hashlib.sha1()
    hopts = dict(options)
    for option in options:
        if (option in IGNORED_OPTIONS or
            options[option] == []):
            del hopts[option]
    if pabot_args.get('testlevelsplit'):
        hopts['testlevelsplit'] = True
    digest.update(repr(sorted(hopts.items())).encode("utf-8"))
    return digest.hexdigest()

def solve_suite_names(outs_dir, datasources, options, pabot_args):
    hash_of_dirs = get_hash_of_dirs(datasources)
    hash_of_command = get_hash_of_command(options, pabot_args)
    hash_of_suitesfrom = "no-suites-from-option"
    if "suitesfrom" in pabot_args:
        digest = hashlib.sha1()
        get_hash_of_file(pabot_args["suitesfrom"], digest)
        hash_of_suitesfrom = digest.hexdigest()
    try:
        if not os.path.isfile(".pabotsuitenames"):
            suite_names = generate_suite_names(outs_dir, 
                                            datasources, 
                                            options, 
                                            pabot_args)
            store_suite_names(hash_of_dirs, 
                        hash_of_command, 
                        hash_of_suitesfrom, 
                        suite_names)
            return [suite_names]
        with open(".pabotsuitenames", "r") as suitenamesfile:
            lines = [line.strip() for line in suitenamesfile.readlines()]
            corrupted = len(lines) < 5
            if not corrupted:
                hash_suites = lines[0][len("datasources:"):]
                hash_command = lines[1][len("commandlineoptions:"):]
                suitesfrom_hash = lines[2][len("suitesfrom:"):]
                file_hash = lines[3][len("file:"):]
                hash_of_file = _file_hash(lines)
            else:
                hash_suites = None
                hash_command = None
                suitesfrom_hash = None
                file_hash = None
                hash_of_file = None
            corrupted = corrupted or any(not l.startswith('--suite ') and
                                        not l.startswith('--test ') and
                                        l != '#WAIT' for l in lines[4:])
            execution_item_lines = [_parse_line(l) for l in lines[4:]]
            if (corrupted or
            hash_suites != hash_of_dirs or 
            hash_command != hash_of_command or
            file_hash != hash_of_file or
            suitesfrom_hash != hash_of_suitesfrom):
                return _group_by_wait(_regenerate(suitesfrom_hash, 
                                        hash_of_suitesfrom,
                                        pabot_args,
                                        hash_suites,
                                        hash_of_dirs,
                                        outs_dir,
                                        datasources,
                                        options,
                                        execution_item_lines,
                                        hash_of_command))
        return _group_by_wait(execution_item_lines)
    except IOError:
        return  [generate_suite_names_with_dryrun(outs_dir, datasources, options)]


@total_ordering
class ExecutionItem(object):

    isWait = False

    def top_name(self):
        return self.name.split('.')[0]

    def contains(self, other):
        return False

    def __eq__(self, other):
        if isinstance(other, ExecutionItem):
            return ((self.name, self.type) == (other.name, other.type))
        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return ((self.name, self.type) < (other.name, other.type))

    def __hash__(self):
        return hash(self.name) | hash(self.type)

    def __repr__(self):
        return "<" + self.type + ":" + self.name + ">"


class SuiteItem(ExecutionItem):

    type = 'suite'

    def __init__(self, name, tests=None, suites=None):
        assert(isinstance(name, str))
        self.name = name
        self.tests = [TestItem(t) for t in tests or []]
        self.suites = [SuiteItem(s) for s in suites or []]

    def line(self):
        return '--suite '+self.name

    def difference(self, from_items):
        if self.tests:
            return [t for t in self.tests if t not in from_items]
        if self.suites:
            return [s for s in self.suites if s not in from_items]
        return []

    def contains(self, other):
        if self == other:
            return True
        return other.name.startswith(self.name+".")

    def tags(self):
        #TODO Make this happen
        return []


class TestItem(ExecutionItem):

    type = 'test'

    def __init__(self, name):
        self.name = name

    def line(self):
        return '--test '+self.name

    def difference(self, from_items):
        return []

    def contains(self, other):
        return self == other

    def tags(self):
        #TODO Make this happen
        return []


class WaitItem(ExecutionItem):

    type = "wait"
    isWait = True

    def __init__(self):
        self.name = "#WAIT"

    def line(self):
        return self.name


class IncludeItem(ExecutionItem):

    type = "include"
    
    def __init__(self, tag):
        self.name = tag

    def line(self):
        return '--include '+self.name

    def contains(self, other):
        return self.name in other.tags()

    def tags(self):
        return [self.name]


def _parse_line(text):
    if text.startswith('--suite '):
        return SuiteItem(text[8:])
    if text.startswith('--test '):
        return TestItem(text[7:])
    if text.startswith('--include '):
        return IncludeItem(text[10:])
    if text == "#WAIT":
        return WaitItem()
    # Assume old suite name
    return SuiteItem(text)


def _group_by_wait(lines):
    suites = [[]]
    for suite in lines:
        if not suite.isWait:
            if suite:
                suites[-1].append(suite)
        else:
            suites.append([])
    return suites

def _regenerate(
    suitesfrom_hash, 
    hash_of_suitesfrom,
    pabot_args,
    hash_suites,
    hash_of_dirs,
    outs_dir,
    datasources,
    options,
    lines,
    hash_of_command):
    assert(all(isinstance(s, ExecutionItem) for s in lines))
    if suitesfrom_hash != hash_of_suitesfrom \
        and 'suitesfrom' in pabot_args \
        and os.path.isfile(pabot_args['suitesfrom']):
        suites = _suites_from_outputxml(pabot_args['suitesfrom'])
        if hash_suites != hash_of_dirs:
            all_suites = generate_suite_names_with_dryrun(outs_dir, datasources, options)
        else:
            all_suites = [suite for suite in lines if suite]
        suites = _preserve_order(all_suites, suites) 
    else:
        suites = generate_suite_names_with_dryrun(outs_dir, datasources, options)
        if pabot_args.get('testlevelsplit'):
            tests = []
            for s in suites:
                tests.extend(s.tests)
            suites = tests
        suites = _preserve_order(suites, [suite for suite in lines if suite])
    if suites:
        store_suite_names(hash_of_dirs, hash_of_command, hash_of_suitesfrom, suites)
    assert(all(isinstance(s, ExecutionItem) for s in suites))
    return suites

def _contains_suite_and_test(suites):
    return any(isinstance(s, SuiteItem) for s in suites) and \
        any(isinstance(t, TestItem) for t in suites)


def _preserve_order(new_items, old_items):
    assert(all(isinstance(s, ExecutionItem) for s in new_items))
    assert(all(isinstance(s, ExecutionItem) for s in old_items))
    old_contains_tests = any(isinstance(t, TestItem) for t in old_items)
    old_contains_suites = any(isinstance(s, SuiteItem) for s in old_items)
    old_items = _fix_items(old_items)
    new_contains_tests = any(isinstance(t, TestItem) for t in new_items)
    if old_contains_tests and old_contains_suites and not new_contains_tests:
        new_items = _split_partially_to_tests(new_items, old_items)
    #TODO: Preserving order when suites => tests OR tests => suites
    preserve, ignorable = _get_preserve_and_ignore(
        new_items, old_items, 
        old_contains_tests and old_contains_suites)
    exists_in_old_and_new = [s for s in old_items
                if (s in new_items and s not in ignorable)
                or s in preserve]
    exists_only_in_new = [s for s in new_items
                if s not in old_items and s not in ignorable]
    return _fix_items(exists_in_old_and_new + exists_only_in_new)


def _fix_items(items):
    assert(all(isinstance(s, ExecutionItem) for s in items))
    to_be_removed = []
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            if items[i].contains(items[j]):
                to_be_removed.append(j)
    items = [item for i, item in enumerate(items) if i not in to_be_removed]
    result = []
    to_be_splitted = {}
    for i in range(len(items)):
        if i in to_be_splitted:
            result.extend(items[i].difference(to_be_splitted[i]))
        else:
            result.append(items[i])
        for j in range(i+1, len(items)):
            if items[j].contains(items[i]):
                if j not in to_be_splitted:
                    to_be_splitted[j] = []
                to_be_splitted[j].append(items[i])
    _remove_double_waits(result)
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
            if old_item.contains(new_item) and new_item != old_item and \
                (isinstance(new_item, SuiteItem) or old_contains_suites_and_tests):
                preserve.append(old_item)
                ignorable.append(new_item)
        if old_item.isWait:
            preserve.append(old_item)
    preserve = [new_item for new_item in preserve 
        if not any([i.contains(new_item) and i != new_item for i in preserve])]
    return preserve, ignorable


def _remove_double_waits(exists_in_old_and_new):
    doubles = []
    for i,(j,k) in enumerate(zip(exists_in_old_and_new, exists_in_old_and_new[1:])):
        if j.isWait and k == j:
            doubles.append(i)
    for i in reversed(doubles):
        del exists_in_old_and_new[i]

def _split_partially_to_tests(new_suites, old_suites):
    suits = []
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
        if line != '#WAIT':
            hashes ^= int(hashlib.sha1(line.encode()).hexdigest(), 16)
    digest.update(str(hashes).encode())
    return digest.hexdigest()

def store_suite_names(hash_of_dirs, hash_of_command, hash_of_suitesfrom, suite_names):
    assert(all(isinstance(s, ExecutionItem) for s in suite_names))
    suite_lines = [s.line() for s in suite_names]
    _write("Storing .pabotsuitenames file")
    with open(".pabotsuitenames", "w") as suitenamesfile:
        suitenamesfile.write("datasources:"+hash_of_dirs+'\n')
        suitenamesfile.write("commandlineoptions:"+hash_of_command+'\n')
        suitenamesfile.write("suitesfrom:"+hash_of_suitesfrom+'\n')
        suitenamesfile.write("file:"+_file_hash([
            "datasources:"+hash_of_dirs, 
            "commandlineoptions:"+hash_of_command, 
            "suitesfrom:"+hash_of_suitesfrom, None]+ suite_lines)+'\n')
        suitenamesfile.writelines(suite_name+'\n' for suite_name in suite_lines)

def generate_suite_names(outs_dir, datasources, options, pabot_args):
    suites = []
    if 'suitesfrom' in pabot_args and os.path.isfile(pabot_args['suitesfrom']):
        suites = _suites_from_outputxml(pabot_args['suitesfrom'])
    else:
        suites = generate_suite_names_with_dryrun(outs_dir, datasources, options)
    if pabot_args.get('testlevelsplit'):
        tests = []
        for s in suites:
            tests.extend(s.tests)
        return tests
    return suites

def generate_suite_names_with_dryrun(outs_dir, datasources, options):
    opts = _options_for_dryrun(options, outs_dir)
    with _with_modified_robot():
        run(*datasources, **opts)
    output = os.path.join(outs_dir, opts['output'])
    suite_names = get_suite_names(output)
    if not suite_names and not options.get('runemptysuite', False):
        stdout_value = opts['stdout'].getvalue()
        if stdout_value:
            _write("[STDOUT] from suite search:\n"+stdout_value+"[STDOUT] end", Color.YELLOW)
        stderr_value = opts['stderr'].getvalue()
        if stderr_value:
            _write("[STDERR] from suite search:\n"+stderr_value+"[STDERR] end", Color.RED)
    return list(sorted(set(suite_names)))


@contextmanager
def _with_modified_robot():
    RobotReader = None
    TsvReader = None
    old_read = None
    try:
        # RF 3.1
        from robot.parsing.robotreader import RobotReader, Utf8Reader

        # RF 3.1.2
        if "_process_row" not in dir(RobotReader):
            def new_read(self, file, populator, path=None):
                path = path or getattr(file, 'name', '<file-like object>')
                process = False
                first = True
                for lineno, line in enumerate(Utf8Reader(file).readlines(), start=1):
                    cells = self.split_row(line.rstrip())
                    cells = list(self._check_deprecations(cells, path, lineno))
                    if cells and cells[0].strip().startswith('*') and \
                            populator.start_table([c.replace('*', '').strip()
                                                for c in cells]):
                        process = True
                    elif process:
                        if cells[0].strip() != '' or \
                                (len(cells) > 1 and
                                    ('[' in cells[1] or (first and '...' in cells[1]))):
                            populator.add(cells)
                            first = True
                        elif first and not (len(cells) == 1 and cells[0].strip() == ''):
                            populator.add(['', 'No Operation'])
                            first = False
                return populator.eof()

        else:
            def new_read(self, file, populator, path=None):
                path = path or getattr(file, 'name', '<file-like object>')
                process = False
                first = True
                for row in Utf8Reader(file).readlines():
                    row = self._process_row(row)
                    cells = [self._process_cell(cell, path) for cell in self.split_row(row)]
                    self._deprecate_empty_data_cells_in_tsv_format(cells, path)
                    if cells and cells[0].strip().startswith('*') and \
                            populator.start_table([c.replace('*', '') for c in cells]):
                        process = True
                    elif process:
                        if cells[0].strip() != '' or \
                                (len(cells) > 1 and
                                    ('[' in cells[1] or (first and '...' in cells[1]))):
                            populator.add(cells)
                            first = True
                        elif first:
                            populator.add(['', 'No Operation'])
                            first = False
                return populator.eof()

        old_read = RobotReader.read
        RobotReader.read = new_read
    except ImportError:
        # RF 3.0
        from robot.parsing.tsvreader import TsvReader, Utf8Reader

        def new_read(self, tsvfile, populator):
            process = False
            first = True
            for row in Utf8Reader(tsvfile).readlines():
                row = self._process_row(row)
                cells = [self._process_cell(cell)
                         for cell in self.split_row(row)]
                if cells and cells[0].strip().startswith('*') and \
                        populator.start_table([c.replace('*', '')
                                               for c in cells]):
                    process = True
                elif process:
                    if cells[0].strip() != '' or \
                            (len(cells) > 1 and
                                 ('[' in cells[1] or (first and '...' in cells[1]))):
                        populator.add(cells)
                        first = True
                    elif first:
                        populator.add(['', 'No Operation'])
                        first = False
            populator.eof()

        old_read = TsvReader.read
        TsvReader.read = new_read
    except:
        pass

    try:
        yield
    finally:
        if RobotReader:
            RobotReader.read = old_read
        if TsvReader:
            TsvReader.read = old_read


class SuiteNotPassingsAndTimes(ResultVisitor):
    def __init__(self):
        self.suites = []

    def start_suite(self, suite):
        if len(suite.tests) > 0:
            self.suites.append((not suite.passed,
                                suite.elapsedtime,
                                suite.longname))


def _suites_from_outputxml(outputxml):
    res = ExecutionResult(outputxml)
    suite_times = SuiteNotPassingsAndTimes()
    res.visit(suite_times)
    return [SuiteItem(suite) for (_, _, suite) in reversed(sorted(suite_times.suites))]


def _options_for_dryrun(options, outs_dir):
    options = options.copy()
    options['log'] = 'NONE'
    options['report'] = 'NONE'
    options['xunit'] = 'NONE'
    if ROBOT_VERSION >= '2.8':
        options['dryrun'] = True
    else:
        options['runmode'] = 'DryRun'
    options['output'] = 'suite_names.xml'
    # --timestampoutputs is not compatible with hard-coded suite_names.xml
    options['timestampoutputs'] = False
    options['outputdir'] = outs_dir
    if PY2:
        options['stdout'] = BytesIO()
        options['stderr'] = BytesIO()
    else:
        options['stdout'] = StringIO()
        options['stderr'] = StringIO()
    options['listener'] = []
    return _set_terminal_coloring_options(options)


def _options_for_rebot(options, start_time_string, end_time_string):
    rebot_options = options.copy()
    rebot_options['starttime'] = start_time_string
    rebot_options['endtime'] = end_time_string
    rebot_options['monitorcolors'] = 'off'
    if ROBOT_VERSION >= '2.8':
        options['monitormarkers'] = 'off'
    return rebot_options


def _now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')


def _print_elapsed(start, end):
    _write('Total testing: ' + _time_string(sum(_ALL_ELAPSED)) + '\nElapsed time:  ' + _time_string(end-start))

def _time_string(elapsed):
    millis = int((elapsed * 100) % 100)
    seconds = int(elapsed) % 60
    elapsed_minutes = (int(elapsed) - seconds) / 60
    minutes = elapsed_minutes % 60
    elapsed_hours = (elapsed_minutes - minutes) / 60
    elapsed_string = ''
    if elapsed_hours > 0:
        plural = ''
        if elapsed_hours > 1:
            plural = 's'
        elapsed_string += ('%d hour' % elapsed_hours) +plural + ' '
    if minutes > 0:
        plural = ''
        if minutes > 1:
            plural = 's'
        elapsed_string += ('%d minute' % minutes) + plural + ' '
    return elapsed_string + '%d.%d seconds' % (seconds, millis)


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
    outputdir = options.get('outputdir', '.')
    outpath = os.path.join(outputdir, 'pabot_results')
    if cleanup and os.path.isdir(outpath):
        shutil.rmtree(outpath)
    return outpath


def _copy_screenshots(options):
    pabot_outputdir = _output_dir(options, cleanup=False)
    outputdir = options.get('outputdir', '.')
    for location, dir_names, file_names in os.walk(pabot_outputdir):
        for file_name in file_names:
            # We want ALL screenshots copied, not just selenium ones!
            if file_name.endswith(".png"):
                prefix = os.path.relpath(location, pabot_outputdir)
                # But not .png files in any sub-folders of "location"
                if os.sep in prefix:
                    continue
                dst_file_name = '-'.join([prefix, file_name])
                shutil.copyfile(os.path.join(location, file_name),
                                os.path.join(outputdir, dst_file_name))


def _report_results(outs_dir, pabot_args, options, start_time_string, tests_root_name):
    if pabot_args['argumentfiles']:
        outputs = []
        for index, _ in pabot_args['argumentfiles']:
            outputs += [_merge_one_run(os.path.join(outs_dir, index), options, tests_root_name,
                                       outputfile=os.path.join('pabot_results', 'output%s.xml' % index))]
            _copy_screenshots(options)
        options['output'] = 'output.xml'
        return rebot(*outputs, **_options_for_rebot(options,
                                                    start_time_string, _now()))
    else:
        return _report_results_for_one_run(outs_dir, options, start_time_string, tests_root_name)


def _report_results_for_one_run(outs_dir, options, start_time_string, tests_root_name):
    output_path = _merge_one_run(outs_dir, options, tests_root_name)
    _copy_screenshots(options)
    if ('report' in options and options['report'] == "NONE" and
        'log' in options and options['log'] == "NONE"):
        options['output'] = output_path #REBOT will return error 252 if nothing is written
    else:
        print('Output:  %s' % output_path)
        options['output'] = None  # Do not write output again with rebot
    return rebot(output_path, **_options_for_rebot(options,
                                                   start_time_string, _now()))


def _merge_one_run(outs_dir, options, tests_root_name, outputfile='output.xml'):
    output_path = os.path.abspath(os.path.join(
        options.get('outputdir', '.'),
        options.get('output', outputfile)))
    files = sorted(glob(os.path.join(_glob_escape(outs_dir), '**/*.xml')))
    if not files:
        _write('WARN: No output files in "%s"' % outs_dir, Color.YELLOW)
        return ""
    merge(files, options, tests_root_name).save(output_path)
    return output_path


# This is from https://github.com/django/django/blob/master/django/utils/glob.py
_magic_check = re.compile('([*?[])')


def _glob_escape(pathname):
    """
    Escape all special characters.
    """
    drive, pathname = os.path.splitdrive(pathname)
    pathname = _magic_check.sub(r'[\1]', pathname)
    return drive + pathname


def _writer():
    while True:
        message = MESSAGE_QUEUE.get()
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
    t.daemon = True
    t.start()


def _stop_message_writer():
    MESSAGE_QUEUE.join()


def _start_remote_library(pabot_args):
    global _PABOTLIBURI
    _PABOTLIBURI = '%s:%s' % (pabot_args['pabotlibhost'],
                              pabot_args['pabotlibport'])
    if not pabot_args['pabotlib']:
        return None
    if pabot_args.get('resourcefile') and not os.path.exists(
            pabot_args['resourcefile']):
        _write('Warning: specified resource file doesn\'t exist.'
               ' Some tests may fail or continue forever.', Color.YELLOW)
        pabot_args['resourcefile'] = None
    return subprocess.Popen('\"{python}\" \"{pabotlibpath}\" {resourcefile} {pabotlibhost} {pabotlibport}'.format(
        python=sys.executable,
        pabotlibpath=os.path.abspath(pabotlib.__file__),
        resourcefile=pabot_args.get('resourcefile'),
        pabotlibhost=pabot_args['pabotlibhost'],
        pabotlibport=pabot_args['pabotlibport']),
        shell=True)


def _stop_remote_library(process):
    _write('Stopping PabotLib process')
    try:
        Remote(_PABOTLIBURI).run_keyword('stop_remote_server', [], {})
    except RuntimeError:
        _write('Could not connect to PabotLib - assuming stopped already')
        return
    i = 50
    while i > 0 and process.poll() is None:
        time.sleep(0.1)
        i -= 1
    if i == 0:
        _write('Could not stop PabotLib Process in 5 seconds ' \
               '- calling terminate', Color.YELLOW)
        process.terminate()
    else:
        _write('PabotLib process stopped')


def _get_suite_root_name(suite_names):
    top_names = [x.top_name() for group in suite_names for x in group]
    if top_names and top_names.count(top_names[0]) == len(top_names):
        return top_names[0]
    return ''


def _run_tutorial():
    print('Hi, This is a short introduction to using Pabot.')
    user_input = raw_input if PY2 else input
    user_input("Press Enter to continue...")
    print('This is another line in the tutorial.')


class QueueItem(object):

    def __init__(self, datasources, outs_dir, options, execution_item, command, verbose, argfile):
        self.datasources = datasources
        self.outs_dir = outs_dir
        self.options = options
        self.execution_item = execution_item
        self.command = command
        self.verbose = verbose
        self.argfile_index = argfile[0]
        self.argfile = argfile[1]
        self.index = -1
        self.last_level = None


def _create_execution_items(suite_names, datasources, outs_dir, options, opts_for_run, pabot_args):
    global _NUMBER_OF_ITEMS_TO_BE_EXECUTED, _COMPLETED_LOCK, _NOT_COMPLETED_INDEXES
    all_items = []
    _NUMBER_OF_ITEMS_TO_BE_EXECUTED = 0
    for suite_group in suite_names:
        #TODO: Fix this better
        if options.get("randomize") in ["all", "suites"] and \
            "suitesfrom" not in pabot_args:
            random.shuffle(suite_group)
        items = [QueueItem(datasources, outs_dir, opts_for_run, suite,
            pabot_args['command'], pabot_args['verbose'], argfile)
            for suite in suite_group
            for argfile in pabot_args['argumentfiles'] or [("", None)]]
        _NUMBER_OF_ITEMS_TO_BE_EXECUTED += len(items)
        all_items.append(items)
    with _COMPLETED_LOCK:
        index = 0
        for item_group in all_items:
            for item in item_group:
                _NOT_COMPLETED_INDEXES.append(index)
                item.index = index
                index += 1
    _construct_last_levels(all_items)
    return all_items

def _find_ending_level(name, group):
    n = name.split(".")
    level = -1
    for other in group:
        o = other.split(".")
        dif = [i for i in range(min(len(o), len(n))) if o[i] != n[i]]
        if dif:
            level = max(dif[0], level)
        else:
            return name+".PABOT_noend"
    return ".".join(n[:(level+1)])

def _construct_last_levels(all_items):
    names = []
    for items in all_items:
        for item in items:
            names.append(item.execution_item.name)
    for items in all_items:
        for item in items:
            item.last_level = _find_ending_level(item.execution_item.name, names[item.index+1:])

def _initialize_queue_index():
    global _PABOTLIBURI
    plib = Remote(_PABOTLIBURI)
    # INITIALISE PARALLEL QUEUE MIN INDEX
    for i in range(300):
        try:
            plib.run_keyword('set_parallel_value_for_key', 
            [pabotlib.PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE, 0], {})
            return
        except RuntimeError as e:
            # REMOTE LIB NOT YET CONNECTED
            time.sleep(0.1)
    raise RuntimeError('Can not connect to PabotLib at %s' % _PABOTLIBURI)


def main(args=None):
    global _PABOTLIBPROCESS
    args = args or sys.argv[1:]
    start_time = time.time()
    start_time_string = _now()
    # NOTE: timeout option
    try:
        _start_message_writer()
        options, datasources, pabot_args, opts_for_run = _parse_args(args)
        if pabot_args['tutorial']:
            _run_tutorial()
            sys.exit(0)
        if pabot_args['help']:
            print(__doc__)
            sys.exit(0)
        _PABOTLIBPROCESS = _start_remote_library(pabot_args)
        if _PABOTLIBPROCESS or _PABOTLIBURI != '127.0.0.1:8270':
            _initialize_queue_index()
        outs_dir = _output_dir(options)
        suite_names = solve_suite_names(outs_dir, datasources, options,
                                        pabot_args)
        if suite_names and suite_names != [[]]:
            for items in _create_execution_items(
                suite_names, datasources, outs_dir, 
                options, opts_for_run, pabot_args):
                _parallel_execute(items, pabot_args['processes'])
            sys.exit(_report_results(outs_dir, pabot_args, options, start_time_string,
                                     _get_suite_root_name(suite_names)))
        else:
            _write('No tests to execute')
            if not options.get('runemptysuite', False):
                sys.exit(252)
    except Information as i:
        print(__doc__)
        print(i.message)
    except DataError as err:
        print(err.message)
    except Exception:
        _write("[ERROR] EXCEPTION RAISED DURING PABOT EXECUTION", Color.RED)
        _write("[ERROR] PLEASE CONSIDER REPORTING THIS ISSUE TO https://github.com/mkorpela/pabot/issues", Color.RED)
        raise
    finally:
        if _PABOTLIBPROCESS:
            _stop_remote_library(_PABOTLIBPROCESS)
        _print_elapsed(start_time, time.time())
        _stop_message_writer()


if __name__ == '__main__':
    main()
