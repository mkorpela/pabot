import os, sys
import multiprocessing
from glob import glob
from StringIO import StringIO
import shutil
from robot import run, rebot
from robot.api import ExecutionResult
from robot.result.visitor import ResultVisitor
from multiprocessing.pool import Pool
from tempfile import mkdtemp
from robot.run import USAGE
from robot.utils import ArgumentParser

NUMBER_OF_PARALLEL_RUNNERS = max(multiprocessing.cpu_count(), 2)


def execute_and_wait(args):
    datasources, outs_dir, options, suite_name = args
    print 'EXECUTING PARALLEL SUITE %s' % suite_name
    rc = run(*datasources, **_options_for_executor(options, outs_dir, suite_name))
    if rc != 0:
        print 'EXECUTION FAILED IN %s' % suite_name


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
    options, datasources = ArgumentParser(USAGE).parse_args(sys.argv[1:])
    keys = set()
    for k in options:
        if options[k] is None:
            keys.add(k)
    for k in keys:
        del options[k]
    return options, datasources

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
        suite_dir = sys.argv[-1]
        options, datasources = get_args()
        suite_names = solve_suite_names(outs_dir, datasources, options)
        if suite_names:
            process_pool = Pool(NUMBER_OF_PARALLEL_RUNNERS)
            process_pool.map_async(execute_and_wait, [(datasources, outs_dir, options, suite) for suite in suite_names])
            process_pool.close()
            process_pool.join()
        sys.exit(rebot(*sorted(glob(os.path.join(outs_dir, '*.xml'))), **_options_for_rebot(options, datasources)))
    finally:
        shutil.rmtree(outs_dir)


