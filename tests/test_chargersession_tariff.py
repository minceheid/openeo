"""Session costing with the optional live Home Assistant tariff rate."""
import datetime
import json
import logging
import os
import sqlite3
import sys
import types
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# globalState builds the live config under /home/pi on import; the plugin only needs the name.
sys.modules.setdefault("globalState", mock.MagicMock())

from lib import chargersession as cs  # noqa: E402

TARIFF = [{"start": "0000", "end": "0029", "cost": 0.27048},
          {"start": "0030", "end": "0529", "cost": 0.04998},
          {"start": "0530", "end": "2359", "cost": 0.27048}]


class Clock:
    """Drives datetime.datetime.now() and time.time() in the plugin module."""

    def __init__(self, dt):
        self.dt = dt

    def ts(self):
        return self.dt.timestamp()


@pytest.fixture
def clock():
    c = Clock(datetime.datetime(2026, 11, 22, 10, 0, 0))

    class FakeDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return c.dt if tz is None else c.dt.astimezone(tz)

    with mock.patch.object(cs, "datetime", types.SimpleNamespace(datetime=FakeDateTime)), \
            mock.patch.object(cs, "time", types.SimpleNamespace(time=c.ts)):
        yield c


@pytest.fixture
def state():
    d = {"eo_charger_state_id": 11, "eo_live_voltage": 240, "eo_current_vehicle": 10,
         "eo_session_current_tariff": 0.0,
         "eo_ha_rate": None, "eo_ha_online": True, "eo_mqtt_connected": True}
    return d


@pytest.fixture
def config_db():
    db = mock.Mock()
    db.get.return_value = "True"
    return db


@pytest.fixture
def env(tmp_path, state, config_db, clock):
    with mock.patch.object(cs.chargersessionClassPlugin, "SESSION_DB_FILE", str(tmp_path / "session.db")), \
            mock.patch.object(cs.globalState, "stateDict", state), \
            mock.patch.object(cs.globalState, "configDB", config_db):
        yield tmp_path


def make_plugin(enabled, stale_minutes=15):
    p = cs.chargersessionClassPlugin({"enabled": True, "tariff": json.dumps(TARIFF),
                                      "ha_rate_enabled": enabled,
                                      "ha_rate_stale_minutes": stale_minutes})
    p.lastloop = cs.datetime.datetime.now()
    return p


def fresh_rate(clock, value):
    return {"value": value, "received_at": clock.ts()}


def run_polls(plugin, clock, n, step=15, before_poll=None):
    for _ in range(n):
        clock.dt += datetime.timedelta(seconds=step)
        if before_poll:
            before_poll()
        plugin.poll()


def rows(env):
    conn = sqlite3.connect(str(env / "session.db"))
    try:
        return conn.execute("SELECT first_timestamp, day_timestamp, joules, cost, cost_by_tariff, fallback_joules "
                            "FROM session_v6 ORDER BY day_timestamp").fetchall()
    finally:
        conn.close()


def logwrites(config_db, text):
    return [c.args[0] for c in config_db.logwrite.call_args_list if text in c.args[0]]


def warnings(caplog, text):
    return [r for r in caplog.records if r.levelno == logging.WARNING and text in r.getMessage()]


def reference_band_cost(timestamps, voltage, amps):
    """The unmodified band algorithm from chargersession.poll(), copied verbatim in substance.

    Returns a list of (cost, joules_by_tariff) after each poll.
    """
    session_tariff = [{"start": x["start"], "end": x["end"], "cost": x["cost"], "joules": 0} for x in TARIFF]
    results = []
    last = timestamps[0]
    for ts in timestamps[1:]:
        current_hhmm = f"{datetime.datetime.fromtimestamp(ts):%H%M}"
        joulesThisLoop = int(voltage * amps * (ts - last))
        for x in session_tariff:
            if x["start"] <= current_hhmm <= x["end"]:
                x["joules"] += joulesThisLoop
                break
        cost = 0
        joules_by_tariff = {}
        for x in session_tariff:
            cost += x["cost"] * (x["joules"] / 3600000)
            joules_by_tariff[x["cost"]] = joules_by_tariff.get(x["cost"], 0) + x["joules"]
        results.append((round(cost, 2), json.dumps(joules_by_tariff)))
        last = ts
    return results


def test_disabled_identical(env, clock, state):
    clock.dt = datetime.datetime(2026, 11, 22, 0, 25, 0)
    plugin = make_plugin(False)
    timestamps = [clock.ts()]
    results = []

    def record():
        timestamps.append(clock.ts())

    for _ in range(50):
        clock.dt += datetime.timedelta(seconds=15)
        record()
        plugin.poll()
        results.append(state["eo_session_cost"])

    expected = reference_band_cost(timestamps, 240, 10)
    assert results == [cost for cost, _ in expected]
    # The last write happened at the last minute boundary crossed (00:37:00).
    last_write = max(i for i, ts in enumerate(timestamps[1:])
                     if datetime.datetime.fromtimestamp(ts).second == 0)
    (row,) = rows(env)
    assert row[4] == expected[last_write][1]
    assert row[3] == expected[last_write][0]
    assert row[5] == 0
    assert "0.04998" in row[4] and "0.27048" in row[4]


def test_disabled_does_not_select_rate(env, clock, state):
    plugin = make_plugin(False)
    state["eo_ha_rate"] = fresh_rate(clock, 0.07)
    with mock.patch.object(cs, "select_rate") as sel, mock.patch.object(cs, "transition_message") as tm:
        run_polls(plugin, clock, 5)
    sel.assert_not_called()
    tm.assert_not_called()
    assert state["eo_session_current_tariff"] == 0.27048


def test_enabled_uses_ha_rate(env, clock, state):
    plugin = make_plugin(True)
    state["eo_ha_rate"] = fresh_rate(clock, 0.07)
    run_polls(plugin, clock, 10, step=60)
    assert state["eo_session_current_tariff"] == 0.07
    assert state["eo_tariff_rate_source"] == "ha"
    assert state["eo_session_cost"] == round(10 * 144000 * 0.07 / 3600000, 2) == 0.03
    assert json.loads(rows(env)[-1][4]) == {"0.07": 10 * 144000}


def test_enabled_fallback_logged_once(env, clock, state, config_db, caplog):
    plugin = make_plugin(True)
    state["eo_ha_rate"] = {"value": 0.07, "received_at": clock.ts() - 3600}
    with caplog.at_level(logging.INFO):
        run_polls(plugin, clock, 10, step=120)
    assert len(warnings(caplog, "falling back")) == 1
    assert len(logwrites(config_db, "falling back")) == 1
    assert state["eo_tariff_rate_source"] == "schedule"
    assert state["eo_session_current_tariff"] == 0.27048
    sessions = plugin.get_sessions()
    assert sessions and sessions[-1]["fallback_joules"] > 0
    assert sessions[-1]["fallback_joules"] == sessions[-1]["joules"]


def test_out_of_range_warned_once(env, clock, state, config_db, caplog):
    plugin = make_plugin(True)
    state["eo_ha_rate"] = fresh_rate(clock, 28.96)
    with caplog.at_level(logging.INFO):
        run_polls(plugin, clock, 5)
    assert len(warnings(caplog, "outside the expected range -1..5")) == 1
    assert len(logwrites(config_db, "outside the expected range -1..5")) == 1
    assert state["eo_session_current_tariff"] == 28.96
    assert state["eo_session_cost"] == round(5 * 36000 * 28.96 / 3600000, 2)


@pytest.mark.parametrize("rate", [-1, 5, -0.2])
def test_in_range_not_warned(env, clock, state, caplog, rate):
    plugin = make_plugin(True)
    state["eo_ha_rate"] = fresh_rate(clock, rate)
    with caplog.at_level(logging.INFO):
        run_polls(plugin, clock, 3)
    assert not warnings(caplog, "outside the expected range")


def test_enable_takes_effect_next_session(env, clock, state):
    plugin = make_plugin(False)
    state["eo_ha_rate"] = fresh_rate(clock, 0.07)
    run_polls(plugin, clock, 2)
    plugin.pluginConfig["ha_rate_enabled"] = True
    run_polls(plugin, clock, 2, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    assert state["eo_session_current_tariff"] == 0.27048
    assert state.get("eo_tariff_rate_source") != "ha"

    state["eo_charger_state_id"] = 1   # unplugged: new session
    run_polls(plugin, clock, 1)
    state["eo_charger_state_id"] = 11
    run_polls(plugin, clock, 1, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    assert state["eo_session_current_tariff"] == 0.07
    assert state["eo_tariff_rate_source"] == "ha"

    plugin.pluginConfig["ha_rate_enabled"] = False
    run_polls(plugin, clock, 1, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    assert state["eo_tariff_rate_source"] == "ha"


def test_v5_migrates_to_v6(env):
    conn = sqlite3.connect(str(env / "session.db"))
    conn.execute("""CREATE TABLE session_v5 (
        first_timestamp INTEGER NOT NULL, day_timestamp INTEGER NOT NULL, last_timestamp INTEGER,
        joules INTEGER NOT NULL, seconds_charged INTEGER NOT NULL, cost REAL NOT NULL,
        cost_by_tariff text not null, PRIMARY KEY (first_timestamp, day_timestamp))""")
    conn.execute("INSERT INTO session_v5 VALUES (100, 50, 200, 7200000, 600, 1.5, '{\"0.27048\": 7200000}')")
    conn.commit()
    conn.close()

    make_plugin(False)

    conn = sqlite3.connect(str(env / "session.db"))
    try:
        got = conn.execute("SELECT first_timestamp, day_timestamp, last_timestamp, joules, seconds_charged, "
                           "cost, cost_by_tariff, fallback_joules FROM session_v6").fetchall()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert got == [(100, 50, 200, 7200000, 600, 1.5, '{"0.27048": 7200000}', 0)]
    assert "session_v5" not in tables


@pytest.mark.parametrize("ha_enabled", [False, "False", None])
def test_ha_plugin_disabled_warns_at_startup(env, config_db, caplog, ha_enabled):
    config_db.get.return_value = ha_enabled
    msg = "Tariff: live HA rate enabled but the Home Assistant plugin is disabled - using schedule rate"
    with caplog.at_level(logging.INFO):
        make_plugin(True)
    config_db.get.assert_any_call("homeassistant", "enabled")
    assert [r.getMessage() for r in warnings(caplog, "Home Assistant plugin is disabled")] == [msg]
    assert logwrites(config_db, "Home Assistant plugin is disabled") == [msg]


@pytest.mark.parametrize("enabled,ha_enabled", [(True, "True"), (False, "False")])
def test_no_startup_warning_otherwise(env, config_db, caplog, enabled, ha_enabled):
    config_db.get.return_value = ha_enabled
    with caplog.at_level(logging.INFO):
        make_plugin(enabled)
    assert not warnings(caplog, "Home Assistant plugin is disabled")


def test_session_cost_reset_set(env, clock, state):
    plugin = make_plugin(True)
    assert state["eo_session_cost_reset"] == clock.dt.astimezone().isoformat(timespec="seconds")


def test_reset_mid_slot_settles_pending(env, clock, state):
    plugin = make_plugin(True)
    run_polls(plugin, clock, 14, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    # 10:03:30 - the 10:03 write carried the open slot's pending HA energy at the last rate.
    (row,) = rows(env)
    assert json.loads(row[4]) == {"0.07": row[2]}
    old = plugin._accumulator
    assert old.pending_joules > 0

    state["eo_charger_state_id"] = 1
    run_polls(plugin, clock, 1)
    assert old.pending_joules == 0
    assert old.settled == {0.07: 14 * 36000}
    assert plugin._accumulator is not old
    assert plugin._accumulator.cost_by_tariff() == {}


def test_midnight_split(env, clock, state):
    clock.dt = datetime.datetime(2026, 11, 22, 23, 58, 0)
    plugin = make_plugin(True)
    run_polls(plugin, clock, 7, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    old = plugin._accumulator
    run_polls(plugin, clock, 1, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    # crossed midnight on that poll: the old day's accumulator was settled and replaced
    assert plugin._accumulator is not old
    assert old.pending_joules == 0
    run_polls(plugin, clock, 7, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))

    old_day, new_day = rows(env)
    assert old_day[0] == new_day[0]           # same session
    assert old_day[1] < new_day[1]            # different day rows
    assert json.loads(old_day[4]) == {"0.07": old_day[2]}
    assert json.loads(new_day[4]) == {"0.07": new_day[2]}
    assert new_day[2] == 5 * 36000            # only energy since midnight (00:00:00-00:01:00 write)
    assert new_day[3] == round(new_day[2] * 0.07 / 3600000, 2)


def test_user_settings_controls(env):
    plugin = make_plugin(False)
    controls = {c["name"]: c for c in plugin.get_user_settings()}
    assert controls["ha_rate_enabled"]["type"] == "boolean"
    assert controls["ha_rate_enabled"]["default"] is False
    slider = controls["ha_rate_stale_minutes"]
    assert slider["type"] == "slider"
    assert slider["range"] == [10, 60] and slider["step"] == 5 and slider["default"] == 15


def test_cost_reset_unchanged_by_idle_polls(env, clock, state):
    plugin = make_plugin(True)
    first = state["eo_session_cost_reset"]
    state["eo_charger_state_id"] = 1
    for _ in range(3):
        clock.dt += datetime.timedelta(minutes=5)
        plugin.poll()
    assert state["eo_session_cost_reset"] == first


def test_cost_reset_moves_when_session_with_energy_resets(env, clock, state):
    plugin = make_plugin(True)
    first = state["eo_session_cost_reset"]
    state["eo_ha_rate"] = fresh_rate(clock, 0.07)
    run_polls(plugin, clock, 4, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    assert state["eo_session_joules"] > 0
    clock.dt += datetime.timedelta(minutes=5)
    state["eo_charger_state_id"] = 1
    plugin.poll()
    assert state["eo_session_cost_reset"] == clock.dt.astimezone().isoformat(timespec="seconds")
    assert state["eo_session_cost_reset"] != first


def test_startup_mqtt_disconnected_logs_info_waiting_not_warning(env, clock, state, config_db, caplog):
    state["eo_mqtt_connected"] = False
    p = make_plugin(True)
    with caplog.at_level(logging.INFO):
        run_polls(p, clock, 2)
        state["eo_mqtt_connected"] = True
        run_polls(p, clock, 2)
    assert not warnings(caplog, "falling back")
    waiting = [r for r in caplog.records
               if r.levelno == logging.INFO and "waiting for first HA rate" in r.getMessage()]
    assert len(waiting) == 1


def test_reason_stale(env, clock, state):
    plugin = make_plugin(True)
    state["eo_ha_rate"] = {"value": 0.07, "received_at": clock.ts() - 3600}
    run_polls(plugin, clock, 3, step=60)
    assert state["eo_tariff_rate_reason"] == "stale"


def test_reason_empty_when_ha_fresh(env, clock, state):
    plugin = make_plugin(True)
    state["eo_ha_rate"] = fresh_rate(clock, 0.07)
    run_polls(plugin, clock, 3, step=60)
    assert state["eo_tariff_rate_source"] == "ha"
    assert state["eo_tariff_rate_reason"] == ""


def test_reason_disabled(env, clock, state):
    plugin = make_plugin(False)
    run_polls(plugin, clock, 3, step=60)
    assert state["eo_tariff_rate_source"] == "schedule"
    assert state["eo_tariff_rate_reason"] == "disabled"


def test_disable_reset_poll_reports_schedule_rate(env, clock, state):
    # The poll that ends a session latches the switch off; it must not leave the HA rate
    # beside a "schedule" source for that one update.
    plugin = make_plugin(True)
    run_polls(plugin, clock, 2, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    assert state["eo_session_current_tariff"] == 0.07
    plugin.pluginConfig["ha_rate_enabled"] = False
    state["eo_charger_state_id"] = 1   # unplugged: this poll resets the session
    run_polls(plugin, clock, 1, before_poll=lambda: state.update(eo_ha_rate=fresh_rate(clock, 0.07)))
    assert state["eo_tariff_rate_source"] == "schedule"
    assert state["eo_tariff_rate_reason"] == "disabled"
    assert state["eo_session_current_tariff"] == 0.27048
