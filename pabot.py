#!/usr/bin/env python
import os, sys
import multiprocessing
from glob import glob
from StringIO import StringIO
import shutil
import subprocess
from robot import run, rebot
from robot.api import ExecutionResult
from robot.result.visitor import ResultVisitor
from multiprocessing.pool import Pool
from tempfile import mkdtemp
from robot.run import USAGE
from robot.utils import ArgumentParser


def execute_and_wait(args):
    datasources, outs_dir, options, suite_name, _ = args
    print 'EXECUTING PARALLEL SUITE %s' % suite_name
    rc = run(*datasources, **_options_for_executor(options, outs_dir, suite_name))
    if rc != 0:
        print 'EXECUTION FAILED IN %s' % suite_name

def execute_and_wait_with(args):
        datasources, outs_dir, options, suite_name, command = args
        cmd = command + _options_for_java_executor(options, outs_dir, suite_name) + datasources
        cmd = [c if ' ' not in c else '"%s"' % c for c in cmd]
        print 'EXECUTING PARALLEL SUITE %s with command "%s"' % (suite_name, ' '.join(cmd))
        process = subprocess.Popen(' '.join(cmd),
                              shell=True,
                              stderr=subprocess.PIPE,
                              stdout=subprocess.PIPE)
        rc = process.wait()
        if rc != 0:
            print _execution_failed_message(suite_name, process)

def _execution_failed_message(suite_name, process):
    msg = ['Execution failed in %s' % suite_name]
    msg += ['<< STDOUT >>']
    msg += [process.stdout.read()]
    msg += ['<< STDERR >>']
    msg += [process.stderr.read()]
    msg += ['<< END OF OUTPUT >>']
    return '\n'.join(msg)

def _options_for_executor(options, outs_dir, suite_name):
    options = options.copy()
    options['log'] = 'NONE'
    options['report'] = 'NONE'
    options['suite'] = suite_name
    options['outputdir'] = outs_dir
    options['output'] = '%s.xml' % suite_name
    options['stdout'] = StringIO()
    options['stderr'] = StringIO()
    return options

def _options_for_java_executor(*args):
    opts = _options_for_executor(*args)
    res = []
    for k, v in opts.items():
        if isinstance(v, basestring):
            res += ['--' + str(k), str(v)]
        if isinstance(v, bool) and (v is True):
            res += ['--' + str(k)]
        if isinstance(v, list):
            for value in v:
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

def get_args():
    args = sys.argv[1:]
    pabot_args = {'command':None,
                  'processes':max(multiprocessing.cpu_count(), 2)}
    while args and args[0] in ['--command', '--processes']:
        if args[0] == '--command':
            end_index = args.index('--end-command')
            pabot_args['command'] = args[1:end_index]
            args = args[end_index+1:]
        if args[0] == '--processes':
            pabot_args['processes'] = int(args[1])
            args = args[2:]
    options, datasources = ArgumentParser(USAGE).parse_args(args)
    keys = set()
    for k in options:
        if options[k] is None:
            keys.add(k)
    for k in keys:
        del options[k]
    return options, datasources, pabot_args

def solve_suite_names(outs_dir, datasources, options):
    options = options.copy()
    options['log'] = 'NONE'
    options['report'] = 'NONE'
    options['dryrun'] = True
    options['output'] = 'suite_names.xml'
    options['outputdir'] = outs_dir
    options['stdout'] = StringIO()
    options['stderr'] = StringIO()
    run(*datasources, **options)
    output = os.path.join(outs_dir, 'suite_names.xml')
    suite_names = get_suite_names(output)
    if os.path.isfile(output):
        os.remove(output)
    return suite_names

def _options_for_rebot(options, datasources):
    rebot_options = options.copy()
    rebot_options['name'] = ', '.join(datasources)
    return rebot_options

if __name__ == '__main__':
    outs_dir = mkdtemp()
    try:
        options, datasources, pabot_args = get_args()
        suite_names = solve_suite_names(outs_dir, datasources, options)
        if suite_names:
            process_pool = Pool(pabot_args['processes'])
            process_pool.map_async(execute_and_wait if not pabot_args['command'] else execute_and_wait_with,
                                   [(datasources, outs_dir, options, suite, pabot_args['command']) for suite in suite_names])
            process_pool.close()
            process_pool.join()
        sys.exit(rebot(*sorted(glob(os.path.join(outs_dir, '*.xml'))), **_options_for_rebot(options, datasources)))
    finally:
        shutil.rmtree(outs_dir)


