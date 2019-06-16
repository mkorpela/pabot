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

from __future__ import absolute_import

try:
    import configparser
except:
    import ConfigParser as configparser  # Support Python 2

from robot.libraries.BuiltIn import BuiltIn
from robotremoteserver import RobotRemoteServer
from robot.libraries.Remote import Remote
from robot.api import logger
import time

PABOT_LAST_LEVEL = "PABOTLASTLEVEL"
PABOT_QUEUE_INDEX = "PABOTQUEUEINDEX"
PABOT_LAST_EXECUTION_IN_POOL = "PABOTISLASTEXECUTIONINPOOL"
PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE = "pabot_min_queue_index_executing"

class _PabotLib(object):

    _TAGS_KEY = "tags"

    def __init__(self, resourcefile=None):
        self._locks = {}
        self._owner_to_values = {}
        self._parallel_values = {}
        self._values = self._parse_values(resourcefile)

    def _parse_values(self, resourcefile):
        vals = {}
        if resourcefile is None:
            return vals
        conf = configparser.ConfigParser()
        conf.read(resourcefile)
        for section in conf.sections():
            vals[section] = dict((k, conf.get(section, k))
                                 for k in conf.options(section))
        for section in vals:
            if self._TAGS_KEY in vals[section]:
                vals[section][self._TAGS_KEY] = [t.strip() for t in vals[section][self._TAGS_KEY].split(",")]
            else:
                vals[section][self._TAGS_KEY] = []
        return vals

    def set_parallel_value_for_key(self, key, value):
        self._parallel_values[key] = value

    def get_parallel_value_for_key(self, key):
        return self._parallel_values.get(key, "")

    def acquire_lock(self, name, caller_id):
        if name in self._locks and caller_id != self._locks[name][0]:
            return False
        if name not in self._locks:
            self._locks[name] = [caller_id, 0]
        self._locks[name][1] += 1
        return True

    def release_lock(self, name, caller_id):
        assert self._locks[name][0] == caller_id
        self._locks[name][1] -= 1
        if self._locks[name][1] == 0:
            del self._locks[name]

    def release_locks(self, caller_id):
        for key in self._locks.keys():
            if self._locks[key][0] == caller_id:
                self._locks[key][1] -= 1
                if self._locks[key][1] == 0:
                    del self._locks[key]

    def acquire_value_set(self, caller_id, *tags):
        if not self._values:
            raise AssertionError(
                'Value set cannot be aquired - it was never imported. Use --resourcefile option to import.')
        # CAN ONLY RESERVE ONE VALUE SET AT A TIME
        if caller_id in self._owner_to_values and self._owner_to_values[caller_id] is not None:
            raise ValueError("Caller has already reserved a value set.")
        matching = False
        for valueset_key in self._values:
            if all(tag in self._values[valueset_key][self._TAGS_KEY] for tag in tags):
                matching = True
                if self._values[valueset_key] not in self._owner_to_values.values():
                    self._owner_to_values[caller_id] = self._values[valueset_key]
                    return (valueset_key, self._values[valueset_key])
        if not matching:
            raise ValueError("No value set matching given tags exists.")
        # This return value is for situations where no set could be reserved
        # and the caller needs to wait until one is free.
        return (None, None)

    def release_value_set(self, caller_id):
        self._owner_to_values[caller_id] = None

    def get_value_from_set(self, key, caller_id):
        if caller_id not in self._owner_to_values:
            raise AssertionError('No value set reserved for caller process')
        if key not in self._owner_to_values[caller_id]:
            raise AssertionError('No value for key "%s"' % key)
        return self._owner_to_values[caller_id][key]


class PabotLib(_PabotLib):

    __version__ = 0.64
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self):
        _PabotLib.__init__(self)
        self.__remotelib = None
        self.__my_id = None
        self._valueset = None
        self.ROBOT_LIBRARY_LISTENER = self
        self._position = []
        self._row_index = 0

    def _start(self, name, attributes):
        self._position.append(attributes["longname"])

    def _end(self, name, attributes):
        self._position = self._position[:-1]

    def _start_keyword(self, name, attributes):
        self._position.append(self._position[-1] + "." + str(self._row_index))
        self._row_index = 0

    def _end_keyword(self, name, attributes):
        self._row_index = int(self._position[-1].split(".")[-1])
        self._row_index += 1
        self._position = self._position[:-1]
    
    _start_suite = _start_test = _start
    _end_suite = _end_test = _end

    def _close(self):
        try:
            self.release_locks()
            self.release_value_set()
        except RuntimeError:
            # This is just last line of defence
            # Ignore connection errors if library server already closed
            logger.console("pabot.PabotLib#_close: threw an exception: is --pabotlib flag used?", stream='stderr')
            pass

    @property
    def _path(self):
        if len(self._position) < 1:
            return ""
        return self._position[-1]

    @property
    def _my_id(self):
        if self.__my_id is None:
            my_id = BuiltIn().get_variable_value('${CALLER_ID}')
            logger.debug('Caller ID is  %r' % my_id)
            self.__my_id = my_id if my_id else None
        return self.__my_id

    @property
    def _remotelib(self):
        if self.__remotelib is None:
            uri = BuiltIn().get_variable_value('${PABOTLIBURI}')
            logger.debug('PabotLib URI %r' % uri)
            self.__remotelib = Remote(uri) if uri else None
        return self.__remotelib

    def run_setup_only_once(self, keyword, *args):
        """
        Runs a setup keyword with args only once at first possible moment when
        an execution has gone throught this step. The executions after that
        will skip this step. If the firts execution fails, all others will also.
        """
        lock_name = 'pabot_setup_%s' % self._path
        try:
            self.acquire_lock(lock_name)
            passed = self.get_parallel_value_for_key(lock_name)
            if passed != '':
                if passed == 'FAILED':
                    raise AssertionError('Setup failed in other process')
                logger.info("Setup skipped in this item")
                return
            BuiltIn().run_keyword(keyword, *args)
            self.set_parallel_value_for_key(lock_name, 'PASSED')
        except:
            self.set_parallel_value_for_key(lock_name, 'FAILED')
            raise
        finally:
            self.release_lock(lock_name)

    def run_only_once(self, keyword):
        """
        Runs a keyword only once in one of the parallel processes.
        As the keyword will be called
        only in one process and the return value could basically be anything.
        The "Run Only Once" can't return the actual return value.
        If the keyword fails, "Run Only Once" fails.
        Others executing "Run Only Once" wait before going through this
        keyword before the actual command has been executed.
        """
        lock_name = 'pabot_run_only_once_%s' % keyword
        try:
            self.acquire_lock(lock_name)
            passed = self.get_parallel_value_for_key(lock_name)
            if passed != '':
                if passed == 'FAILED':
                    raise AssertionError('Keyword failed in other process')
                logger.info("Skipped in this item")
                return
            BuiltIn().run_keyword(keyword)
            self.set_parallel_value_for_key(lock_name, 'PASSED')
        except:
            self.set_parallel_value_for_key(lock_name, 'FAILED')
            raise
        finally:
            self.release_lock(lock_name)

    def run_teardown_only_once(self, keyword, *args):
        """
        Runs a teardown keyword with args only once after all executions have gone
        throught this step in the last possible moment.
        Note it is important to not have any conditions preventing from executing
        this step as that may prevent this keyword from working correctly.
        """
        last_level = BuiltIn().get_variable_value('${%s}' % PABOT_LAST_LEVEL)
        if last_level is None:
            BuiltIn().run_keyword(keyword, *args)
            return
        logger.trace('Current path "%s" and last level "%s"' % (self._path, last_level))
        if not self._path.startswith(last_level):
            logger.info("Teardown skipped in this item")
            return
        queue_index = int(BuiltIn().get_variable_value('${%s}' % PABOT_QUEUE_INDEX) or 0)
        logger.trace("Queue index (%d)" % queue_index)
        if self._remotelib:
            while self.get_parallel_value_for_key(PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE) < queue_index:
                logger.trace(self.get_parallel_value_for_key(PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE))
                time.sleep(0.3)
        logger.trace("Teardown conditions met. Executing keyword.")
        BuiltIn().run_keyword(keyword, *args)

    def run_on_last_process(self, keyword):
        """
        Runs a keyword on last process used by pabot.
        Keyword will wait until all other processes have stopped executing.
        This can be used to run a global teardown that should be only
        executed after all testing is done.
        """
        is_last = int(BuiltIn().get_variable_value('${%s}' % PABOT_LAST_EXECUTION_IN_POOL) or 1) == 1
        if not is_last:
            logger.info("Skipped in this item")
            return
        queue_index = int(BuiltIn().get_variable_value('${%s}' % PABOT_QUEUE_INDEX) or 0)
        if queue_index > 0 and self._remotelib:
            while self.get_parallel_value_for_key('pabot_only_last_executing') != 1:
                time.sleep(0.3)
        BuiltIn().run_keyword(keyword)

    def set_parallel_value_for_key(self, key, value):
        """
        Set a globally available key and value that can be accessed
        from all the pabot processes.
        """
        self._run_with_lib('set_parallel_value_for_key', key, value)

    def _run_with_lib(self, keyword, *args):
        if self._remotelib:
            try:
                return self._remotelib.run_keyword(keyword, args, {})
            except RuntimeError:
                logger.error('No connection - is pabot called with --pabotlib option?')
                self.__remotelib = None
                raise
        return getattr(_PabotLib, keyword)(self, *args)

    def get_parallel_value_for_key(self, key):
        """
        Get the value for a key. If there is no value for the key then empty
        string is returned.
        """
        return self._run_with_lib('get_parallel_value_for_key', key)

    def acquire_lock(self, name):
        """
        Wait for a lock with name.
        This will prevent other processes from acquiring the lock with
        the name while it is held. Thus they will wait in the position
        where they are acquiring the lock until the process that has it
        releases it.
        """
        if self._remotelib:
            try:
                while not self._remotelib.run_keyword('acquire_lock',
                                                      [name, self._my_id], {}):
                    time.sleep(0.1)
                    logger.debug('waiting for lock to release')
                return True
            except RuntimeError:
                logger.error('No connection - is pabot called with --pabotlib option?')
                self.__remotelib = None
                raise
        return _PabotLib.acquire_lock(self, name, self._my_id)

    def release_lock(self, name):
        """
        Release a lock with name.
        This will enable others to acquire the lock.
        """
        self._run_with_lib('release_lock', name, self._my_id)

    def release_locks(self):
        """
        Release all locks called by instance.
        """
        self._run_with_lib('release_locks', self._my_id)

    def acquire_value_set(self, *tags):
        """
        Reserve a set of values for this execution.
        No other process can reserve the same set of values while the set is
        reserved. Acquired value set needs to be released after use to allow
        other processes to access it.
        Add tags to limit the possible value sets that this returns.
        """
        setname = self._acquire_value_set(*tags)
        if setname is None:
            raise ValueError("Could not aquire a value set")
        return setname

    def _acquire_value_set(self, *tags):
        if self._remotelib:
            try:
                while True:
                    key, self._valueset = self._remotelib.run_keyword('acquire_value_set',
                                                        [self._my_id]+list(tags), {})
                    if key:
                        logger.info('Value set "%s" acquired' % key)
                        return key
                    time.sleep(0.1)
                    logger.debug('waiting for a value set')
            except RuntimeError:
                logger.error('No connection - is pabot called with --pabotlib option?')
                self.__remotelib = None
                raise
        key, self._valueset = _PabotLib.acquire_value_set(self, self._my_id, *tags)
        return key

    def get_value_from_set(self, key):
        """
        Get a value from previously reserved value set.
        """
        if self._valueset is None:
            raise AssertionError('No value set reserved for caller process')
        key = key.lower()
        if key not in self._valueset:
            raise AssertionError('No value for key "%s"' % key)
        return self._valueset[key]

    def release_value_set(self):
        """
        Release a reserved value set so that other executions can use it also.
        """
        self._valueset = None
        self._run_with_lib('release_value_set', self._my_id)


if __name__ == '__main__':
    import sys
    RobotRemoteServer(_PabotLib(sys.argv[1]), host=sys.argv[2],
                      port=sys.argv[3], allow_stop=True)
