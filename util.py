"""
Common utilities used by other openeo modules.
"""

import logging, os, sys, psutil

_LOGGER = logging.getLogger(__name__)


def restart_python():
    """Restarts the current program, with file objects and descriptors cleanup."""
    # https://stackoverflow.com/questions/11329917/restart-python-script-from-within-itself
    _LOGGER.info("Got restart request.")
    
    try:
        p = psutil.Process(os.getpid())
        for handler in (p.open_files() + p.connections()):
            try:
                os.close(handler.fd)
            except Exception as e:
                _LOGGER.error("Inner error closing for restart %r: %r" % (handler, e))
    except Exception as e:
        _LOGGER.error("Outer exception in restart: %r" % e)

    python = sys.executable
    os.execl(python, python, *sys.argv)



if __name__ == "__main__":
    TEST_get_nested_default()