#!/usr/bin/env python3
"""Tests for lib/wifi_status helpers and the wifi_health plugin's never-raise guarantee."""

import os, sys
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import wifi_status


def test_read_status_missing_is_unknown(tmp_path):
    assert wifi_status.read_status(tmp_path / "nope.json", 1000)["level"] == "unknown"


def test_read_status_rejects_garbage(tmp_path):
    p = tmp_path / "s.json"
    for body in ["{trunc", "[1]", '{"level": "purple", "updated": 1000}', '{"level": "ok", "updated": "x"}',
                 '{"level": "ok", "updated": 699}', '{"level": "ok", "updated": 1301}',
                 '{"level": "ok", "updated": NaN}']:
        p.write_text(body)
        assert wifi_status.read_status(p, 1000)["level"] == "unknown"
    p.write_text('{"level": "ok", "code": "ok", "message": "Wi-Fi OK", "updated": 700}')
    assert wifi_status.read_status(p, 1000)["level"] == "ok"


def test_state_fields_none_bssid_is_empty_string():
    f = wifi_status.state_fields({"level": "ok", "code": "ok", "message": "m", "since": None,
                                  "pinned_bssid": None, "current_bssid": None, "rssi": None})
    assert set(f) == {"eo_wifi_health", "eo_wifi_health_code", "eo_wifi_health_message", "eo_wifi_health_since",
                      "eo_wifi_pinned_bssid", "eo_wifi_current_bssid", "eo_wifi_rssi", "eo_wifi_drops_1h"}
    assert f["eo_wifi_pinned_bssid"] == "" and f["eo_wifi_current_bssid"] == ""
    assert f["eo_wifi_drops_1h"] == 0
    g = wifi_status.state_fields({"level": "warning", "code": "c", "message": "m", "since": 5,
                                  "pinned_bssid": "AA:BB", "current_bssid": "CC:DD", "rssi": -60, "drops_1h": 2})
    assert g["eo_wifi_pinned_bssid"] == "AA:BB" and g["eo_wifi_rssi"] == -60 and g["eo_wifi_drops_1h"] == 2
    assert g["eo_wifi_health"] == "warning" and g["eo_wifi_health_since"] == 5


def test_log_lines_change_only():
    a = {"level": "ok", "code": "ok", "message": "Wi-Fi OK", "last_event": None, "last_event_at": None}
    b = a | {"level": "problem", "code": "flapping", "message": "m",
             "last_event": "UNPIN bssid=X reason=flapping", "last_event_at": 5}
    assert wifi_status.log_lines(None, a) == ["wifi: ok ok - Wi-Fi OK"]
    assert wifi_status.log_lines(a, a) == []
    assert wifi_status.log_lines(a, b) == ["wifi: problem flapping - m", "wifi: UNPIN bssid=X reason=flapping"]
    assert wifi_status.log_lines(b, b | {"last_event_at": 9}) == ["wifi: UNPIN bssid=X reason=flapping"]
    assert wifi_status.log_lines(None, b | {"level": "unknown"}) == []


def test_log_lines_switch_to_unknown_is_silent():
    a = {"level": "ok", "code": "ok", "message": "Wi-Fi OK", "last_event": "REPIN", "last_event_at": 5}
    assert wifi_status.log_lines(a, {"level": "unknown", "code": "", "message": ""}) == []


def poll_sequence(statuses):
    """Drive the plugin's poll() through a list of read_status results; returns the lines logged."""
    fake = SimpleNamespace(stateDict={}, configDB=mock.Mock())
    with mock.patch.dict(sys.modules, {"globalState": fake}):
        sys.modules.pop("lib.wifi_health", None)
        from lib import wifi_health
        plugin = wifi_health.wifi_healthClassPlugin.__new__(wifi_health.wifi_healthClassPlugin)
        plugin.prev = None
        # The lib package keeps the module from an earlier import; point it at this fake
        with mock.patch.object(wifi_health, "globalState", fake), \
                mock.patch.object(wifi_health.wifi_status, "read_status", side_effect=statuses):
            for _ in statuses:
                plugin.poll()
        sys.modules.pop("lib.wifi_health", None)
    return [c.args[0] for c in fake.configDB.logwrite.call_args_list]


def test_plugin_unknown_gap_does_not_replay_or_log():
    unknown = {"level": "unknown", "code": "", "message": ""}
    ok = {"level": "ok", "code": "ok", "message": "Wi-Fi OK", "last_event": "REPIN", "last_event_at": 5}
    first = ["wifi: ok ok - Wi-Fi OK"]
    # ok -> unknown -> ok with the same event: nothing after the first poll
    assert poll_sequence([ok, unknown, ok]) == first
    # unknown -> problem logs the level line, and no event replay
    problem = ok | {"level": "problem", "code": "offline", "message": "m"}
    assert poll_sequence([ok, unknown, problem]) == first + ["wifi: problem offline - m"]
    # An unknown first poll leaves the next known poll as the first one: no replay
    assert poll_sequence([unknown, ok]) == first


def test_plugin_poll_never_raises():
    fake = SimpleNamespace(stateDict={}, configDB=mock.Mock())
    with mock.patch.dict(sys.modules, {"globalState": fake}):
        sys.modules.pop("lib.wifi_health", None)
        from lib import wifi_health
        plugin = wifi_health.wifi_healthClassPlugin.__new__(wifi_health.wifi_healthClassPlugin)
        plugin.prev = None
        with mock.patch.object(wifi_health.wifi_status, "read_status", side_effect=RuntimeError("boom")):
            assert plugin.poll() == 0
        fake.configDB.logwrite.side_effect = OSError("db")
        with mock.patch.object(wifi_health.wifi_status, "read_status",
                               return_value={"level": "ok", "code": "ok", "message": "m"}):
            assert plugin.poll() == 0
        sys.modules.pop("lib.wifi_health", None)
