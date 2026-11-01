"""Shared Wi-Fi pinning helpers for the portal and the Wi-Fi watchdog.

Every nmcli, ping and iw call goes through a Runner: a callable taking an argument
list and returning a subprocess.CompletedProcess, which never raises. Tests inject a
fake one, so nothing here needs real hardware.
"""

import os
import json
import math
import re
import statistics
import subprocess
import time
from dataclasses import dataclass

# =========================
# Constants (deliberately not user config)
# =========================

SCAN_SAMPLES = 3
SCAN_INTERVAL = 3
PIN_MIN_SIGNAL = 30
HEALTH_PINGS = 10
HEALTH_MAX_LOSS = 20
HEALTH_SETTLE = 120
HEALTH_INTERVAL = 600
HEALTH_FAILS_TO_UNPIN = 2
FAILOVER_AFTER = 60
BLOCKED_RECOVERY_AFTER = 300
RECONNECT_MIN_GAP = 300
REPIN_STABLE = 600
REPIN_RETRY = 3600
REPIN_MAX_REJECTIONS = 3
LOCK_STALE = 300
FLAP_WINDOW = 600
SELF_RECONNECT_GRACE = 30
DROPS_KEEP = 3600
FLAP_DROPS = 3
FLAP_COOLOFF = 3600
STATUS_HOLD = 3600
WEAK_RSSI = -75
WEAK_RUNS = 3
AUTH_FAIL_HOLD = 600
OFFLINE_AFTER = 60
DROPS_WARN = 2
SETUP_LOCK = "/run/openeo-wifi-setup.lock"
SETUP_DONE = "/run/openeo-wifi-setup.done"    # touched when a setup ends; see setup_done_path()
STATE_FILE = "/run/openeo-wifi-watchdog/state.json"
STATUS_FILE = "/run/openeo-wifi-watchdog/status.json"
CONNECTION_NAME = "custom-wifi"
WIFI_INTERFACE = "wlan0"


# =========================
# Runner
# =========================

def setup_done_path(lock_path):
    """The setup-finished marker that sits next to a setup lock."""
    return os.path.splitext(str(lock_path))[0] + ".done"


def make_runner(sudo, timeout=120):
    """Return a Runner. Missing binaries give rc 127 and timeouts rc 124.
    sudo is skipped when already root: sudo logs each command line to the journal,
    and the portal's nmcli calls carry the Wi-Fi password."""
    use_sudo = sudo and os.geteuid() != 0

    def run(args):
        cmd = (['sudo'] if use_sudo else []) + list(args)
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
        except FileNotFoundError:
            return subprocess.CompletedProcess(cmd, 127, "", "")
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, 124, "", "timeout")
    return run


# =========================
# Parsing and formatting
# =========================

def split_terse(line):
    """Split nmcli terse output on unescaped colons, un-escaping each field."""
    fields = [""]
    escaped = False
    for ch in line:
        if escaped:
            fields[-1] += ch
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            fields.append("")
        else:
            fields[-1] += ch
    return fields


def unescape(value):
    """Un-escape a single nmcli -g value, e.g. a BSSID printed as AA\\:BB\\:..."""
    out = ""
    escaped = False
    for ch in value:
        if escaped or ch != "\\":
            out += ch
            escaped = False
        else:
            escaped = True
    return out


def format_event(event, fields):
    """Format a log line as 'EVENT key=value ...', leaving out None values."""
    parts = [event] + [f"{k}={v}" for k, v in fields.items() if v is not None]
    return " ".join(parts)


# =========================
# Scan sampling and selection rule
# =========================

@dataclass
class Selection:
    bssid: str = None
    signal: int = None
    runner_up: int = None
    samples: int = 0
    reason: str = "single"    # pin | single | weak | noscan | excluded


def parse_scan(stdout):
    """Parse 'nmcli -t -f BSSID,SSID,SIGNAL' output into (bssid, ssid, signal) tuples."""
    rows = []
    for line in stdout.splitlines():
        fields = split_terse(line)
        if len(fields) != 3 or not fields[0]:
            continue
        try:
            rows.append((fields[0], fields[1], int(fields[2])))
        except ValueError:
            continue
    return rows


def select_bssid(samples, ssid, exclude=frozenset()):
    """Apply the selection rule to scan samples for the target SSID.

    The multi-AP test runs on every candidate; then BSSIDs in 'exclude' are passed over
    for the pin, though they still count as the runner-up.
    """
    if not samples:
        return Selection(reason="noscan")

    seen = {}    # bssid -> list of per-sample signals
    for sample in samples:
        best_in_sample = {}
        for bssid, row_ssid, signal in sample:
            if row_ssid == ssid and bssid:
                best_in_sample[bssid] = max(signal, best_in_sample.get(bssid, signal))
        for bssid, signal in best_in_sample.items():
            seen.setdefault(bssid, []).append(signal)

    needed = math.ceil(len(samples) / 2)
    candidates = [(statistics.median_low(sigs), len(sigs), bssid)
                  for bssid, sigs in seen.items() if len(sigs) >= needed]
    # Strongest first; ties go to the node seen most often, then the lowest BSSID
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2]))

    if len(candidates) < 2:
        return Selection(samples=len(samples), reason="single")
    excluded = {norm_bssid(b) for b in exclude}
    allowed = [c for c in candidates if norm_bssid(c[2]) not in excluded]
    if not allowed:
        return Selection(samples=len(samples), reason="excluded")
    best = allowed[0]
    second = next(c for c in candidates if c is not best)
    if best[0] < PIN_MIN_SIGNAL:
        return Selection(signal=best[0], runner_up=second[0], samples=len(samples), reason="weak")
    return Selection(best[2], best[0], second[0], len(samples), "pin")


def scan_samples(run, sleep=time.sleep):
    """Take SCAN_SAMPLES scans. Failed scans are skipped; if all fail, use NM's cached results."""
    cmd = ['nmcli', '-t', '-f', 'BSSID,SSID,SIGNAL', 'dev', 'wifi', 'list',
           'ifname', WIFI_INTERFACE, '--rescan']
    samples = []
    for i in range(SCAN_SAMPLES):
        if i:
            sleep(SCAN_INTERVAL)
        result = run(cmd + ['yes'])
        if result.returncode == 0:
            samples.append(parse_scan(result.stdout))
    if not samples:
        result = run(cmd + ['no'])
        if result.returncode == 0:
            samples.append(parse_scan(result.stdout))
    return samples


def choose_pin(run, ssid, sleep=time.sleep, exclude=frozenset()):
    return select_bssid(scan_samples(run, sleep), ssid, exclude)


# =========================
# Health check and radio counters
# =========================

@dataclass
class HealthResult:
    passed: bool
    loss: int = None
    skipped: bool = False


SKIPPED = HealthResult(True, None, True)


def health_check(run):
    """Ping the gateway over wlan0. Anything that stops the check running counts as a pass."""
    gateway = run(['nmcli', '-g', 'IP4.GATEWAY', 'device', 'show', WIFI_INTERFACE]).stdout.strip()
    if not gateway:
        return SKIPPED
    result = run(['ping', '-c', str(HEALTH_PINGS), '-i', '0.2', '-W', '1', '-I', WIFI_INTERFACE, gateway])
    # ping exits 1 when replies are lost, so parse the summary whatever the return code
    match = re.search(r"(\d+(?:\.\d+)?)% packet loss", result.stdout or "")
    if result.returncode == 127 or not match:
        return SKIPPED
    loss = round(float(match.group(1)))
    return HealthResult(loss <= HEALTH_MAX_LOSS, loss, False)


def station_info(run):
    """Read signal and tx counters from 'iw dev wlan0 station dump'. Logged only, never acted on."""
    result = run(['iw', 'dev', WIFI_INTERFACE, 'station', 'dump'])
    if result.returncode != 0:
        return {}
    patterns = [("rssi", r"^\s*signal:\s*(-?\d+)", int),
                ("tx_bitrate", r"^\s*tx bitrate:\s*([\d.]+)", float),
                ("tx_retries", r"^\s*tx retries:\s*(\d+)", int),
                ("tx_failed", r"^\s*tx failed:\s*(\d+)", int)]
    info = {}
    for key, pattern, conv in patterns:
        match = re.search(pattern, result.stdout, re.MULTILINE)
        if match:
            info[key] = conv(match.group(1))
    return info


# =========================
# nmcli wrappers for the custom-wifi profile
# =========================

def profile_exists(run):
    return run(['nmcli', '-g', 'connection.id', 'connection', 'show', CONNECTION_NAME]).returncode == 0


def profile_uuid(run):
    """UUID of the custom-wifi profile. It changes whenever setup re-creates the profile."""
    result = run(['nmcli', '-g', 'connection.uuid', 'connection', 'show', CONNECTION_NAME])
    return result.stdout.strip() if result.returncode == 0 else ""


def get_pin(run):
    result = run(['nmcli', '-g', '802-11-wireless.bssid', 'connection', 'show', CONNECTION_NAME])
    return unescape(result.stdout.strip()) if result.returncode == 0 else ""


def set_pin(run, bssid):
    return run(['nmcli', 'connection', 'modify', CONNECTION_NAME, '802-11-wireless.bssid', bssid]).returncode == 0


def clear_pin(run):
    return set_pin(run, "")


def con_up(run):
    return run(['nmcli', 'connection', 'up', CONNECTION_NAME])


def norm_bssid(b):
    return (b or "").strip().upper()


@dataclass
class LinkState:
    up: bool
    bssid: str | None = None
    rssi: int | None = None

    def __post_init__(self):
        if self.bssid is not None:
            self.bssid = norm_bssid(self.bssid) or None


def iw_link(run):
    """Kernel view of the link: (state, bssid, rssi); state is connected, disconnected or unknown."""
    result = run(['iw', 'dev', WIFI_INTERFACE, 'link'])
    if result.returncode != 0:
        return "unknown", None, None
    out = result.stdout
    m = re.search(r'Connected to ([0-9A-Fa-f:]{17})', out)
    if m:
        sig = re.search(r'signal:\s*(-?\d+)', out)
        return "connected", norm_bssid(m.group(1)), int(sig.group(1)) if sig else None
    if 'Not connected' in out:
        return "disconnected", None, None
    return "unknown", None, None


def link_state(run):
    result = run(['nmcli', '-g', 'GENERAL.STATE,GENERAL.CONNECTION', 'device', 'show', WIFI_INTERFACE])
    lines = result.stdout.splitlines() + ["", ""]
    nm_up = lines[0].startswith("100") and lines[1].strip() == CONNECTION_NAME
    state, bssid, rssi = iw_link(run)
    return LinkState(nm_up and state != "disconnected", bssid, rssi)


def link_up(run):
    return link_state(run).up


def profile_ssid(run):
    result = run(['nmcli', '-g', '802-11-wireless.ssid', 'connection', 'show', CONNECTION_NAME])
    return unescape(result.stdout.strip()) if result.returncode == 0 else ""


# =========================
# wpa_supplicant journal (the source of drop events)
# =========================

DROP_RE = re.compile(r'^wlan0: CTRL-EVENT-DISCONNECTED bssid=([0-9A-Fa-f:]{17})')


@dataclass
class WpaEvent:
    kind: str              # "drop" or "auth_fail"
    at: float              # monotonic seconds
    bssid: str | None = None


def parse_wpa_journal(stdout, boot_id=""):
    """Parse `journalctl -o json` output (one object per line) into events and the last cursor."""
    events, cursor = [], None
    for line in stdout.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        cursor = entry.get("__CURSOR", cursor)
        if boot_id and entry.get("_BOOT_ID") != boot_id:
            continue
        message = entry.get("MESSAGE")
        if not isinstance(message, str):
            continue
        try:
            at = int(entry["__MONOTONIC_TIMESTAMP"]) / 1e6
        except (KeyError, TypeError, ValueError):
            continue
        m = DROP_RE.match(message)
        if m:
            events.append(WpaEvent("drop", at, norm_bssid(m.group(1))))
        elif 'reason=WRONG_KEY' in message or 'pre-shared key may be incorrect' in message:
            events.append(WpaEvent("auth_fail", at))
    return events, cursor


def read_wpa_events(run, cursor, boot_id):
    """New wpa_supplicant events since the cursor, or the last FLAP_WINDOW seconds without one."""
    base = ['journalctl', '-t', 'wpa_supplicant', '-b']
    tail = ['-o', 'json', '--no-pager']
    result = run(base + ['--after-cursor', cursor] + tail) if cursor else None
    if result is None or result.returncode != 0:
        result = run(base + ['--since', f'-{FLAP_WINDOW}s'] + tail)
    events, new_cursor = parse_wpa_journal(result.stdout, boot_id)
    return events, new_cursor or cursor


def boot_id():
    try:
        with open('/proc/sys/kernel/random/boot_id') as f:
            return f.read().strip().replace('-', '')
    except OSError:
        return ""
