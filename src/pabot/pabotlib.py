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

from robot.errors import RobotError

try:
    import configparser  # type: ignore
except:
    import ConfigParser as configparser  # type: ignore

    # Support Python 2

import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Remote import Remote
from robot.utils.importer import Importer
from robot.libraries import STDLIBS

from .robotremoteserver import RobotRemoteServer

PABOT_LAST_LEVEL = "PABOTLASTLEVEL"
PABOT_QUEUE_INDEX = "PABOTQUEUEINDEX"
PABOT_LAST_EXECUTION_IN_POOL = "PABOTISLASTEXECUTIONINPOOL"
PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE = "pabot_min_queue_index_executing"


class _PabotLib(object):
    _TAGS_KEY = "tags"

    def __init__(self, resourcefile=None):  # type: (Optional[str]) -> None
        self._locks = {}  # type: Dict[str, Tuple[str, int]]
        self._owner_to_values = {}  # type: Dict[str, Dict[str, object]]
        self._parallel_values = {}  # type: Dict[str, object]
        self._remote_libraries = (
            {}
        )  # type: Dict[str, Tuple[int, RobotRemoteServer, threading.Thread]]
        self._values = self._parse_values(resourcefile)
        self._added_suites = []  # type: List[Tuple[str, List[str]]]
        self._ignored_executions = set()  # type: Set[str]

    def _parse_values(
        self, resourcefile
    ):  # type: (Optional[str]) -> Dict[str, Dict[str, Any]]
        vals = {}  # type: Dict[str, Dict[str, Any]]
        if resourcefile is None:
            return vals
        conf = configparser.ConfigParser()
        conf.read(resourcefile)
        for section in conf.sections():
            vals[section] = dict(
                (k, conf.get(section, k)) for k in conf.options(section)
            )
        for section in vals:
            if self._TAGS_KEY in vals[section]:
                vals[section][self._TAGS_KEY] = [
                    t.strip() for t in vals[section][self._TAGS_KEY].split(",")
                ]
            else:
                vals[section][self._TAGS_KEY] = []
        return vals

    def set_parallel_value_for_key(self, key, value):  # type: (str, object) -> None
        self._parallel_values[key] = value

    def get_parallel_value_for_key(self, key):  # type: (str) -> object
        return self._parallel_values.get(key, "")

    def acquire_lock(self, name, caller_id):  # type: (str, str) -> bool
        if name in self._locks and caller_id != self._locks[name][0]:
            return False
        if name not in self._locks:
            self._locks[name] = (caller_id, 0)
        self._locks[name] = (caller_id, self._locks[name][1] + 1)
        return True

    def release_lock(self, name, caller_id):  # type: (str, str) -> None
        assert self._locks[name][0] == caller_id
        self._locks[name] = (caller_id, self._locks[name][1] - 1)
        if self._locks[name][1] == 0:
            del self._locks[name]

    def release_locks(self, caller_id):
        # type: (str) -> None
        for key in list(self._locks.keys()):
            if self._locks[key][0] == caller_id:
                self._locks[key] = (caller_id, self._locks[key][1] - 1)
                if self._locks[key][1] == 0:
                    del self._locks[key]

    def acquire_value_set(self, caller_id, *tags):
        if not self._values:
            raise AssertionError(
                "Value set cannot be aquired. It was never imported or all are disabled. Use --resourcefile option to import."
            )
        # CAN ONLY RESERVE ONE VALUE SET AT A TIME
        if (
            caller_id in self._owner_to_values
            and self._owner_to_values[caller_id] is not None
        ):
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

    def release_value_set(self, caller_id):  # type: (str) -> None
        if caller_id not in self._owner_to_values:
            return
        del self._owner_to_values[caller_id]

    def disable_value_set(self, setname, caller_id):  # type: (str, str) -> None
        del self._owner_to_values[caller_id]
        del self._values[setname]

    def get_value_from_set(self, key, caller_id):  # type: (str, str) -> object
        if caller_id not in self._owner_to_values:
            raise AssertionError("No value set reserved for caller process")
        if key not in self._owner_to_values[caller_id]:
            raise AssertionError('No value for key "%s"' % key)
        return self._owner_to_values[caller_id][key]

    def add_value_to_set(self, name, content):
        if self._TAGS_KEY in content.keys():
            content[self._TAGS_KEY] = [
                t.strip() for t in content[self._TAGS_KEY].split(",")
            ]
        if self._TAGS_KEY not in content.keys():
            content[self._TAGS_KEY] = []
        self._values[name] = content

    def import_shared_library(
        self, name, args=None
    ):  # type: (str, Iterable[Any]|None) -> int
        if name in self._remote_libraries:
            return self._remote_libraries[name][0]
        if name in STDLIBS:
            import_name = "robot.libraries." + name
        else:
            import_name = name
        imported = Importer("library").import_class_or_module(
            name_or_path=import_name, instantiate_with_args=args
        )
        server = RobotRemoteServer(imported, port=0, serve=False, allow_stop=True)
        server_thread = threading.Thread(target=server.serve)
        server_thread.start()
        time.sleep(1)
        port = server.server_port
        self._remote_libraries[name] = (port, server, server_thread)
        return port

    def add_suite_to_execution_queue(
        self, suitename, variables
    ):  # type: (str, List[str]) -> None
        self._added_suites.append((suitename, variables or []))

    def get_added_suites(self):  # type: () -> List[Tuple[str, List[str]]]
        added_suites = self._added_suites
        self._added_suites = []
        return added_suites

    def ignore_execution(self, caller_id):  # type: (str) -> None
        self._ignored_executions.add(caller_id)

    def is_ignored_execution(self, caller_id):  # type: (str) -> bool
        return caller_id in self._ignored_executions

    def stop_remote_libraries(self):
        for name in self._remote_libraries:
            self._remote_libraries[name][1].stop_remote_server()
        for name in self._remote_libraries:
            self._remote_libraries[name][2].join()


class PabotLib(_PabotLib):
    __version__ = 0.67
    ROBOT_LIBRARY_SCOPE = "GLOBAL"
    ROBOT_LISTENER_API_VERSION = 2
    _pollingSeconds_SetupTeardown = 0.3
    _pollingSeconds = 0.1
    _polling_logging = True
    _execution_ignored = False

    def __init__(self):
        _PabotLib.__init__(self)
        self.__remotelib = None
        self.__my_id = None
        self._valueset = None
        self._setname = None
        self.ROBOT_LIBRARY_LISTENER = self
        self._position = []  # type: List[str]
        self._row_index = 0

    def _start(self, name, attributes):
        self._position.append(attributes["longname"])

    def _end(self, name, attributes):
        self._position = (
            self._position[:-1]
            if len(self._position) > 1
            else [attributes["longname"][: -len(name) - 1]]
        )

    def _start_keyword(self, name, attributes):
        if not (self._position):
            self._position = ["0", "0." + str(self._row_index)]
        else:
            self._position.append(self._position[-1] + "." + str(self._row_index))
        self._row_index = 0

    def _end_keyword(self, name, attributes):
        if not (self._position):
            self._row_index = 1
            self._position = ["0"]
            return
        splitted = self._position[-1].split(".")
        self._row_index = int(splitted[-1]) if len(splitted) > 1 else 0
        self._row_index += 1
        self._position = (
            self._position[:-1]
            if len(self._position) > 1
            else [str(int(splitted[0]) + 1)]
        )

    _start_suite = _start_test = _start
    _end_suite = _end_test = _end

    def _close(self):
        try:
            self.release_locks()
            self.release_value_set()
        except RuntimeError as err:
            # This is just last line of defence
            # Ignore connection errors if library server already closed
            logger.console(
                "pabot.PabotLib#_close: threw an exception: is --pabotlib flag used? ErrorDetails: {0}".format(
                    repr(err)
                ),
                stream="stderr",
            )
            pass

    @property
    def _path(self):
        if len(self._position) < 1:
            return ""
        return self._position[-1]

    @property
    def _my_id(self):
        if self.__my_id is None:
            my_id = BuiltIn().get_variable_value("${CALLER_ID}")
            logger.debug("Caller ID is  %r" % my_id)
            self.__my_id = my_id if my_id else None
        return self.__my_id

    @property
    def _remotelib(self):
        if self.__remotelib is None:
            uri = BuiltIn().get_variable_value("${PABOTLIBURI}")
            logger.debug("PabotLib URI %r" % uri)
            self.__remotelib = Remote(uri) if uri else None
        return self.__remotelib

    def set_polling_seconds(self, secs):
        """
        Determine the amount of seconds to wait between checking for free locks. Default: 0.1  (100ms)
        """
        PabotLib._pollingSeconds = secs

    def set_polling_seconds_setupteardown(self, secs):
        """
        Determine the amount of seconds to wait between checking for free locks during setup and teardown. Default: 0.3  (300ms)
        """
        PabotLib._pollingSeconds_SetupTeardown = secs

    def set_polling_logging(self, enable):
        """
        Enable or disable logging inside of polling. Logging inside of polling can be disabled (enable=False) to reduce log file size.
        """
        if isinstance(enable, str):
            enable = enable.lower() == "true"
        PabotLib._polling_logging = bool(enable)

    def run_setup_only_once(self, keyword, *args):
        """
        Runs a keyword only once at the first possible moment when
        an execution has gone through this step.
        [https://pabot.org/PabotLib.html?ref=log#run-setup-only-once|Open online docs.]
        """
        if self._execution_ignored:
            return
        lock_name = "pabot_setup_%s" % self._path
        try:
            self.acquire_lock(lock_name)
            passed = self.get_parallel_value_for_key(lock_name)
            if passed != "":
                if passed == "FAILED":
                    raise AssertionError("Setup failed in other process")
                logger.info("Setup skipped in this item")
                return
            BuiltIn().run_keyword(keyword, *args)
            self.set_parallel_value_for_key(lock_name, "PASSED")
        except:
            self.set_parallel_value_for_key(lock_name, "FAILED")
            raise
        finally:
            self.release_lock(lock_name)

    def run_only_once(self, keyword, *args):
        """
        Runs a keyword only once in one of the parallel processes. Optional arguments of the keyword needs to be serializeable in order to
        create an unique lockname.
        Sample request sequence [keyword, keyword 'x', keyword, keyword 5, keyword 'x', keyword 5]
        results in execution of [keyword, keyword 'x', keyword 5]
        [https://pabot.org/PabotLib.html?ref=log#run-only-once|Open online docs.]
        """
        if self._execution_ignored:
            return
        lock_name = "pabot_run_only_once_%s_%s" % (keyword, str(args))
        try:
            self.acquire_lock(lock_name)
            passed = self.get_parallel_value_for_key(lock_name)
            if passed != "":
                if passed == "FAILED":
                    raise AssertionError("Keyword failed in other process")
                logger.info("Skipped in this item")
                return
            BuiltIn().run_keyword(keyword, *args)
            self.set_parallel_value_for_key(lock_name, "PASSED")
        except:
            self.set_parallel_value_for_key(lock_name, "FAILED")
            raise
        finally:
            self.release_lock(lock_name)

    def run_teardown_only_once(self, keyword, *args):
        """
        Runs a keyword only once after all executions have gone through this step in the last possible moment.
        [https://pabot.org/PabotLib.html?ref=log#run-teardown-only-once|Open online docs.]
        """
        if self._execution_ignored:
            return
        last_level = BuiltIn().get_variable_value("${%s}" % PABOT_LAST_LEVEL)
        if last_level is None:
            BuiltIn().run_keyword(keyword, *args)
            return
        logger.trace('Current path "%s" and last level "%s"' % (self._path, last_level))
        if not self._path.startswith(last_level):
            logger.info("Teardown skipped in this item")
            return
        queue_index = int(
            BuiltIn().get_variable_value("${%s}" % PABOT_QUEUE_INDEX) or 0
        )
        logger.trace("Queue index (%d)" % queue_index)
        if self._remotelib:
            while (
                self.get_parallel_value_for_key(
                    PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE
                )
                < queue_index
            ):
                if PabotLib._polling_logging:
                    logger.trace(
                        self.get_parallel_value_for_key(
                            PABOT_MIN_QUEUE_INDEX_EXECUTING_PARALLEL_VALUE
                        )
                    )
                time.sleep(PabotLib._pollingSeconds_SetupTeardown)
        logger.trace("Teardown conditions met. Executing keyword.")
        BuiltIn().run_keyword(keyword, *args)

    def run_on_last_process(self, keyword):
        """
        Runs a keyword only on last process used by pabot.
        [https://pabot.org/PabotLib.html?ref=log#run-on-last-process|Open online docs.]
        """
        if self._execution_ignored:
            return
        is_last = (
            int(
                BuiltIn().get_variable_value("${%s}" % PABOT_LAST_EXECUTION_IN_POOL)
                or 1
            )
            == 1
        )
        if not is_last:
            logger.info("Skipped in this item")
            return
        queue_index = int(
            BuiltIn().get_variable_value("${%s}" % PABOT_QUEUE_INDEX) or 0
        )
        if queue_index > 0 and self._remotelib:
            while self.get_parallel_value_for_key("pabot_only_last_executing") != 1:
                time.sleep(PabotLib._pollingSeconds_SetupTeardown)
        BuiltIn().run_keyword(keyword)

    def set_parallel_value_for_key(self, key, value):
        """
        Set a globally available key and value that can be accessed
        from all the pabot processes.
        [https://pabot.org/PabotLib.html?ref=log#set-parallel-value-for-key|Open online docs.]
        """
        self._run_with_lib("set_parallel_value_for_key", key, value)

    def _run_with_lib(self, keyword, *args):
        if self._remotelib:
            try:
                return self._remotelib.run_keyword(keyword, args, {})
            except RuntimeError as err:
                logger.error(
                    "RuntimeError catched in remotelib keyword execution. Maybe there is no connection - is pabot called with --pabotlib option? ErrorDetails: {0}".format(
                        repr(err)
                    )
                )
                self.__remotelib = None
                raise
        return getattr(_PabotLib, keyword)(self, *args)

    def add_suite_to_execution_queue(self, suitename, *variables):
        self._run_with_lib("add_suite_to_execution_queue", suitename, variables)

    def get_parallel_value_for_key(self, key):
        """
        Get the value for a key. If there is no value for the key then empty
        string is returned.
        [https://pabot.org/PabotLib.html?ref=log#get-parallel-value-for-key|Open online docs.]
        """
        return self._run_with_lib("get_parallel_value_for_key", key)

    def acquire_lock(self, name):
        """
        Wait for a lock with name.
        [https://pabot.org/PabotLib.html?ref=log#acquire-lock|Open online docs.]
        """
        if self._remotelib:
            try:
                while not self._remotelib.run_keyword(
                    "acquire_lock", [name, self._my_id], {}
                ):
                    time.sleep(PabotLib._pollingSeconds)
                    if PabotLib._polling_logging:
                        logger.debug("waiting for lock to release")
                return True
            except RuntimeError as err:
                logger.error(
                    "RuntimeError catched in remote acquire_lock execution. Maybe there is no connection - is pabot called with --pabotlib option? ErrorDetails: {0}".format(
                        repr(err)
                    )
                )
                self.__remotelib = None
                raise
        return _PabotLib.acquire_lock(self, name, self._my_id)

    def release_lock(self, name):
        """
        Release a lock with name.
        [https://pabot.org/PabotLib.html?ref=log#release-lock|Open online docs.]
        """
        self._run_with_lib("release_lock", name, self._my_id)

    def release_locks(self):
        """
        Release all locks called by instance.
        [https://pabot.org/PabotLib.html?ref=log#release-locks|Open online docs.]
        """
        self._run_with_lib("release_locks", self._my_id)

    def acquire_value_set(self, *tags):
        """
        Reserve a set of values for this execution.
        [https://pabot.org/PabotLib.html?ref=log#acquire-value-set|Open online docs.]
        """
        setname = self._acquire_value_set(*tags)
        if setname is None:
            raise ValueError("Could not aquire a value set")
        return setname

    def _acquire_value_set(self, *tags):
        if self._remotelib:
            try:
                while True:
                    self._setname, self._valueset = self._remotelib.run_keyword(
                        "acquire_value_set", [self._my_id] + list(tags), {}
                    )
                    if self._setname:
                        logger.info('Value set "%s" acquired' % self._setname)
                        return self._setname
                    time.sleep(PabotLib._pollingSeconds)
                    if PabotLib._polling_logging:
                        logger.debug("waiting for a value set")
            except RuntimeError as err:
                logger.error(
                    "RuntimeError catched in remote _acquire_value_set execution. Maybe there is no connection - is pabot called with --pabotlib option? ErrorDetails: {0}".format(
                        repr(err)
                    )
                )
                self.__remotelib = None
                raise
        self._setname, self._valueset = _PabotLib.acquire_value_set(
            self, self._my_id, *tags
        )
        return self._setname

    def get_value_from_set(self, key):
        """
        Get a value from previously reserved value set.
        [https://pabot.org/PabotLib.html?ref=log#get-value-from-set|Open online docs.]
        """
        if self._valueset is None:
            raise AssertionError("No value set reserved for caller process")
        key = key.lower()
        if key not in self._valueset:
            raise AssertionError('No value for key "%s"' % key)
        return self._valueset[key]

    def ignore_execution(self):
        self._run_with_lib("ignore_execution", self._my_id)
        error = RobotError("Ignore")
        error.ROBOT_EXIT_ON_FAILURE = True
        error.ROBOT_CONTINUE_ON_FAILURE = False
        self._execution_ignored = True
        raise error

    def release_value_set(self):
        """
        Release a reserved value set so that other executions can use it also.
        [https://pabot.org/PabotLib.html?ref=log#release-value-set|Open online docs.]
        """
        self._valueset = None
        self._setname = None
        self._run_with_lib("release_value_set", self._my_id)

    def disable_value_set(self):
        """
        Disable a reserved value set.
        [https://pabot.org/PabotLib.html?ref=log#disable-value-set|Open online docs.]
        """
        self._valueset = None
        self._run_with_lib("disable_value_set", self._setname, self._my_id)
        self._setname = None


# Module import will give a bad error message in log file
# Workaround: expose PabotLib also as pabotlib
pabotlib = PabotLib

if __name__ == "__main__":
    import sys

    RobotRemoteServer(
        _PabotLib(sys.argv[1]), host=sys.argv[2], port=sys.argv[3], allow_stop=True
    )
