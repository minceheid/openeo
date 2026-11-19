import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Index 0 so that "import portal" finds portal/portal.py, not the portal/ directory
sys.path.insert(0, os.path.join(HERE, "..", "portal", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "portal"))


def cp(rc, stdout="", stderr=""):
    return subprocess.CompletedProcess([], rc, stdout, stderr)


def ok(stdout=""):
    return cp(0, stdout)


def fail(rc=1, stderr=""):
    return cp(rc, "", stderr)


class FakeRunner:
    """Stands in for a wifi_pinning Runner. responses is a list of (prefix, result) where
    result is a CompletedProcess, a callable taking args, or a list consumed one per call."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        for prefix, result in self.responses:
            if tuple(args[:len(prefix)]) == tuple(prefix):
                if isinstance(result, list):
                    result = result.pop(0) if len(result) > 1 else result[0]
                return result(args) if callable(result) else result
        return ok("")
