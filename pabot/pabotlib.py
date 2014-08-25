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
from robotremoteserver import RobotRemoteServer
from robot.libraries.Remote import Remote
import time


class PabotLib(object):

    def __init__(self, uri=None):
        self._remotelib = Remote(uri) if uri else None
        self._locks = set()

    def acquire_lock(self, name):
        if self._remotelib:
            try:
                while not self._remotelib.run_keyword('acquire_lock', [name], {}):
                    time.sleep(0.1)
                    print 'waiting for lock to release'
                return True
            except RuntimeError:
                print 'no connection'
                self._remotelib = None
        if name in self._locks:
            return False
        self._locks.add(name)
        return True

    def release_lock(self, name):
        if self._remotelib:
            self._remotelib.run_keyword('release_lock', [name], {})
        else:
            self._locks.remove(name)

if __name__ == '__main__':
    RobotRemoteServer(PabotLib())