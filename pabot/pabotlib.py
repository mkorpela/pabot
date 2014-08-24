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

class PabotLib(object):

    def ping(self):
        print 'PONG PONG'
        return 'pong'

if __name__ == '__main__':
    RobotRemoteServer(PabotLib())