#################################################################################
"""
OpenEO Module: Log Viewer helpers
Helpers for the /getlogs endpoint served by the configserver module. Kept free of
globalState imports so that they can be unit tested off-device.

Sources:
  app     - the application event log held in the sqlite "log" table
  journal - the systemd journal for the openeo service
  wifi    - Wi-Fi event lines from the watchdog, setup-portal and wpa_supplicant journals
"""
#################################################################################

import re, subprocess, urllib.parse

LOG_SOURCES = ("app", "journal", "wifi")
DEFAULT_SOURCE = "app"
DEFAULT_LINES = 500
MIN_LINES = 50
MAX_LINES = 5000
JOURNAL_TIMEOUT = 10

WIFI_UNITS = ("openeo_wifi_watchdog", "openeo_portal", "wpa_supplicant")
# journalctl time grows with matches: 1000 took 1.8 s on a Pi Zero W, 5000 up to 9.2 s
# under load, too close to JOURNAL_TIMEOUT for a tab that auto-refreshes every 5 s
WIFI_MAX_LINES = 1000
# Allowlist: old setup-portal request lines contain the Wi-Fi password, so only
# lines whose message starts with a known event name may ever be shown.
WIFI_EVENTS = frozenset({"PIN", "PIN_REJECTED", "UNPIN", "REPIN", "REPIN_GIVEUP", "RECONNECT", "HEALTH_FAIL", "ERROR"})
_LIFECYCLE = (r"\[STARTUP\]", r"\[SHUTDOWN\]")
_WPA_EVENTS = r"wlan0: CTRL-EVENT-(DISCONNECTED|ASSOC-REJECT|SSID-TEMP-DISABLED|CONNECTED)"
_JOURNAL_MESSAGE = re.compile(r"^\S+ \S+ [^\s\[:]+(?:\[\d+\])?: (.*)$")
_WPA_EVENT = re.compile("^" + _WPA_EVENTS + r"\b")
# journalctl --grep pattern for the same messages. It only narrows what journalctl reads,
# so the read stays fast on a large journal; is_wifi_event() remains the security gate.
WIFI_GREP = "^(" + "|".join(sorted(WIFI_EVENTS) + list(_LIFECYCLE) + [_WPA_EVENTS]) + ")( |$)"


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


def _journalctl(args, no_match_ok=False):
    """
    Runs journalctl with the given arguments and returns its output, or an "Error: ..."
    string. Arguments are passed as a list (no shell), so nothing from the request can
    reach a shell. With --grep, journalctl exits 1 with an empty stderr when nothing
    matches; no_match_ok turns that into empty output.
    """
    try:
        result = subprocess.run(
            ["journalctl", *args, "--no-pager", "-o", "short-iso"],
            capture_output=True,
            text=True,
            timeout=JOURNAL_TIMEOUT,
        )
    except FileNotFoundError:
        return "Error: journalctl is not available on this system"
    except subprocess.TimeoutExpired:
        return f"Error: journalctl did not respond within {JOURNAL_TIMEOUT}s"

    if no_match_ok and result.returncode == 1 and not result.stderr.strip():
        return ""
    if result.returncode != 0:
        return f"Error: {result.stderr.strip() or 'journalctl exited with code ' + str(result.returncode)}"
    return result.stdout


def _unit_args(units):
    return [arg for unit in units for arg in ("-u", unit)]


def read_journal(lines):
    """Returns the last n lines of the openeo service journal as a string."""
    return _journalctl([*_unit_args(("openeo",)), "-n", str(int(lines))])


def is_wifi_event(line):
    """
    True only for a short-iso journal line whose message is a known Wi-Fi event. The
    decision is made on the message's first token, never on substrings, so a request
    line that merely mentions an event name (or carries a password) is rejected.
    """
    match = _JOURNAL_MESSAGE.match(line)
    if not match:
        return False
    message = match.group(1)
    if message.startswith(("[STARTUP]", "[SHUTDOWN]")):
        return True
    if message.split(" ", 1)[0] in WIFI_EVENTS:
        return True
    return bool(_WPA_EVENT.match(message))


def filter_wifi_lines(text, lines):
    r"""
    Keeps the Wi-Fi event lines, then the last n of them, as newline-terminated text.
    Splits on newline only: journalctl ends each entry with one, and splitlines() would
    also break on \r, \x85 or \u2028 inside a message and judge the pieces on their own.
    """
    kept = [line for line in text.split("\n") if line and is_wifi_event(line)][-int(lines):]
    return "\n".join(kept) + "\n" if kept else ""


def read_wifi_log(lines):
    """
    Returns the last n Wi-Fi event lines, oldest first, or the Error: text if the journal
    could not be read. journalctl filters with WIFI_GREP and reads newest-first (-r), so it
    stops after n matches rather than formatting the whole journal. n is capped at
    WIFI_MAX_LINES.
    """
    lines = min(int(lines), WIFI_MAX_LINES)
    text = _journalctl([*_unit_args(WIFI_UNITS), "--grep", WIFI_GREP, "-r", "-n", str(lines)],
                       no_match_ok=True)
    if text.startswith("Error:"):
        return text
    oldest_first = "\n".join(reversed(text.split("\n")))
    return filter_wifi_lines(oldest_first, lines)
