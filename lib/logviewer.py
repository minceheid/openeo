#################################################################################
"""
OpenEO Module: Log Viewer helpers
Helpers for the /getlogs endpoint served by the configserver module. Kept free of
globalState imports so that they can be unit tested off-device.

Sources:
  app     - the application event log held in the sqlite "log" table
  journal - the systemd journal for the openeo service
"""
#################################################################################

import subprocess, urllib.parse

LOG_SOURCES = ("app", "journal")
DEFAULT_SOURCE = "app"
DEFAULT_LINES = 500
MIN_LINES = 50
MAX_LINES = 5000
JOURNAL_TIMEOUT = 10


def parse_log_query(path):
    """
    Parses the query string of a /getlogs request, returning (source, lines).
    Unknown sources fall back to the default, and the line count is clamped.
    """
    query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)

    source = query.get("source", [DEFAULT_SOURCE])[0]
    if source not in LOG_SOURCES:
        source = DEFAULT_SOURCE

    try:
        lines = int(query.get("lines", [DEFAULT_LINES])[0])
    except ValueError:
        lines = DEFAULT_LINES
    lines = max(MIN_LINES, min(MAX_LINES, lines))

    return source, lines


def read_journal(lines):
    """
    Returns the last n lines of the openeo service journal as a string. Arguments are
    passed as a list (no shell), so nothing from the request can reach a shell.
    """
    try:
        result = subprocess.run(
            ["journalctl", "-u", "openeo", "-n", str(int(lines)), "--no-pager", "-o", "short-iso"],
            capture_output=True,
            text=True,
            timeout=JOURNAL_TIMEOUT,
        )
    except FileNotFoundError:
        return "Error: journalctl is not available on this system"
    except subprocess.TimeoutExpired:
        return f"Error: journalctl did not respond within {JOURNAL_TIMEOUT}s"

    if result.returncode != 0:
        return f"Error: {result.stderr.strip() or 'journalctl exited with code ' + str(result.returncode)}"
    return result.stdout
