from qgis.core import QgsMessageLog, Qgis

import logging

log = logging.getLogger("mappy")


class QgsLogHandler(logging.StreamHandler):
    """
    A handler class which allows the cursor to stay on
    one line for selected messages
    """

    def emit(self, record):
        try:
            msg = self.format(record)
            QgsMessageLog.logMessage(msg, "Mappy", Qgis.MessageLevel.Info, False)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


prev_handlers = log.handlers

if len(prev_handlers) == 0:  # when reloading a plugin the python interpreter is the same so we dont want to duplicate
    # logging handlers. Not a clean way to do so, but it is just for development
    handler = QgsLogHandler()
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
