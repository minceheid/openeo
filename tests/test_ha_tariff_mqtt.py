"""Tariff rate and HA status wiring in the Home Assistant plugin."""
import json
import logging
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# globalState builds the live config under /home/pi on import; the plugin only needs the name.
sys.modules.setdefault("globalState", mock.MagicMock())

from lib import homeassistant as ha  # noqa: E402

RATE_TOPIC = "openeo/eo1/command/tariff_rate/set"
STATUS_TOPIC = "homeassistant/status"


def msg(topic, payload):
    return mock.Mock(topic=topic, payload=payload.encode("utf-8"))


@pytest.fixture
def plugin():
    p = ha.homeassistantClassPlugin.__new__(ha.homeassistantClassPlugin)
    p.mqtt_client = mock.Mock()
    p.connected = True
    p.discovery_sent = False
    p.get_config = lambda k: {"device_id": "eo1", "mqtt_discovery_prefix": "homeassistant"}[k]
    p._tariff_warned_units = set()
    return p


@pytest.fixture
def state():
    d = {"eo_ha_rate": None, "eo_ha_online": None, "eo_mqtt_connected": False}
    with mock.patch.object(ha.globalState, "stateDict", d), \
            mock.patch.object(ha.globalState, "configDB", mock.Mock()):
        yield d


def test_subscribes_tariff_and_status(plugin, state):
    plugin._subscribe_to_commands()
    topics = [c.args[0] for c in plugin.mqtt_client.subscribe.call_args_list]
    assert RATE_TOPIC in topics
    assert STATUS_TOPIC in topics


def test_tariff_message_stored(plugin, state):
    plugin._on_message(None, None, msg(RATE_TOPIC, '{"rate": "0.07", "unit": "GBP/kWh"}'))
    assert state["eo_ha_rate"]["value"] == 0.07


@pytest.mark.parametrize("payload,expected", [
    ("online", True), ("offline", False), (" ONLINE\n", True), ("Offline", False),
])
def test_ha_status(plugin, state, payload, expected):
    plugin._on_message(None, None, msg(STATUS_TOPIC, payload))
    assert state["eo_ha_online"] is expected


def test_ha_status_ignores_other_payloads(plugin, state):
    state["eo_ha_online"] = True
    plugin._on_message(None, None, msg(STATUS_TOPIC, "garbage"))
    assert state["eo_ha_online"] is True


def test_receipt_logged_at_info(plugin, state, caplog):
    with caplog.at_level(logging.INFO):
        plugin._on_message(None, None, msg(RATE_TOPIC, "0.07"))
        plugin._on_message(None, None, msg(STATUS_TOPIC, "online"))
    info = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert f"Received tariff rate on {RATE_TOPIC}: '0.07'" in info
    assert f"Received HA status on {STATUS_TOPIC}: 'online'" in info
    # Routed before the generic command handler, so no "Received command" line.
    assert not [m for m in info if "Received command" in m]


def test_receipt_log_truncates_payload(plugin, state, caplog):
    with caplog.at_level(logging.INFO):
        plugin._on_message(None, None, msg(RATE_TOPIC, "9" * 500))
    line = [r.getMessage() for r in caplog.records
            if r.getMessage().startswith("Received tariff rate")][0]
    assert line == f"Received tariff rate on {RATE_TOPIC}: {('9' * 64)!r}"


def test_warning_goes_to_logger_and_app_events(plugin, state):
    plugin._on_message(None, None, msg(RATE_TOPIC, "abc"))
    assert state["eo_ha_rate"]["value"] is None
    assert ha.globalState.configDB.logwrite.called


def test_missing_configdb_cannot_raise(plugin, state):
    with mock.patch.object(ha.globalState, "configDB", None):
        plugin._on_message(None, None, msg(RATE_TOPIC, "abc"))
    assert state["eo_ha_rate"]["value"] is None


def test_disconnect_clears_rate(plugin, state):
    state["eo_ha_rate"] = {"value": 0.07, "received_at": 1.0}
    state["eo_mqtt_connected"] = True
    plugin._on_disconnect(None, None, mock.Mock(is_disconnect_packet_from_server=False), 1, None)
    assert state["eo_ha_rate"] is None
    assert state["eo_mqtt_connected"] is False


def test_clean_disconnect_also_clears(plugin, state):
    state["eo_ha_rate"] = {"value": 0.07, "received_at": 1.0}
    state["eo_mqtt_connected"] = True
    plugin._on_disconnect(None, None, mock.Mock(is_disconnect_packet_from_server=False), 0, None)
    assert state["eo_ha_rate"] is None
    assert state["eo_mqtt_connected"] is False


def test_connect_sets_flag(plugin, state):
    plugin.connected = False
    plugin._get_availability_topic = lambda: "openeo/eo1/availability"
    with mock.patch.object(ha.threading, "Thread"):
        plugin._on_connect(None, None, mock.Mock(), 0, None)
    assert state["eo_mqtt_connected"] is True


def test_failed_connect_leaves_flag(plugin, state):
    plugin._on_connect(None, None, mock.Mock(), 5, None)
    assert state["eo_mqtt_connected"] is False


def test_disconnect_forgets_ha_online(plugin, state):
    # The HA birth message is not retained, so an old False must not survive a reconnect.
    state["eo_ha_online"] = False
    plugin._on_disconnect(None, None, mock.Mock(is_disconnect_packet_from_server=False), 1, None)
    assert state["eo_ha_online"] is None


def discovery_configs(plugin):
    configs = {}
    ha.globalState.configDB.get.return_value = 10
    ha.globalState.MAX_CHARGING_CURRENT = 32
    ha.globalState.MIN_CHARGING_CURRENT = 6
    plugin._get_device_info = lambda: {"identifiers": ["eo1"]}
    plugin._get_availability_topic = lambda: "openeo/eo1/availability"
    plugin._get_schedules = lambda: []
    plugin._get_solar_schedules = lambda: []
    plugin._published_schedule_count = 0
    plugin._published_solar_schedule_count = 0
    plugin._send_discovery()
    for c in plugin.mqtt_client.publish.call_args_list:
        topic, payload = c.args[0], c.args[1]
        if topic.endswith("/config") and payload:
            configs[topic.split("/")[-2]] = json.loads(payload)
    return configs


def published_state(plugin):
    ha.globalState.configDB.get.return_value = 10
    plugin._get_schedules = lambda: []
    plugin._get_solar_schedules = lambda: []
    plugin._bool_config = lambda *a: False
    plugin._publish_state()
    call = [c for c in plugin.mqtt_client.publish.call_args_list if c.args[0] == "openeo/eo1/state"][-1]
    return json.loads(call.args[1])


def test_state_payload_has_rate_fields(plugin, state):
    state.update(eo_session_current_tariff=0.07, eo_tariff_rate_source="ha",
                 eo_session_cost_reset="2026-11-22T10:00:00+00:00")
    payload = published_state(plugin)
    assert payload["current_rate"] == 0.07
    assert payload["rate_source"] == "ha"
    assert payload["session_cost_reset"] == "2026-11-22T10:00:00+00:00"


def test_state_payload_rate_defaults(plugin, state):
    payload = published_state(plugin)
    assert payload["current_rate"] == 0.0
    assert payload["rate_source"] == "schedule"
    assert payload["session_cost_reset"] is None


def test_discovery_has_rate_sensors(plugin, state):
    configs = discovery_configs(plugin)
    rate = configs["current_rate"]
    assert rate["name"] == "Current Rate"
    assert rate["value_template"] == "{{ value_json.current_rate }}"
    assert rate["unit_of_measurement"] == "GBP/kWh"
    assert rate["state_class"] == "measurement"
    assert rate["icon"] == "mdi:cash"
    assert "device_class" not in rate
    source = configs["rate_source"]
    assert source["name"] == "Rate Source"
    assert source["value_template"] == "{{ value_json.rate_source }}"
    assert source["icon"] == "mdi:swap-horizontal"


def test_session_cost_sensor_state_class(plugin, state):
    cost = discovery_configs(plugin)["session_cost"]
    assert cost["state_class"] == "total"
    assert cost["last_reset_value_template"] == "{{ value_json.session_cost_reset }}"


SWITCH_TOPIC = "openeo/eo1/command/ha_rate_enabled/set"


def test_subscribes_ha_rate_enabled(plugin, state):
    plugin._subscribe_to_commands()
    topics = [c.args[0] for c in plugin.mqtt_client.subscribe.call_args_list]
    assert SWITCH_TOPIC in topics


@pytest.mark.parametrize("payload,expected", [
    ("ON", True), ("true", True), ("1", True), ("OFF", False), ("0", False), ("false", False),
])
def test_ha_rate_enabled_command(plugin, state, payload, expected):
    plugin._publish_state = mock.Mock()
    plugin._on_message(None, None, msg(SWITCH_TOPIC, payload))
    ha.globalState.configDB.set.assert_called_once_with("chargersession", "ha_rate_enabled", expected)
    plugin._publish_state.assert_called_once_with()


def test_state_payload_ha_rate_enabled(plugin, state):
    ha.globalState.configDB.get.return_value = 10
    plugin._get_schedules = lambda: []
    plugin._get_solar_schedules = lambda: []
    plugin._bool_config = lambda module, key, default=False: (module, key) == ("chargersession", "ha_rate_enabled")
    plugin._publish_state()
    call = [c for c in plugin.mqtt_client.publish.call_args_list if c.args[0] == "openeo/eo1/state"][-1]
    payload = json.loads(call.args[1])
    assert payload["ha_rate_enabled"] is True
    assert payload["solar_enabled"] is False


def test_state_payload_ha_rate_received(plugin, state):
    import datetime
    state.update(eo_ha_rate={"value": 0.07, "received_at": 1795341600.0}, eo_tariff_rate_reason="stale")
    payload = published_state(plugin)
    assert payload["ha_rate_received"] == 0.07
    expected = datetime.datetime.fromtimestamp(1795341600.0).astimezone().isoformat(timespec="seconds")
    assert payload["ha_rate_received_at"] == expected
    assert payload["rate_reason"] == "stale"


@pytest.mark.parametrize("rate", [None, {"value": None, "received_at": 1795341600.0}])
def test_state_payload_ha_rate_received_none(plugin, state, rate):
    state["eo_ha_rate"] = rate
    payload = published_state(plugin)
    assert payload["ha_rate_received"] is None
    if rate is None:
        assert payload["ha_rate_received_at"] is None
    assert payload["rate_reason"] == ""
    assert payload["ha_rate_enabled"] is False


def test_discovery_has_use_live_rate_switch(plugin, state):
    sw = discovery_configs(plugin)["ha_rate_enabled"]
    solar = discovery_configs(plugin)["solar_enabled"]
    assert sw["name"] == "Use Live Rate"
    assert sw["command_topic"] == SWITCH_TOPIC
    assert sw["state_topic"] == "openeo/eo1/state"
    assert sw["value_template"] == "{{ 'ON' if value_json.ha_rate_enabled else 'OFF' }}"
    assert sw["icon"] == "mdi:cash-sync"
    for k in ("payload_on", "payload_off", "state_on", "state_off", "device_class"):
        assert sw[k] == solar[k]
    assert sw["unique_id"] == "eo1_ha_rate_enabled"


def test_discovery_has_ha_rate_received_sensor(plugin, state):
    s = discovery_configs(plugin)["ha_rate_received"]
    assert s["name"] == "HA Rate Received"
    assert s["value_template"] == "{{ value_json.ha_rate_received }}"
    assert s["unit_of_measurement"] == "GBP/kWh"
    assert s["state_class"] == "measurement"
    assert s["icon"] == "mdi:cash-check"
    assert s["json_attributes_topic"] == "openeo/eo1/state"
    assert s["json_attributes_template"] == "{{ {'received_at': value_json.ha_rate_received_at} | tojson }}"


def test_rate_source_has_reason_attribute(plugin, state):
    s = discovery_configs(plugin)["rate_source"]
    assert s["json_attributes_topic"] == "openeo/eo1/state"
    assert s["json_attributes_template"] == "{{ {'reason': value_json.rate_reason} | tojson }}"
