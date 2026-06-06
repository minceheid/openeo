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


import subprocess
import shutil

def ensure_net_bind_capability():
    # Find the real path of python3
    python3_path = shutil.which("python3")
    if not python3_path:
        raise RuntimeError("python3 not found in PATH")

    real_path = os.path.realpath(python3_path)

    # Check current capabilities
    result = subprocess.run(
        ["getcap", real_path],
        capture_output=True, text=True
    )

    if "cap_net_bind_service=eip" in result.stdout.lower():
        #print(f"Capability already set on {real_path}")
        return

    # Not set — apply it
    print(f"Applying CAP_NET_BIND_SERVICE to {real_path}...")
    set_result = subprocess.run(
        ["sudo", "setcap", "CAP_NET_BIND_SERVICE=+eip", real_path],
        capture_output=True, text=True
    )

    if set_result.returncode != 0:
        raise RuntimeError(f"setcap failed: {set_result.stderr.strip()}")

    print("Capability set successfully. Restarting...")
    restart_python()



if __name__ == "__main__":
    print("Do nothing when run as a script.")