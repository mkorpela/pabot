from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Remote import Remote
from robot.api import logger
from .pabotlib import PABOT_QUEUE_INDEX

class SharedLibrary(object):

    def __init__(self, name):
        """
        Import a library so that the library instance is shared between executions.
        [https://pabot.org/PabotLib.html?ref=log#import-shared-library|Open online docs.]
        """
        if BuiltIn().get_variable_value('${%s}' % PABOT_QUEUE_INDEX) is None:
            logger.debug("Not currently running pabot. Importing library for this process.")
            BuiltIn().import_library(name)
            return
        uri = BuiltIn().get_variable_value('${PABOTLIBURI}')
        logger.debug('PabotLib URI %r' % uri)
        remotelib = Remote(uri) if uri else None
        if remotelib:
            try:
                port = remotelib.run_keyword("import_shared_library", [name], {})
            except RuntimeError:
                logger.error('No connection - is pabot called with --pabotlib option?')
                self.__remotelib = None
                raise
            BuiltIn().import_library("Remote", "http://127.0.0.1:%s" % port, "WITH NAME", name)
            logger.debug("Lib imported with name %s from http://127.0.0.1:%s" % (name, port))
        else:
            logger.error('No connection - is pabot called with --pabotlib option?')
            raise AssertionError('No connection to pabotlib')


    def passing_keyword(self):
        pass