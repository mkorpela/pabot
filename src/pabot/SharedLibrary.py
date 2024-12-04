from __future__ import absolute_import

from robot import __version__ as ROBOT_VERSION
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Remote import Remote
from robot.running.testlibraries import TestLibrary

from .pabotlib import PABOT_QUEUE_INDEX
from .robotremoteserver import RemoteLibraryFactory


class SharedLibrary(object):
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self, name, args=None):
        """
        Import a library so that the library instance is shared between executions.
        [https://pabot.org/PabotLib.html?ref=log#import-shared-library|Open online docs.]
        """
        # FIXME: RELATIVE IMPORTS WITH FILE NAME
        self._remote = None
        if BuiltIn().get_variable_value("${%s}" % PABOT_QUEUE_INDEX) is None:
            logger.debug(
                "Not currently running pabot. Importing library for this process."
            )
            self._lib = RemoteLibraryFactory(
                TestLibrary.from_name(
                    name, args=args, variables=None, create_keywords=True
                ).instance
                if ROBOT_VERSION >= "7.0"
                else TestLibrary(name, args=args).get_instance()
            )
            return
        uri = BuiltIn().get_variable_value("${PABOTLIBURI}")
        logger.debug("PabotLib URI %r" % uri)
        remotelib = Remote(uri) if uri else None
        if remotelib:
            try:
                port = remotelib.run_keyword(
                    "import_shared_library", [name], {"args": args}
                )
            except RuntimeError:
                logger.error("No connection - is pabot called with --pabotlib option?")
                raise
            self._remote = Remote("http://127.0.0.1:%s" % port)
            logger.debug(
                "Lib imported with name %s from http://127.0.0.1:%s" % (name, port)
            )
        else:
            logger.error("No connection - is pabot called with --pabotlib option?")
            raise AssertionError("No connection to pabotlib")

    def get_keyword_names(self):
        if self._remote:
            return self._remote.get_keyword_names()
        return self._lib.get_keyword_names()

    def run_keyword(self, name, args, kwargs):
        if self._remote:
            return self._remote.run_keyword(name, args, kwargs)
        result = self._lib.run_keyword(name, args, kwargs)
        if result["status"] == "FAIL":
            raise AssertionError(result["error"])
        return result.get("return")
