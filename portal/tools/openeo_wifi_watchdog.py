#!/usr/bin/env python3
"""openeo Wi-Fi watchdog. Run every 60 s by openeo_wifi_watchdog.timer, as root.

Unpins custom-wifi when its pinned node goes away or stops carrying traffic, reconnects
when NM has given up, and re-pins once the link has been stable again. The rules live in
two pure functions, decide() and after_health(), so they can be unit-tested; the code
around them gathers inputs and carries out the actions. See the design spec §6.
"""

import json
import math
import os
import sys
import tempfile
import time
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
import wifi_pinning as wp

# kind: CLEAR_PIN | CON_UP | CHECK_HEALTH | REPIN_SCAN | LOG
Action = namedtuple("Action", "kind fields")


def default_state():
    return {
        "down_since": None,
        "up_since": None,
        "last_reconnect": None,
        "unpinned_by_watchdog": False,
        "last_repin_attempt": None,
        "roam_count": 0,
        "last_health_check": None,
        "health_failures": 0,
        "repin_rejections": 0,
        "profile_uuid": None,
        "journal_cursor": None,
        "drops": [],            # [at, bssid] pairs, monotonic seconds
        "last_auth_fail": None,
        "excluded_bssids": [],  # never re-pinned until a new setup or a reboot (/run)
        "last_unpin_reason": None,
        "last_unpin_at": None,
        "last_flap": None,      # {"bssid", "drops", "span"} of the last flapping unpin
        "pinned_at": None,      # when the watchdog re-pinned; None for a pin set by setup
        "weak_runs": 0,         # consecutive runs with a weak signal
        "status_level": None,   # the last status written, so 'since' survives between runs
        "status_code": None,
        "status_since": None,   # wall-clock epoch
        "last_event": None,     # last executor line other than RECONNECT
        "last_event_at": None,  # wall-clock epoch
    }


def _log(event, **fields):
    return Action("LOG", {"event": event, **fields})


def _con_up(reason):
    return Action("CON_UP", {"reason": reason})


def _since(now, then):
    """Seconds since 'then', or None if it never happened."""
    return None if then is None else now - then


def _exclude(state, bssid):
    """Keep the watchdog from re-pinning this node."""
    bssid = wp.norm_bssid(bssid)
    if bssid and bssid not in state["excluded_bssids"]:
        state["excluded_bssids"] = state["excluded_bssids"] + [bssid]


def _unpin(state, now, bssid, reason, **extra):
    """Clear the pin, exclude the node from re-pinning and reconnect by SSID (rules 1a, 1 and 3)."""
    _exclude(state, bssid)
    state["last_unpin_reason"] = reason
    state["last_unpin_at"] = now
    state["pinned_at"] = None
    state["unpinned_by_watchdog"] = True
    state["roam_count"] += 1
    state["last_reconnect"] = now
    state["up_since"] = None
    state["health_failures"] = 0
    state["repin_rejections"] = 0
    return [Action("CLEAR_PIN", {}),
            _log("UNPIN", bssid=bssid, reason=reason, **extra, roam_count=state["roam_count"]),
            _con_up("failover" if reason == "down" else reason)]


def record_events(state, events, now, *, lock_age, setup_done_age=None):
    """Fold journal events into the state. Pure: returns a new state.
    setup_done_age: seconds since the portal last finished a setup, or None."""
    state = dict(state)
    state["drops"] = [list(d) for d in state["drops"] if d[0] >= now - wp.DROPS_KEEP]
    if lock_age is not None and lock_age < wp.LOCK_STALE:
        return state    # the portal is setting up Wi-Fi; its disconnects are not flaps
    # A setup's last reconnects are often read only after its lock has gone. A setup makes
    # a new profile, so nothing before it ended (plus the grace) counts against the new one
    setup_end = now - setup_done_age if setup_done_age is not None else None
    last_reconnect = state["last_reconnect"]
    for event in events:
        if event.kind == "auth_fail":
            state["last_auth_fail"] = max(state["last_auth_fail"] or event.at, event.at)
            continue
        if setup_end is not None and event.at <= setup_end + wp.SELF_RECONNECT_GRACE:
            continue    # the setup's own reconnects
        if last_reconnect is not None and 0 <= event.at - last_reconnect <= wp.SELF_RECONNECT_GRACE:
            continue    # our own reconnect, not a drop
        drop = [event.at, wp.norm_bssid(event.bssid)]
        if drop not in state["drops"]:
            state["drops"].append(drop)
    return state


def decide(state, now, *, link_up, pinned, profile_exists, lock_age):
    """Decide this run's actions from the link state. Returns (actions, new_state)."""
    # Guards: unconfigured charger, or the portal is setting up Wi-Fi right now
    if not profile_exists or (lock_age is not None and lock_age < wp.LOCK_STALE):
        return [], state

    state = dict(state)
    if link_up:
        state["down_since"] = None
        if state["up_since"] is None:
            state["up_since"] = now
    else:
        state["up_since"] = None
        if state["down_since"] is None:
            state["down_since"] = now

    down_for = _since(now, state["down_since"])
    up_for = _since(now, state["up_since"])

    # Rule 1a: flapping. The pinned node keeps dropping us; let NM roam by SSID instead
    if pinned:
        pin = wp.norm_bssid(pinned)
        # Drops from before a watchdog re-pin happened while unpinned; they are not this pin's
        recent = [at for at, bssid in state["drops"]
                  if bssid == pin and now - at <= wp.FLAP_WINDOW
                  and (state["pinned_at"] is None or at >= state["pinned_at"])]
        if len(recent) >= wp.FLAP_DROPS:
            actions = _unpin(state, now, pinned, "flapping", drops=len(recent), window=wp.FLAP_WINDOW)
            state["drops"] = []
            state["last_flap"] = {"bssid": pin, "drops": len(recent), "span": int(max(recent) - min(recent))}
            return actions, state

    # Rule 1: failover. A pinned node that has gone away must not strand the charger
    if not link_up and pinned and down_for >= wp.FAILOVER_AFTER:
        return _unpin(state, now, pinned, "down", down_for=int(down_for)), state

    # Rule 2: blocked-recovery. An explicit activation clears NM's no-secrets block
    if not link_up and down_for >= wp.BLOCKED_RECOVERY_AFTER:
        since_reconnect = _since(now, state["last_reconnect"])
        if since_reconnect is None or since_reconnect >= wp.RECONNECT_MIN_GAP:
            state["last_reconnect"] = now
            return [_con_up("blocked")], state

    # Rule 3: periodic health check of a pinned link
    if link_up and pinned and up_for >= wp.HEALTH_SETTLE:
        since_check = _since(now, state["last_health_check"])
        if state["health_failures"] > 0 or since_check is None or since_check >= wp.HEALTH_INTERVAL:
            return [Action("CHECK_HEALTH", {"source": "periodic"})], state

    # Rule 4: re-pin once the link has been stable after a watchdog unpin
    if link_up and not pinned and state["unpinned_by_watchdog"] and up_for >= wp.REPIN_STABLE:
        since_attempt = _since(now, state["last_repin_attempt"])
        # A node that flapped gets an hour's cool-off before any re-pin
        cooled_off = (state["last_unpin_reason"] != "flapping"
                      or now - state["last_unpin_at"] >= wp.FLAP_COOLOFF)
        if cooled_off and (since_attempt is None or since_attempt >= wp.REPIN_RETRY):
            state["last_repin_attempt"] = now
            return [Action("REPIN_SCAN", {})], state

    return [], state


def after_health(state, now, source, passed, bssid=None):
    """Act on a health check result. source is 'periodic' (rule 3) or 'repin' (rule 4);
    bssid is the node checked: the current pin, or the one just pinned for a re-pin."""
    state = dict(state)

    if source == "periodic":
        state["last_health_check"] = now
        if passed:
            state["health_failures"] = 0
            return [], state
        state["health_failures"] += 1
        actions = [_log("HEALTH_FAIL", failures=state["health_failures"])]
        if state["health_failures"] >= wp.HEALTH_FAILS_TO_UNPIN:
            actions += _unpin(state, now, bssid, "unhealthy")
        return actions, state

    # Re-pin: the script has already set the pin and re-activated
    state["last_reconnect"] = now
    state["up_since"] = None
    if passed:
        state["unpinned_by_watchdog"] = False
        state["pinned_at"] = now
        state["last_health_check"] = now
        state["health_failures"] = 0
        state["repin_rejections"] = 0
        return [_log("REPIN")], state

    state["repin_rejections"] += 1
    _exclude(state, bssid)
    actions = [Action("CLEAR_PIN", {}), _log("PIN_REJECTED", source="repin"), _con_up("rejected")]
    if state["repin_rejections"] < wp.REPIN_MAX_REJECTIONS:
        state["unpinned_by_watchdog"] = True
    else:
        # A router that ignores ping would otherwise cost two blips an hour forever
        state["unpinned_by_watchdog"] = False
        actions.append(_log("REPIN_GIVEUP", rejections=state["repin_rejections"]))
    return actions, state


# =========================
# Health status (spec §4.4)
# =========================

def _health(state, now, now_wall, link, pinned, ssid, drops_1h):
    """The first matching (level, code, message), in the spec table's order."""
    # Only while disconnected: handshake timeouts during AP flapping also log WRONG_KEY
    if (not link.up and state["last_auth_fail"] is not None
            and now - state["last_auth_fail"] <= wp.AUTH_FAIL_HOLD):
        return ("problem", "auth_failed",
                "The Wi-Fi password was rejected. Check it in the setup portal, "
                "or check whether it changed on your router.")
    if not link.up and state["down_since"] is not None and now - state["down_since"] >= wp.OFFLINE_AFTER:
        down_at = time.strftime("%H:%M", time.localtime(now_wall - (now - state["down_since"])))
        return "problem", "offline", f"Not connected to Wi-Fi since {down_at}."
    if (state["last_unpin_reason"] == "flapping" and state["last_unpin_at"] is not None
            and now - state["last_unpin_at"] < wp.STATUS_HOLD):
        flap = state["last_flap"] or {}
        minutes = max(1, math.ceil(flap.get("span", 0) / 60))
        return ("problem", "flapping",
                f"Access point {flap.get('bssid') or 'unknown'} kept disconnecting the charger "
                f"({flap.get('drops', 0)} drops in {minutes} min). It now connects to any access point "
                f"on {ssid}. If this repeats, check that access point's minimum-signal (min-RSSI) "
                f"setting or its position.")
    recent = [d for d in state["drops"] if now - d[0] <= wp.FLAP_WINDOW]
    if not pinned and len(recent) >= wp.FLAP_DROPS:
        return ("problem", "unstable_network",
                "Wi-Fi keeps dropping on every access point. The signal at the charger may be "
                "too weak, or the network may be dropping it.")
    if state["unpinned_by_watchdog"]:
        bad = state["excluded_bssids"][-1] if state["excluded_bssids"] else "an access point"
        return ("warning", "fallback",
                f"Running without a fixed access point after a problem with {bad}. "
                f"It will try another access point later.")
    if drops_1h >= wp.DROPS_WARN:
        return "warning", "drops", f"Wi-Fi dropped {drops_1h} times in the last hour."
    if state["weak_runs"] >= wp.WEAK_RUNS:
        return ("warning", "weak_signal",
                f"Weak Wi-Fi signal at the charger ({link.rssi} dBm). Access points may disconnect it.")
    return "ok", "ok", "Wi-Fi OK"


def classify(state, now, now_wall, *, profile_exists, lock_age, link, pinned, ssid):
    """This run's health status for the owner. Pure: returns (status, new_state)."""
    state = dict(state)
    drops_1h = sum(1 for d in state["drops"] if now - d[0] <= wp.DROPS_KEEP)
    if not profile_exists or (lock_age is not None and lock_age < wp.LOCK_STALE):
        level, code, message, since = "unknown", "", "", None
    else:
        weak = link.rssi is not None and link.rssi <= wp.WEAK_RSSI
        state["weak_runs"] = state["weak_runs"] + 1 if weak else 0
        level, code, message = _health(state, now, now_wall, link, pinned, ssid, drops_1h)
        if (level, code) != (state["status_level"], state["status_code"]):
            state["status_level"], state["status_code"] = level, code
            state["status_since"] = int(now_wall)
        since = state["status_since"]
    status = {
        "level": level,
        "code": code,
        "message": message,
        "since": since,
        "updated": int(now_wall),
        "pinned_bssid": wp.norm_bssid(pinned) or None,
        "current_bssid": wp.norm_bssid(link.bssid) or None,
        "rssi": link.rssi,
        "drops_1h": drops_1h,
        "excluded_bssids": list(state["excluded_bssids"]),
        "last_event": state["last_event"],
        "last_event_at": state["last_event_at"],
    }
    return status, state


# =========================
# State file
# =========================

def load_state(path):
    """Read the state file. Missing, corrupt or partial files fall back to the defaults."""
    state = default_state()
    try:
        with open(path) as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            state.update({k: v for k, v in saved.items() if k in state})
    except (OSError, ValueError):
        pass
    return state


def save_state(path, state):
    directory = os.path.dirname(os.fspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def save_status(path, status):
    """Write the status file atomically and world-readable: it holds no secrets, and the
    main app (not root) reads it."""
    directory = os.path.dirname(os.fspath(path))
    os.makedirs(directory, exist_ok=True)
    os.chmod(directory, 0o755)
    fd, tmp = tempfile.mkstemp(dir=directory)
    with os.fdopen(fd, "w") as f:
        json.dump(status, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def lock_age(path, now_wall):
    """Age of the portal's setup lock in seconds, or None if there is none.
    File times are wall-clock, so this is the one place wall time is used."""
    try:
        return now_wall - os.stat(path).st_mtime
    except OSError:
        return None


# =========================
# Running the actions
# =========================

# Fields the executor knows from this run, per event, placed before the event's own fields
CONTEXT_FIELDS = {
    "HEALTH_FAIL": ("bssid", "loss"),
    "UNPIN": ("bssid",),
    "PIN_REJECTED": ("bssid", "signal", "loss"),
    "REPIN": ("bssid", "signal", "loss"),
}
MUTATING = ("CLEAR_PIN", "CON_UP")


class SetupStarted(Exception):
    """The portal took the setup lock while this run was acting."""


def _loss(result):
    return None if result.skipped else f"{result.loss}%"


class Executor:
    def __init__(self, run, now, now_wall, lock_path, sleep, pinned):
        self.run, self.now, self.now_wall = run, now, now_wall
        self.lock_path, self.sleep = lock_path, sleep
        self.ctx = {"bssid": pinned or None}
        self.lines = []

    def emit(self, line):
        print(line, flush=True)
        self.lines.append(line)

    def check_lock(self):
        age = lock_age(self.lock_path, self.now_wall)
        if age is not None and age < wp.LOCK_STALE:
            raise SetupStarted()

    def log(self, fields):
        event = fields["event"]
        merged = {k: self.ctx.get(k) for k in CONTEXT_FIELDS.get(event, ())}
        for key, value in fields.items():
            if key != "event" and (value is not None or key not in merged):
                merged[key] = value
        if event == "REPIN":
            merged.update(self.ctx.get("station", {}))
        self.emit(wp.format_event(event, merged))

    def execute(self, actions, state):
        for action in actions:
            if action.kind in MUTATING:
                self.check_lock()
            if action.kind == "CLEAR_PIN":
                wp.clear_pin(self.run)
            elif action.kind == "CON_UP":
                rc = wp.con_up(self.run).returncode
                self.emit(wp.format_event("RECONNECT", {"reason": action.fields["reason"], "rc": rc}))
            elif action.kind == "LOG":
                self.log(action.fields)
            elif action.kind == "CHECK_HEALTH":
                result = wp.health_check(self.run)
                self.ctx["loss"] = _loss(result)
                more, state = after_health(state, self.now, "periodic", result.passed, self.ctx["bssid"])
                state = self.execute(more, state)
            elif action.kind == "REPIN_SCAN":
                state = self.repin(state)
        return state

    def repin(self, state):
        selection = wp.choose_pin(self.run, wp.profile_ssid(self.run), self.sleep,
                                  exclude=frozenset(state["excluded_bssids"]))
        if not selection.bssid:
            return state    # stay unpinned, try again in an hour
        self.check_lock()
        wp.set_pin(self.run, selection.bssid)
        # Always re-activate: a profile change doesn't reach the running connection
        if wp.con_up(self.run).returncode == 0:
            result = wp.health_check(self.run)
        else:
            # The node refused us; never keep a pin on it (as at setup, §5 step 7)
            result = wp.HealthResult(False, None, True)
        self.ctx.update(bssid=selection.bssid, signal=selection.signal, loss=_loss(result))
        if result.passed:
            self.ctx["station"] = wp.station_info(self.run)
        more, state = after_health(state, self.now, "repin", result.passed, self.ctx["bssid"])
        return self.execute(more, state)


def run_once(run, now, now_wall, state_path=wp.STATE_FILE, lock_path=wp.SETUP_LOCK, sleep=time.sleep,
             status_path=None):
    """One watchdog run. 'now' is monotonic time; returns the log lines it printed.
    status_path None means wp.STATUS_FILE. A run that ends in ERROR leaves the status file
    alone, so the main app sees it go stale."""
    executor = None
    try:
        state = load_state(state_path)
        # A new portal setup re-creates the profile; nothing learned about the old one applies
        uuid = wp.profile_uuid(run)
        if uuid and uuid != state["profile_uuid"]:
            state = default_state() | {"profile_uuid": uuid}
        events, state["journal_cursor"] = wp.read_wpa_events(run, state["journal_cursor"], wp.boot_id())
        lock = lock_age(lock_path, now_wall)
        state = record_events(state, events, now, lock_age=lock,
                              setup_done_age=lock_age(wp.setup_done_path(lock_path), now_wall))
        pinned = wp.get_pin(run)
        executor = Executor(run, now, now_wall, lock_path, sleep, pinned)
        link = wp.link_state(run)
        profile_exists = wp.profile_exists(run)
        actions, state = decide(state, now,
                                link_up=link.up,
                                pinned=pinned,
                                profile_exists=profile_exists,
                                lock_age=lock)
        save_state(state_path, state)
        try:
            state = executor.execute(actions, state)
        except SetupStarted:
            pass
        save_state(state_path, state)

        events = [line for line in executor.lines if not line.startswith("RECONNECT")]
        if events:
            state["last_event"], state["last_event_at"] = events[-1], int(now_wall)
        # The actions may have changed the pin
        status, state = classify(state, now, now_wall,
                                 profile_exists=profile_exists,
                                 lock_age=lock,
                                 link=link,
                                 pinned=wp.get_pin(run),
                                 ssid=wp.profile_ssid(run))
        save_state(state_path, state)
        save_status(status_path or wp.STATUS_FILE, status)
        return executor.lines
    except Exception as e:
        line = f"ERROR {type(e).__name__}: {e}"
        print(line, flush=True)
        return (executor.lines if executor else []) + [line]


def main():
    run_once(wp.make_runner(sudo=False), time.monotonic(), time.time())


if __name__ == "__main__":
    main()
