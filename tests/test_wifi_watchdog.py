from openeo_wifi_watchdog import decide, after_health, default_state

import pytest

P = "AA:BB:CC:DD:EE:01"


@pytest.fixture(autouse=True)
def _status_file_in_tmp(tmp_path, monkeypatch):
    """run_once writes the status file; never let a test write to /run."""
    import openeo_wifi_watchdog as wd
    monkeypatch.setattr(wd.wp, "STATUS_FILE", str(tmp_path / "status.json"))


def step(state, now, up, pinned=P, profile=True, lock_age=None):
    return decide(state, now, link_up=up, pinned=pinned, profile_exists=profile, lock_age=lock_age)


def kinds(actions):
    return [a.kind for a in actions]


def events(actions):
    return [a.fields["event"] for a in actions if a.kind == "LOG"]


# =========================
# decide() / after_health() (§6.4)
# =========================

def test_steady_up_no_action_before_settle():
    s = default_state()
    for t in (0, 60, 119):
        a, s = step(s, t, True)
        assert a == []
    assert s["up_since"] == 0 and s["down_since"] is None


def test_short_blip_no_action():
    s = default_state()
    _, s = step(s, 0, True)
    a, s = step(s, 60, False)
    a, s = step(s, 100, False)
    assert a == []


def test_pinned_outage_fails_over_at_60s():
    s = default_state()
    _, s = step(s, 0, False)
    a, s = step(s, 59, False)
    assert a == []
    a, s = step(s, 60, False)
    assert kinds(a) == ["CLEAR_PIN", "LOG", "CON_UP"] and a[2].fields["reason"] == "failover"
    assert a[1].fields == {"event": "UNPIN", "bssid": P, "reason": "down", "down_for": 60, "roam_count": 1}
    assert s["unpinned_by_watchdog"] and s["roam_count"] == 1 and s["up_since"] is None
    assert s["last_reconnect"] == 60


def test_long_outage_blocked_recovery_then_rate_limited():
    s = default_state()
    _, s = step(s, 0, False, pinned="")
    a, s = step(s, 300, False, pinned="")
    assert kinds(a) == ["CON_UP"] and a[0].fields["reason"] == "blocked"
    a, s = step(s, 360, False, pinned="")
    assert a == []
    a, s = step(s, 600, False, pinned="")
    assert a[0].fields["reason"] == "blocked"


def test_repin_after_10_min_stable_then_retry_after_60():
    s = default_state() | {"unpinned_by_watchdog": True}
    _, s = step(s, 0, True, pinned="")
    a, s = step(s, 599, True, pinned="")
    assert a == []
    a, s = step(s, 600, True, pinned="")
    assert kinds(a) == ["REPIN_SCAN"] and s["last_repin_attempt"] == 600
    a, s = step(s, 900, True, pinned="")     # no qualifying node last time, wait an hour
    assert a == []
    a, s = step(s, 600 + 3600, True, pinned="")
    assert kinds(a) == ["REPIN_SCAN"]


def test_health_due_rules():
    s = default_state()
    _, s = step(s, 0, True)
    a, s = step(s, 119, True)                # inside HEALTH_SETTLE
    assert a == []
    a, s = step(s, 120, True)
    assert kinds(a) == ["CHECK_HEALTH"] and a[0].fields["source"] == "periodic"
    _, s = after_health(s, 120, "periodic", True)
    a, s = step(s, 700, True)
    assert a == []
    a, s = step(s, 720, True)
    assert kinds(a) == ["CHECK_HEALTH"]
    a, _ = step(s, 2000, True, pinned="")    # unpinned: never checked
    assert a == []


def test_one_failure_then_pass_no_unpin():
    s = default_state()
    _, s = step(s, 0, True)
    _, s = step(s, 120, True)
    a, s = after_health(s, 120, "periodic", False)
    assert events(a) == ["HEALTH_FAIL"] and a[0].fields["failures"] == 1
    a, s = step(s, 180, True)                # confirming check on the next run
    assert kinds(a) == ["CHECK_HEALTH"]
    a, s = after_health(s, 180, "periodic", True)
    assert s["health_failures"] == 0 and "CLEAR_PIN" not in kinds(a)


def test_two_failures_unpin_unhealthy():
    s = default_state()
    _, s = step(s, 0, True)
    _, s = after_health(s, 120, "periodic", False)
    a, s = after_health(s, 180, "periodic", False)
    assert kinds(a) == ["LOG", "CLEAR_PIN", "LOG", "CON_UP"]
    assert events(a) == ["HEALTH_FAIL", "UNPIN"] and a[2].fields["reason"] == "unhealthy"
    assert a[3].fields["reason"] == "unhealthy"
    assert s["unpinned_by_watchdog"] and s["up_since"] is None and s["health_failures"] == 0
    assert s["roam_count"] == 1 and s["repin_rejections"] == 0


def test_skipped_check_counts_as_pass():
    # The script passes passed=True for a skipped check; health_failures resets
    s = default_state() | {"health_failures": 1}
    _, s = after_health(s, 100, "periodic", True)
    assert s["health_failures"] == 0


def test_repin_pass_sets_health_clock_and_resets():
    s = default_state() | {"unpinned_by_watchdog": True, "repin_rejections": 2, "up_since": 0}
    a, s = after_health(s, 5000, "repin", True)
    assert events(a) == ["REPIN"] and s["last_health_check"] == 5000
    assert s["repin_rejections"] == 0 and not s["unpinned_by_watchdog"]
    assert s["up_since"] is None and s["last_reconnect"] == 5000


def test_repin_rejected_then_gives_up_on_third():
    s = default_state() | {"unpinned_by_watchdog": True}
    for n in (1, 2):
        a, s = after_health(s, n * 3600, "repin", False)
        assert kinds(a) == ["CLEAR_PIN", "LOG", "CON_UP"] and a[2].fields["reason"] == "rejected"
        assert events(a) == ["PIN_REJECTED"] and s["unpinned_by_watchdog"] and s["repin_rejections"] == n
    a, s = after_health(s, 3 * 3600, "repin", False)
    assert events(a) == ["PIN_REJECTED", "REPIN_GIVEUP"] and not s["unpinned_by_watchdog"]
    _, s = step(s, 3 * 3600 + 1, True, pinned="")
    a, _ = step(s, 9 * 3600, True, pinned="")
    assert a == []


def test_repin_no_node_does_not_count_as_rejection():
    s = default_state() | {"unpinned_by_watchdog": True}
    _, s = step(s, 0, True, pinned="")
    _, s = step(s, 600, True, pinned="")     # REPIN_SCAN; script found no node, so no after_health
    assert s["repin_rejections"] == 0 and s["unpinned_by_watchdog"]


def test_new_unpin_resets_rejections():
    s = default_state() | {"repin_rejections": 2}
    _, s = step(s, 0, False)
    _, s = step(s, 60, False)
    assert s["repin_rejections"] == 0


def test_guards_lock_and_profile():
    s = default_state()
    _, s = step(s, 0, False)
    assert step(s, 100, False, lock_age=10) == ([], s)
    assert kinds(step(s, 100, False, lock_age=301)[0])[:1] == ["CLEAR_PIN"]
    assert step(s, 100, False, profile=False) == ([], s)


def test_decide_does_not_mutate_input():
    s = default_state()
    snapshot = dict(s)
    step(s, 0, False)
    assert s == snapshot


# =========================
# State file and run_once (§6.1, §6.7)
# =========================

import json
import time

import openeo_wifi_watchdog as wd
from conftest import FakeRunner, ok

UP = (("nmcli", "-g", "GENERAL.STATE,GENERAL.CONNECTION"), ok("100 (connected)\ncustom-wifi\n"))
DOWN = (("nmcli", "-g", "GENERAL.STATE,GENERAL.CONNECTION"), ok("30 (disconnected)\n\n"))
PIN = (("nmcli", "-g", "802-11-wireless.bssid"), ok("AA\\:BB\\:CC\\:DD\\:EE\\:01\n"))
NOPIN = (("nmcli", "-g", "802-11-wireless.bssid"), ok("\n"))
CLEAR = ("nmcli", "connection", "modify", "custom-wifi", "802-11-wireless.bssid", "")


def is_con_up(call):
    return call[:3] == ["nmcli", "connection", "up"]


def test_load_state_corrupt_and_partial(tmp_path):
    p = tmp_path / "state.json"
    assert wd.load_state(p) == wd.default_state()
    p.write_text("{not json")
    assert wd.load_state(p) == wd.default_state()
    p.write_text("[1, 2]")
    assert wd.load_state(p) == wd.default_state()
    p.write_text(json.dumps({"roam_count": 4}))
    assert wd.load_state(p) == wd.default_state() | {"roam_count": 4}


def test_save_state_round_trip_creates_dir(tmp_path):
    p = tmp_path / "sub" / "state.json"
    wd.save_state(p, wd.default_state() | {"roam_count": 2})
    assert wd.load_state(p)["roam_count"] == 2


def test_run_once_quiet_when_nothing_to_do(tmp_path):
    assert wd.run_once(FakeRunner([UP, NOPIN]), 0, 1e9, tmp_path / "s.json", tmp_path / "lock") == []


def test_run_once_failover_logs_and_persists(tmp_path):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    run = FakeRunner([DOWN, PIN])
    wd.run_once(run, 0, 1e9, st, lock)
    lines = wd.run_once(run, 60, 1e9 + 60, st, lock)
    assert lines == ["UNPIN bssid=AA:BB:CC:DD:EE:01 reason=down down_for=60 roam_count=1",
                     "RECONNECT reason=failover rc=0"]
    assert list(CLEAR) in run.calls and any(is_con_up(c) for c in run.calls)
    assert wd.load_state(st)["unpinned_by_watchdog"] is True


def test_run_once_stops_when_setup_lock_appears(tmp_path):
    st, lock = tmp_path / "s.json", tmp_path / "lock"

    def touch_lock_on_clear(args):
        lock.touch()
        return ok("")

    run = FakeRunner([DOWN, PIN, (CLEAR, touch_lock_on_clear)])
    wd.run_once(run, 0, time.time(), st, lock)
    wd.run_once(run, 60, time.time(), st, lock)   # real wall time, so the freshly touched lock is fresh
    assert list(CLEAR) in run.calls
    assert not any(is_con_up(c) for c in run.calls)


def test_run_once_ignores_stale_lock(tmp_path):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    lock.touch()
    run = FakeRunner([DOWN, PIN])
    wd.run_once(run, 0, time.time() + 400, st, lock)
    wd.run_once(run, 60, time.time() + 460, st, lock)
    assert any(is_con_up(c) for c in run.calls)


def test_run_once_periodic_health_fail_logs_bssid_and_loss(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"up_since": 0})
    monkeypatch.setattr(wd.wp, "health_check", lambda run: wd.wp.HealthResult(False, 40, False))
    lines = wd.run_once(FakeRunner([UP, PIN]), 200, 1e9, st, lock)
    assert lines == ["HEALTH_FAIL bssid=AA:BB:CC:DD:EE:01 loss=40% failures=1"]
    assert wd.load_state(st)["health_failures"] == 1


def test_run_once_repin_passes_and_logs_repin(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0})
    sel = wd.wp.Selection("AA:BB:CC:DD:EE:02", 74, 60, 3, "pin")
    monkeypatch.setattr(wd.wp, "choose_pin", lambda run, ssid, sleep=None, exclude=None: sel)
    monkeypatch.setattr(wd.wp, "health_check", lambda run: wd.wp.HealthResult(True, 0, False))
    monkeypatch.setattr(wd.wp, "station_info", lambda run: {"rssi": -58})
    run = FakeRunner([UP, NOPIN])
    lines = wd.run_once(run, 600, 1e9, st, lock)
    assert lines == ["REPIN bssid=AA:BB:CC:DD:EE:02 signal=74 loss=0% rssi=-58"]
    assert ["nmcli", "connection", "modify", "custom-wifi", "802-11-wireless.bssid", "AA:BB:CC:DD:EE:02"] in run.calls
    assert any(is_con_up(c) for c in run.calls)    # always re-activates to apply the pin
    assert wd.load_state(st)["unpinned_by_watchdog"] is False


def test_run_once_repin_rejected_runs_clear_and_reconnect(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0})
    sel = wd.wp.Selection("AA:BB:CC:DD:EE:02", 74, 60, 3, "pin")
    monkeypatch.setattr(wd.wp, "choose_pin", lambda run, ssid, sleep=None, exclude=None: sel)
    monkeypatch.setattr(wd.wp, "health_check", lambda run: wd.wp.HealthResult(False, 100, False))
    run = FakeRunner([UP, NOPIN])
    lines = wd.run_once(run, 600, 1e9, st, lock)
    assert lines == ["PIN_REJECTED bssid=AA:BB:CC:DD:EE:02 signal=74 loss=100% source=repin",
                     "RECONNECT reason=rejected rc=0"]
    assert list(CLEAR) in run.calls
    assert wd.load_state(st)["repin_rejections"] == 1


def test_run_once_repin_no_node_stays_unpinned(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0})
    monkeypatch.setattr(wd.wp, "choose_pin", lambda run, ssid, sleep=None, exclude=None: wd.wp.Selection(reason="single"))
    run = FakeRunner([UP, NOPIN])
    assert wd.run_once(run, 600, 1e9, st, lock) == []
    assert not any(is_con_up(c) for c in run.calls)
    assert wd.load_state(st)["last_repin_attempt"] == 600


def test_run_once_exception_is_logged_not_raised(tmp_path):
    def broken(args):
        raise RuntimeError("nmcli exploded")
    lines = wd.run_once(broken, 0, 1e9, tmp_path / "s.json", tmp_path / "lock")
    assert len(lines) == 1 and lines[0].startswith("ERROR")


def test_run_once_uses_injected_clock(tmp_path, monkeypatch):
    def no_wall_clock():
        raise AssertionError("wall clock used")
    monkeypatch.setattr(wd.time, "time", no_wall_clock)
    monkeypatch.setattr(wd.time, "monotonic", no_wall_clock)
    wd.run_once(FakeRunner([UP, PIN]), 0, 1e9, tmp_path / "s.json", tmp_path / "lock")


def test_run_once_repin_failed_activation_is_a_rejection(tmp_path, monkeypatch):
    # A node that refuses the association must not stay pinned, even though the
    # health check would be skipped (no gateway) and count as a pass
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0})
    sel = wd.wp.Selection("AA:BB:CC:DD:EE:02", 74, 60, 3, "pin")
    monkeypatch.setattr(wd.wp, "choose_pin", lambda run, ssid, sleep=None, exclude=None: sel)
    monkeypatch.setattr(wd.wp, "health_check", lambda run: wd.wp.HealthResult(True, None, True))
    from conftest import fail
    run = FakeRunner([UP, NOPIN, (("nmcli", "connection", "up"), [fail(4), ok("")])])
    lines = wd.run_once(run, 600, 1e9, st, lock)
    assert lines[0] == "PIN_REJECTED bssid=AA:BB:CC:DD:EE:02 signal=74 source=repin"
    assert list(CLEAR) in run.calls


UUID = ("nmcli", "-g", "connection.uuid")


def test_run_once_resets_state_when_profile_is_recreated(tmp_path):
    # A new portal setup deletes and re-adds custom-wifi. Old watchdog state must not carry
    # over: here it would otherwise re-pin a network that setup left unpinned
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0,
                                            "health_failures": 1, "profile_uuid": "old-uuid"})
    run = FakeRunner([UP, NOPIN, (UUID, ok("new-uuid\n"))])
    assert wd.run_once(run, 600, 1e9, st, lock) == []
    state = wd.load_state(st)
    assert state == wd.default_state() | {"profile_uuid": "new-uuid", "up_since": 600,
                                          "status_level": "ok", "status_code": "ok", "status_since": 1e9}


def test_run_once_keeps_state_for_same_profile(tmp_path):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"roam_count": 3, "profile_uuid": "same"})
    wd.run_once(FakeRunner([UP, NOPIN, (UUID, ok("same\n"))]), 0, 1e9, st, lock)
    assert wd.load_state(st)["roam_count"] == 3


def test_run_once_sees_drop_from_iw_while_nm_still_up(tmp_path):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    run = FakeRunner([UP, PIN, (("iw", "dev", "wlan0", "link"), ok("Not connected.\n"))])
    wd.run_once(run, 0, 1e9, st, lock)
    lines = wd.run_once(run, 60, 1e9 + 60, st, lock)
    assert lines[0] == "UNPIN bssid=AA:BB:CC:DD:EE:01 reason=down down_for=60 roam_count=1"


# =========================
# Journal drops (§4.2)
# =========================

from wifi_pinning import WpaEvent
from test_wifi_pinning import jline


def test_record_events_grace_lock_prune_dedupe():
    s = wd.default_state() | {"last_reconnect": 1000, "drops": [[10, P]]}
    ev = [WpaEvent("drop", 1010, P), WpaEvent("drop", 1031, P), WpaEvent("auth_fail", 1040)]
    s2 = wd.record_events(s, ev, 4000, lock_age=None)
    assert s2["drops"] == [[1031, P]]               # 1010 inside 30 s grace; 10 pruned (> 1 h old)
    assert s2["last_auth_fail"] == 1040
    assert s["drops"] == [[10, P]]                   # input not mutated
    assert wd.record_events(s2, ev, 4000, lock_age=None)["drops"] == [[1031, P]]   # re-read: no duplicates
    assert wd.record_events(wd.default_state(), ev, 4000, lock_age=10)["drops"] == []  # setup lock fresh


def test_record_events_normalises_bssid_and_keeps_latest_auth_fail():
    s = wd.default_state() | {"last_auth_fail": 2000}
    s2 = wd.record_events(s, [WpaEvent("drop", 50, P.lower()), WpaEvent("auth_fail", 1500)], 100, lock_age=None)
    assert s2["drops"] == [[50, P]] and s2["last_auth_fail"] == 2000


def test_run_once_saves_journal_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr(wd.wp, "boot_id", lambda: "b1")
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    disc = f"wlan0: CTRL-EVENT-DISCONNECTED bssid={P.lower()} reason=3"
    run = FakeRunner([UP, PIN, (("journalctl",), ok(jline(5, disc, cursor="k9")))])
    wd.run_once(run, 100, 1e9, st, lock)
    saved = wd.load_state(st)
    assert saved["journal_cursor"] == "k9" and saved["drops"] == [[5.0, P]]


# =========================
# Flap rule 1a, exclusions and cool-off (§4.2, §4.3)
# =========================

def flap_step(state, now, drop_times, up=True, pinned=P):
    state = state | {"drops": [[t, P] for t in drop_times]}
    return step(state, now, up, pinned=pinned)


def test_two_drops_no_action():
    a, s = flap_step(default_state(), 150, [0, 100])
    assert a == [] and len(s["drops"]) == 2


def test_three_drops_unpin_flapping():
    a, s = flap_step(default_state(), 300, [0, 100, 200])
    assert kinds(a) == ["CLEAR_PIN", "LOG", "CON_UP"] and a[2].fields["reason"] == "flapping"
    assert a[1].fields == {"event": "UNPIN", "bssid": P, "reason": "flapping", "drops": 3,
                           "window": 600, "roam_count": 1}
    assert s["excluded_bssids"] == [P] and s["drops"] == [] and s["last_unpin_reason"] == "flapping"
    assert s["last_flap"] == {"bssid": P, "drops": 3, "span": 200}
    assert s["last_unpin_at"] == 300


def test_drops_outside_window_dont_count():
    a, _ = flap_step(default_state(), 701, [0, 100, 200])
    assert a == []


def test_drops_for_other_bssid_dont_count():
    other = "AA:BB:CC:DD:EE:02"
    s = default_state() | {"drops": [[0, other], [100, other], [200, other]]}
    a, _ = step(s, 300, True)
    assert a == []


def test_flap_rule_needs_pin():
    a, _ = flap_step(default_state(), 300, [0, 100, 200], pinned="")
    assert "UNPIN" not in events(a)


def test_flap_rule_matches_pin_case_insensitively():
    a, _ = flap_step(default_state(), 300, [0, 100, 200], pinned=P.lower())
    assert events(a) == ["UNPIN"] and a[1].fields["reason"] == "flapping"


def test_replay_2026_10_30_unpins_at_15_30_57():
    # t=0 is 15:27:28 (first drop). Drops 15:27:28, 15:29:28, 15:30:13; runs at :57 past each minute.
    # Journal BSSID is lower case; the pin is the nmcli upper-case form.
    drops = [0, 120, 165]
    runs = [29, 89, 149, 209]
    s = default_state()
    for run_at in runs:
        new = [WpaEvent("drop", t, "02:ec:da:fd:20:a6") for t in drops if t <= run_at]
        s = wd.record_events(s, new, run_at, lock_age=None)
        a, s = step(s, run_at, True, pinned="02:EC:DA:FD:20:A6")
        if run_at < 209:
            assert "UNPIN" not in events(a)
    assert events(a) == ["UNPIN"] and a[1].fields["reason"] == "flapping"
    assert s["excluded_bssids"] == ["02:EC:DA:FD:20:A6"]


def test_repin_does_not_count_drops_from_before_the_pin():
    B = "AA:BB:CC:DD:EE:02"
    s = default_state() | {"unpinned_by_watchdog": True, "drops": [[3300, B], [3400, B], [3500, B]]}
    _, s = after_health(s, 3600, "repin", True, bssid=B)
    assert s["pinned_at"] == 3600
    a, s = step(s, 3660, True, pinned=B)
    assert "UNPIN" not in events(a)
    s = s | {"drops": s["drops"] + [[3700, B], [3800, B], [3900, B]]}
    a, s = step(s, 3960, True, pinned=B)
    assert events(a) == ["UNPIN"] and a[1].fields["reason"] == "flapping" and a[1].fields["drops"] == 3
    assert s["pinned_at"] is None


def test_every_unpin_excludes():
    s = default_state()
    _, s = step(s, 0, False)
    a, s = step(s, 60, False)
    assert a[1].fields["reason"] == "down" and s["excluded_bssids"] == [P]
    assert s["last_unpin_reason"] == "down" and s["last_unpin_at"] == 60

    other = "AA:BB:CC:DD:EE:02"
    s = default_state() | {"health_failures": 1, "excluded_bssids": [P]}
    a, s = after_health(s, 100, "periodic", False, bssid=other.lower())
    assert a[2].fields["reason"] == "unhealthy" and s["excluded_bssids"] == [P, other]
    _, s = after_health(s | {"health_failures": 1}, 200, "periodic", False, bssid=P)
    assert s["excluded_bssids"] == [P, other]      # no duplicates


def test_repin_rejection_excludes():
    B = "AA:BB:CC:DD:EE:02"
    s = default_state() | {"unpinned_by_watchdog": True}
    _, s = after_health(s, 3600, "repin", False, bssid=B)
    assert B in s["excluded_bssids"]


def test_flap_cooloff_holds_repin():
    s = default_state() | {"unpinned_by_watchdog": True, "last_unpin_reason": "flapping",
                           "last_unpin_at": 0, "up_since": 0}
    assert step(s, 3599, True, pinned="")[0] == []
    assert kinds(step(s, 3600, True, pinned="")[0]) == ["REPIN_SCAN"]


def test_down_unpin_has_no_cooloff():
    s = default_state() | {"unpinned_by_watchdog": True, "last_unpin_reason": "down",
                           "last_unpin_at": 0, "up_since": 0}
    assert kinds(step(s, 600, True, pinned="")[0]) == ["REPIN_SCAN"]


def test_run_once_repin_passes_exclusions(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0,
                                            "excluded_bssids": [P]})
    seen = {}

    def fake_choose(run, ssid, sleep=None, exclude=None):
        seen["exclude"] = exclude
        return wd.wp.Selection(reason="excluded")

    monkeypatch.setattr(wd.wp, "choose_pin", fake_choose)
    wd.run_once(FakeRunner([UP, NOPIN]), 600, 1e9, st, lock)
    assert seen["exclude"] == frozenset({P})


def test_run_once_all_excluded_no_rejection(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0,
                                            "excluded_bssids": [P]})
    monkeypatch.setattr(wd.wp, "choose_pin",
                        lambda run, ssid, sleep=None, exclude=None: wd.wp.Selection(samples=3, reason="excluded"))
    run = FakeRunner([UP, NOPIN])
    assert wd.run_once(run, 600, 1e9, st, lock) == []
    assert not any(is_con_up(c) for c in run.calls)
    assert wd.load_state(st)["repin_rejections"] == 0


def test_run_once_rejected_repin_excludes_selection(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"unpinned_by_watchdog": True, "up_since": 0})
    sel = wd.wp.Selection("AA:BB:CC:DD:EE:02", 74, 60, 3, "pin")
    monkeypatch.setattr(wd.wp, "choose_pin", lambda run, ssid, sleep=None, exclude=None: sel)
    monkeypatch.setattr(wd.wp, "health_check", lambda run: wd.wp.HealthResult(False, 100, False))
    wd.run_once(FakeRunner([UP, NOPIN]), 600, 1e9, st, lock)
    assert wd.load_state(st)["excluded_bssids"] == ["AA:BB:CC:DD:EE:02"]


def test_run_once_unhealthy_unpin_excludes_pin(tmp_path, monkeypatch):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"up_since": 0, "health_failures": 1})
    monkeypatch.setattr(wd.wp, "health_check", lambda run: wd.wp.HealthResult(False, 40, False))
    lines = wd.run_once(FakeRunner([UP, PIN]), 200, 1e9, st, lock)
    assert "UNPIN bssid=AA:BB:CC:DD:EE:01 reason=unhealthy roam_count=1" in lines
    assert wd.load_state(st)["excluded_bssids"] == [P]


def test_run_once_flapping_logs_unpin_and_reconnect(tmp_path):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"drops": [[0, P], [100, P], [200, P]]})
    lines = wd.run_once(FakeRunner([UP, PIN]), 300, 1e9, st, lock)
    assert lines == ["UNPIN bssid=AA:BB:CC:DD:EE:01 reason=flapping drops=3 window=600 roam_count=1",
                     "RECONNECT reason=flapping rc=0"]


def test_profile_reset_clears_exclusions(tmp_path):
    st, lock = tmp_path / "s.json", tmp_path / "lock"
    wd.save_state(st, wd.default_state() | {"excluded_bssids": [P], "profile_uuid": "old"})
    wd.run_once(FakeRunner([UP, NOPIN, (UUID, ok("new\n"))]), 0, 1e9, st, lock)
    assert wd.load_state(st)["excluded_bssids"] == []


# =========================
# Health status (§4.4)
# =========================

from wifi_pinning import LinkState

STATUS_KEYS = {"level", "code", "message", "since", "updated", "pinned_bssid", "current_bssid",
               "rssi", "drops_1h", "excluded_bssids", "last_event", "last_event_at"}


def cl(state=None, now=1000, now_wall=1_700_000_000, up=True, rssi=-60, pinned=P,
       profile_exists=True, lock_age=None):
    return wd.classify(state or default_state(), now, now_wall,
                       profile_exists=profile_exists, lock_age=lock_age,
                       link=LinkState(up, P if up else None, rssi), pinned=pinned, ssid="Home")


def level_code(status):
    return status["level"], status["code"]


def test_classify_ok():
    status, _ = cl()
    assert level_code(status) == ("ok", "ok") and status["message"] == "Wi-Fi OK"
    assert status["pinned_bssid"] == P and status["current_bssid"] == P and status["rssi"] == -60


def test_classify_auth_failed():
    status, _ = cl(default_state() | {"last_auth_fail": 1000 - 599}, up=False)
    assert level_code(status) == ("problem", "auth_failed") and "password" in status["message"]
    assert cl(default_state() | {"last_auth_fail": 1000 - 601}, up=False)[0]["code"] != "auth_failed"


def test_classify_auth_fail_ignored_while_connected():
    # Handshake timeouts while an AP flaps log WRONG_KEY with a correct password
    st = default_state() | {"last_auth_fail": 990, "last_unpin_reason": "flapping", "last_unpin_at": 900,
                            "unpinned_by_watchdog": True, "last_flap": {"bssid": P, "drops": 3, "span": 165}}
    assert level_code(cl(st, pinned="")[0]) == ("problem", "flapping")
    assert level_code(cl(default_state() | {"last_auth_fail": 990})[0]) == ("ok", "ok")


def test_classify_offline():
    status, _ = cl(default_state() | {"down_since": 940}, up=False)
    assert level_code(status) == ("problem", "offline") and "since" in status["message"]
    assert status["current_bssid"] is None
    assert cl(default_state() | {"down_since": 941}, up=False)[0]["code"] != "offline"


def test_classify_offline_time_is_wall_clock_of_drop():
    now_wall = 1_700_000_000
    status, _ = cl(default_state() | {"down_since": 400}, up=False, now_wall=now_wall)
    expected = time.strftime("%H:%M", time.localtime(now_wall - 600))
    assert expected in status["message"]


def test_classify_flapping_and_hold():
    st = default_state() | {"last_unpin_reason": "flapping", "last_unpin_at": 0, "unpinned_by_watchdog": True,
                            "last_flap": {"bssid": P, "drops": 3, "span": 165}}
    status, _ = cl(st, now=3599, pinned="")
    assert (status["level"], status["code"]) == ("problem", "flapping")
    assert P in status["message"] and "3 drops in 3 min" in status["message"] and "Home" in status["message"]
    assert cl(st, now=3600, pinned="")[0]["code"] == "fallback"            # hold expired, still unpinned


def test_classify_unstable_network():
    st = default_state() | {"drops": [[500, P], [700, "AA:BB:CC:DD:EE:02"], [900, P]]}
    status, _ = cl(st, pinned="")
    assert level_code(status) == ("problem", "unstable_network")
    # Pinned, the same drops are rule 1a's business, not "every access point"
    assert cl(st)[0]["code"] == "drops"


def test_classify_drops_warning():
    status, _ = cl(default_state() | {"drops": [[100, P], [900, P]]})
    assert level_code(status) == ("warning", "drops") and "2 times" in status["message"]
    assert status["drops_1h"] == 2


def test_classify_drops_1h_counts_last_hour_only():
    status, _ = cl(default_state() | {"drops": [[5000 - 3600, P], [5000 - 3601, P]]}, now=5000)
    assert status["drops_1h"] == 1 and status["code"] == "ok"


def test_classify_fallback_names_bssid():
    st = default_state() | {"unpinned_by_watchdog": True, "last_unpin_reason": "down",
                            "last_unpin_at": 900, "excluded_bssids": [P]}
    status, _ = cl(st, pinned="")
    assert level_code(status) == ("warning", "fallback") and P in status["message"]
    assert status["pinned_bssid"] is None and status["excluded_bssids"] == [P]


def test_classify_weak_signal_needs_three_runs():
    s = default_state()
    for i in range(2):
        status, s = cl(s, rssi=-75); assert status["code"] == "ok"
    status, s = cl(s, rssi=-75); assert status["code"] == "weak_signal"
    assert status["level"] == "warning" and "-75 dBm" in status["message"]
    status, s = cl(s, rssi=-74); assert status["code"] == "ok" and s["weak_runs"] == 0


def test_classify_unknown_when_no_profile_or_lock():
    st = default_state() | {"weak_runs": 2, "status_level": "ok", "status_code": "ok", "status_since": 5,
                            "last_auth_fail": 1000}
    for status, s in (cl(st, profile_exists=False, rssi=-80), cl(st, lock_age=10, rssi=-80)):
        assert (status["level"], status["code"], status["message"]) == ("unknown", "", "")
        assert s["weak_runs"] == 2 and s["status_since"] == 5
    assert cl(st, lock_age=wd.wp.LOCK_STALE, up=False)[0]["level"] == "problem"   # a stale lock is ignored


def test_classify_precedence():
    st = default_state() | {"last_auth_fail": 990, "down_since": 900, "drops": [[100, P], [200, P]]}
    assert cl(st, up=False)[0]["code"] == "auth_failed"
    st = default_state() | {"down_since": 900, "unpinned_by_watchdog": True, "excluded_bssids": [P]}
    assert cl(st, up=False, pinned="")[0]["code"] == "offline"


def test_classify_since_stable():
    _, s = cl(now=1000); assert s["status_since"] == 1_700_000_000
    status, s = cl(s, now=1060, now_wall=1_700_000_060)   # same level/code
    assert status["since"] == 1_700_000_000 and status["updated"] == 1_700_000_060
    status, s = cl(s | {"down_since": 1000}, now=1120, now_wall=1_700_000_120, up=False)
    assert status["code"] == "offline" and status["since"] == 1_700_000_120


def test_classify_does_not_mutate_input():
    st = default_state()
    before = json.dumps(st)
    cl(st, rssi=-80)
    assert json.dumps(st) == before


def test_save_status_modes(tmp_path):
    p = tmp_path / "d" / "status.json"; wd.save_status(p, {"level": "ok"})
    assert oct(p.stat().st_mode & 0o777) == "0o644" and oct(p.parent.stat().st_mode & 0o777) == "0o755"
    assert json.loads(p.read_text()) == {"level": "ok"}


def test_run_once_writes_status_and_last_event(tmp_path):
    st, lock, sp = tmp_path / "s.json", tmp_path / "lock", tmp_path / "out" / "status.json"
    run = FakeRunner([DOWN, PIN])
    wd.run_once(run, 0, 1e9, st, lock, status_path=sp)
    wd.run_once(run, 60, 1e9 + 60, st, lock, status_path=sp)
    status = json.loads(sp.read_text())
    assert level_code(status) in (("problem", "offline"), ("warning", "fallback"))
    assert status["last_event"].startswith("UNPIN") and status["last_event_at"] == 1e9 + 60
    assert status["updated"] == 1e9 + 60 and set(status) == STATUS_KEYS
    assert wd.load_state(st)["last_event"].startswith("UNPIN")


def test_run_once_status_defaults_to_status_file(tmp_path):
    wd.run_once(FakeRunner([UP, NOPIN]), 0, 1e9, tmp_path / "s.json", tmp_path / "lock")
    assert level_code(json.loads((tmp_path / "status.json").read_text())) == ("ok", "ok")


def test_run_once_error_leaves_status_untouched(tmp_path):
    sp = tmp_path / "status.json"
    sp.write_text(json.dumps({"updated": 1}))
    def broken(args):
        raise RuntimeError("nmcli exploded")
    wd.run_once(broken, 0, 1e9, tmp_path / "s.json", tmp_path / "lock", status_path=sp)
    assert json.loads(sp.read_text()) == {"updated": 1}


def test_status_has_no_secret_keys():
    st = default_state() | {"unpinned_by_watchdog": True, "excluded_bssids": [P], "last_event": "UNPIN x"}
    for status, _ in (cl(), cl(st, pinned=""), cl(profile_exists=False)):
        assert set(status) == STATUS_KEYS


def test_record_events_ignores_drops_from_a_finished_setup():
    # Setup ended 100 s ago (now 4000 -> setup end at 3900). Its reconnects, read only now
    # because the lock had already gone, are not drops; a later one is.
    ev = [WpaEvent("drop", 3870, P), WpaEvent("drop", 3899, P), WpaEvent("drop", 3925, P),
          WpaEvent("drop", 3960, P)]
    s = wd.record_events(wd.default_state(), ev, 4000, lock_age=None, setup_done_age=100)
    assert s["drops"] == [[3960, P]]            # 3925 is inside the 30 s grace after setup


def test_run_once_does_not_count_setup_reconnects_after_lock_removed(tmp_path, monkeypatch):
    """Device 2026-10-31: setup at 22:34, lock removed, first watchdog run at 22:36 counted
    the setup's two reconnects and showed 'Wi-Fi dropped 2 times in the last hour'."""
    import os
    monkeypatch.setattr(wd.wp, "boot_id", lambda: "b1")
    st, lock = tmp_path / "s.json", tmp_path / "openeo-wifi-setup.lock"
    done = tmp_path / "openeo-wifi-setup.done"
    done.touch()
    now_wall = os.stat(done).st_mtime + 90          # setup finished 90 s ago
    events = [wd.wp.WpaEvent("drop", 1000 - 120, P), wd.wp.WpaEvent("drop", 1000 - 95, P)]
    monkeypatch.setattr(wd.wp, "read_wpa_events", lambda run, cursor, boot: (events, "c1"))
    wd.run_once(FakeRunner([UP, PIN]), 1000, now_wall, st, lock)
    assert wd.load_state(st)["drops"] == []
