#  Copyright 2014 Mikko Korpela
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

import ConfigParser
import os
import uuid
from robot.libraries.BuiltIn import BuiltIn
from robotremoteserver import RobotRemoteServer
from robot.libraries.Remote import Remote
from robot.api import logger
import time


class _PabotLib(object):

    def __init__(self, resourcefile=None):
        self._locks = {}
        self._owner_to_values = {}
        self._values = self._parse_values(resourcefile)

    def _parse_values(self, resourcefile):
        vals = {}
        if resourcefile is None or not os.path.exists(resourcefile):
            return vals
        conf = ConfigParser.ConfigParser()
        conf.read(resourcefile)
        for section in conf.sections():
            vals[section] = dict((k,conf.get(section, k)) for k in conf.options(section))
        return vals

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

    def acquire_value_set(self, caller_id):
        for k in self._values:
            if self._values[k] not in self._owner_to_values.values():
                self._owner_to_values[caller_id] = self._values[k]
                return k

    def release_value_set(self, caller_id):
        self._owner_to_values[caller_id] = None

    def get_value_from_set(self, key, caller_id):
        if caller_id not in self._owner_to_values:
            raise AssertionError('No value set reserved for caller process')
        if key not in self._owner_to_values[caller_id]:
            raise AssertionError('No value for key "%s"' % key)
        return self._owner_to_values[caller_id][key]


class PabotLib(_PabotLib):

    __version__ = 0.11
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'

    def __init__(self):
        _PabotLib.__init__(self)
        self.__remotelib = None
        self._my_id = uuid.uuid4().get_hex()

    @property
    def _remotelib(self):
        if self.__remotelib is None:
            uri = BuiltIn().get_variable_value('${PABOTLIBURI}')
            logger.debug('PabotLib URI %r' % uri)
            self.__remotelib = Remote(uri) if uri else None
        return self.__remotelib

    def acquire_lock(self, name):
        """
        Wait for a lock with name.
        This will prevent other processes from acquiring the lock with the name while it is held.
        Thus they will wait in the position where they are acquiring the lock until the process
        that has it releases it.
        """
        if self._remotelib:
            try:
                while not self._remotelib.run_keyword('acquire_lock', [name, self._my_id], {}):
                    time.sleep(0.1)
                    logger.debug('waiting for lock to release')
                return True
            except RuntimeError:
                logger.warn('no connection')
                self.__remotelib = None
        return _PabotLib.acquire_lock(self, name, self._my_id)

    def release_lock(self, name):
        """
        Release a lock with name.
        This will enable others to acquire the lock.
        """
        if self._remotelib:
            self._remotelib.run_keyword('release_lock', [name, self._my_id], {})
        else:
            _PabotLib.release_lock(self, name, self._my_id)

    def acquire_value_set(self):
        """
        Reserve a set of values for this execution.
        No other process can reserve the same set of values while the set is reserved.
        Acquired value set needs to be released after use to allow other processes
        to access it.
        """
        if self._remotelib:
            try:
                while True:
                    value = self._remotelib.run_keyword('acquire_value_set', [self._my_id], {})
                    if value:
                        logger.info('Value set "%s" acquired' % value)
                        return value
                    time.sleep(0.1)
                    logger.debug('waiting for a value set')
            except RuntimeError:
                logger.warn('no connection')
                self.__remotelib = None
        return _PabotLib.acquire_value_set(self, self._my_id)

    def get_value_from_set(self, key):
        """
        Get a value from previously reserved value set.
        """
        if self._remotelib:
            while True:
                value = self._remotelib.run_keyword('get_value_from_set', [key, self._my_id], {})
                if value:
                    return value
                time.sleep(0.1)
                logger.debug('waiting for a value')
        else:
            return _PabotLib.get_value_from_set(self, key, self._my_id)

    def release_value_set(self):
        """
        Release a reserved value set so that other executions can use it also.
        """
        if self._remotelib:
            self._remotelib.run_keyword('release_value_set', [self._my_id], {})
        else:
            _PabotLib.release_value_set(self, self._my_id)


if __name__ == '__main__':
    import sys
    RobotRemoteServer(_PabotLib(sys.argv[1]), allow_stop=True)