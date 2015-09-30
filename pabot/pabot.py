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



import re
import os, sys, time, datetime
import multiprocessing
from glob import glob
from StringIO import StringIO
import shutil
import subprocess
import threading
from robot import run, rebot
from robot import __version__ as ROBOT_VERSION
from robot.api import ExecutionResult
from robot.errors import Information
from robot.result.visitor import ResultVisitor
from robot.libraries.Remote import Remote
from multiprocessing.pool import ThreadPool
from robot.run import USAGE
from robot.utils import ArgumentParser
import signal
import PabotLib
from result_merger import merge
import Queue

CTRL_C_PRESSED = False
MESSAGE_QUEUE = Queue.Queue()
_PABOTLIBURI = '127.0.0.1:8270'

class Color:
    SUPPORTED_OSES = ['posix']

    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

def execute_and_wait_with(args):
    global CTRL_C_PRESSED
    if CTRL_C_PRESSED:
        # Keyboard interrupt has happened!
        return
    time.sleep(0)
    datasources, outs_dir, options, suite_name, command, verbose = args
    datasources = [d.encode('utf-8') if isinstance(d, unicode) else d for d in datasources]
    outs_dir = os.path.join(outs_dir, suite_name)
    cmd = command + _options_for_custom_executor(options, outs_dir, suite_name) + datasources
    cmd = [c if (' ' not in c) and (';' not in c) else '"%s"' % c for c in cmd]
    os.makedirs(outs_dir)
    with open(os.path.join(outs_dir, 'stdout.txt'), 'w') as stdout:
        with open(os.path.join(outs_dir, 'stderr.txt'), 'w') as stderr:
            process, rc = _run(cmd, stderr, stdout, suite_name, verbose)
    if rc != 0:
        _write(_execution_failed_message(suite_name, rc, verbose), Color.RED)
    else:
        _write('PASSED %s' % suite_name, Color.GREEN)

def _run(cmd, stderr, stdout, suite_name, verbose):
    process = subprocess.Popen(' '.join(cmd),
                               shell=True,
                               stderr=stderr,
                               stdout=stdout)
    if verbose:
        _write('[PID:%s] EXECUTING PARALLEL SUITE %s with command:\n%s' % (process.pid, suite_name, ' '.join(cmd)))
    else:
        _write('[PID:%s] EXECUTING %s' % (process.pid, suite_name))
    rc = None
    elapsed = 0
    while rc is None:
        rc = process.poll()
        time.sleep(0.1)
        elapsed += 1
        if elapsed % 150 == 0:
            _write('[PID:%s] still running %s after %s seconds' % (process.pid, suite_name, elapsed / 10.0))
    return process, rc

def _execution_failed_message(suite_name, rc, verbose):
    if not verbose:
        return 'FAILED %s' % suite_name
    return 'Execution failed in %s with %d failing test(s)' % (suite_name, rc)

def _options_for_custom_executor(*args):
    return _options_to_cli_arguments(_options_for_executor(*args))

def _options_for_executor(options, outs_dir, suite_name):
    options = options.copy()
    options['log'] = 'NONE'
    options['report'] = 'NONE'
    options['xunit'] = 'NONE'
    options['suite'] = suite_name
    options['outputdir'] = outs_dir
    options['variable'] = options.get('variable')
    options['variable'].append('PABOTLIBURI:%s' % _PABOTLIBURI)
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
        elif isinstance(v, unicode):
            res += ['--' + str(k), v.encode('utf-8')]
        elif isinstance(v, bool) and (v is True):
            res += ['--' + str(k)]
        elif isinstance(v, list):
            for value in v:
                if isinstance(value, unicode):
                    res += ['--' + str(k), value.encode('utf-8')]
                else:
                    res += ['--' + str(k), str(value)]
    return res

class GatherSuiteNames(ResultVisitor):

      def __init__(self):
          self.result = []

      def end_suite(self, suite):
          if len(suite.tests):
             self.result.append(suite.longname)

def get_suite_names(output_file):
    if not os.path.isfile(output_file):
       return []
    try:
       e = ExecutionResult(output_file)
       gatherer = GatherSuiteNames()
       e.visit(gatherer)
       return gatherer.result
    except:
       return []

def _parse_args(args):
    pabot_args = {'command':['pybot'],
                  'verbose':False,
                  'pabotlib':False,
                  'pabotlibhost':'127.0.0.1',
                  'pabotlibport':8270,
                  'processes':max(multiprocessing.cpu_count(), 2)}
    while args and args[0] in ['--'+param for param in ['command', 'processes', 'verbose', 'resourcefile',
                                                        'pabotlib', 'pabotlibhost', 'pabotlibport']]:
        if args[0] == '--command':
            end_index = args.index('--end-command')
            pabot_args['command'] = args[1:end_index]
            args = args[end_index+1:]
        if args[0] == '--processes':
            pabot_args['processes'] = int(args[1])
            args = args[2:]
        if args[0] == '--verbose':
            pabot_args['verbose'] = True
            args = args[1:]
        if args[0] == '--resourcefile':
            pabot_args['resourcefile'] = args[1]
            args = args[2:]
        if args[0] == '--pabotlib':
            pabot_args['pabotlib'] = True
            args = args[1:]
        if args[0] == '--pabotlibhost':
            pabot_args['pabotlibhost'] = args[1]
            args = args[2:]
        if args[0] == '--pabotlibport':
            pabot_args['pabotlibport'] = int(args[1])
            args = args[2:]
    options, datasources = ArgumentParser(USAGE, auto_pythonpath=False, auto_argumentfile=False).parse_args(args)
    keys = set()
    for k in options:
        if options[k] is None:
            keys.add(k)
    for k in keys:
        del options[k]
    return options, datasources, pabot_args

def solve_suite_names(outs_dir, datasources, options):
    opts = _options_for_dryrun(options, outs_dir)
    run(*datasources, **opts)
    output = os.path.join(outs_dir, opts['output'])
    suite_names = get_suite_names(output)
    if os.path.isfile(output):
        os.remove(output)
    return sorted(set(suite_names))

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
    options['outputdir'] = outs_dir
    options['stdout'] = StringIO()
    options['stderr'] = StringIO()
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
    elapsed = end - start
    millis = int((elapsed * 1000) % 1000)
    seconds = int(elapsed) % 60
    elapsed_minutes = (int(elapsed)-seconds)/60
    minutes = elapsed_minutes % 60
    elapsed_hours = (elapsed_minutes-minutes)/60
    elapsed_string = ''
    if elapsed_hours > 0:
        elapsed_string += '%d hours ' % elapsed_hours
    elapsed_string += '%d minutes %d.%d seconds' % (minutes, seconds, millis)
    print 'Elapsed time: '+elapsed_string

def keyboard_interrupt(*args):
    global CTRL_C_PRESSED
    CTRL_C_PRESSED = True

def _parallel_execute(datasources, options, outs_dir, pabot_args, suite_names):
    original_signal_handler = signal.signal(signal.SIGINT, keyboard_interrupt)
    pool = ThreadPool(pabot_args['processes'])
    result = pool.map_async(execute_and_wait_with,
               [(datasources,
                 outs_dir,
                 options,
                 suite,
                 pabot_args['command'],
                 pabot_args['verbose'])
                for suite in suite_names])
    pool.close()
    while not result.ready():
        # keyboard interrupt is executed in main thread and needs this loop to get time to get executed
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
            if re.search("selenium-screenshot-.*\.png", file_name):
                prefix = os.path.relpath(location, pabot_outputdir)
                dst_file_name = '-'.join([prefix, file_name])
                shutil.copyfile(os.path.join(location, file_name),
                                os.path.join(outputdir, dst_file_name))


def _report_results(outs_dir, options, start_time_string, tests_root_name):
    output_path = os.path.abspath(os.path.join(options.get('outputdir', '.'), options.get('output', 'output.xml')))
    merge(sorted(glob(os.path.join(outs_dir, '**/*.xml'))), options, tests_root_name).save(output_path)
    _copy_screenshots(options)
    print 'Output:  %s' % output_path
    options['output'] = None # Do not write output again with rebot
    return rebot(output_path, **_options_for_rebot(options, start_time_string, _now()))

def _writer():
    while True:
        message = MESSAGE_QUEUE.get()
        print message

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
    t.setDaemon(True)
    t.start()

def _start_remote_library(pabot_args):
    if not pabot_args['pabotlib']:
        return None
    return subprocess.Popen('python %s %s %s %s' % (os.path.abspath(PabotLib.__file__),
                                              pabot_args.get('resourcefile', 'N/A'), pabot_args['pabotlibhost'], pabot_args['pabotlibport']),
                            shell=True)

def _stop_remote_library(process):
    print 'Stopping PabotLib process'
    Remote(_PABOTLIBURI).run_keyword('stop_remote_server', [], {})
    i = 50
    while i > 0 and process.poll() is None:
        time.sleep(0.1)
        i -= 1
    if i == 0:
        print 'Could not stop PabotLib Process in 5 seconds - calling terminate'
        process.terminate()
    else:
        print 'PabotLib process stopped'


def _get_suite_root_name(suite_names):
    top_names = [x.split('.')[0] for x in suite_names]
    if top_names.count(top_names[0]) == len(top_names):
        return top_names[0]
    return ''


def main(args):
    start_time = time.time()
    start_time_string = _now()
    lib_process = None
    #NOTE: timeout option
    try:
        _start_message_writer()
        options, datasources, pabot_args = _parse_args(args)
        global _PABOTLIBURI
        _PABOTLIBURI = pabot_args['pabotlibhost'] + ':' + str(pabot_args['pabotlibport'])
        lib_process = _start_remote_library(pabot_args)
        outs_dir = _output_dir(options)
        suite_names = solve_suite_names(outs_dir, datasources, options)
        if suite_names:
            _parallel_execute(datasources, options, outs_dir, pabot_args, suite_names)
            sys.exit(_report_results(outs_dir, options, start_time_string, _get_suite_root_name(suite_names)))
        else:
            print 'No tests to execute'
    except Information, i:
        print """A parallel executor for Robot Framework test cases. Version 0.19.

Supports all Robot Framework command line options and also following options (these must be before normal RF options):

--verbose
more output

--command [ACTUAL COMMANDS TO START ROBOT EXECUTOR] --end-command
RF script for situations where pybot is not used directly

--processes [NUMBER OF PROCESSES]
How many parallel executors to use (default max of 2 and cpu count)

--resourcefile [FILEPATH]
Indicator for a file that can contain shared variables for distributing resources.

--pabotlib
Start PabotLib remote server. This enables locking and resource distribution between parallel test executions.

--pabotlibhost [HOSTNAME]
  Host name of the PabotLib remote server (default is 127.0.0.1)

--pabotlibport [PORT]
  Port number of the PabotLib remote server (default is 8270)

Copyright 2015 Mikko Korpela - Apache 2 License
"""
        print i.message
    finally:
        if lib_process:
            _stop_remote_library(lib_process)
        _print_elapsed(start_time, time.time())


if __name__ == '__main__':
    main(sys.argv[1:])
