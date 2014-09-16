#    Copyright 2014 Mikko Korpela
#
#    This file is part of Pabot - A parallel executor for Robot Framework test cases..
#
#    Pabot is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Pabot is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Pabot.  If not, see <http://www.gnu.org/licenses/>.
#
import ConfigParser
import os
import uuid
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

    def get_value(self, key, caller_id):
        return self._owner_to_values[caller_id][key]


class PabotLib(_PabotLib):

    def __init__(self, uri):
        _PabotLib.__init__(self)
        self._remotelib = Remote(uri) if uri else None
        self._my_id = uuid.uuid4().get_hex()

    def acquire_lock(self, name):
        """
        Wait for a lock with name.
        This will prevent other processes from acquiring the lock with the name while it is held.
        """
        if self._remotelib:
            try:
                while not self._remotelib.run_keyword('acquire_lock', [name, self._my_id], {}):
                    time.sleep(0.1)
                    logger.debug('waiting for lock to release')
                return True
            except RuntimeError:
                logger.warn('no connection')
                self._remotelib = None
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
        if self._remotelib:
            try:
                while True:
                    value = self._remotelib.run_keyword('acquire_value_set', [self._my_id], {})
                    if value:
                        return value
                    time.sleep(0.1)
                    logger.debug('waiting for a value set')
            except RuntimeError:
                logger.warn('no connection')
                self._remotelib = None
        return _PabotLib.acquire_value_set(self, self._my_id)

    def get_value(self, key):
        if self._remotelib:
            while True:
                value = self._remotelib.run_keyword('get_value', [key, self._my_id], {})
                if value:
                    return value
                time.sleep(0.1)
                logger.debug('waiting for a value')
        else:
            return _PabotLib.get_value(self, key, self._my_id)

    def release_value_set(self):
        if self._remotelib:
            self._remotelib.run_keyword('release_value_set', [self._my_id], {})
        else:
            _PabotLib.release_value_set(self, self._my_id)


if __name__ == '__main__':
    import sys
    RobotRemoteServer(_PabotLib(sys.argv[1]))