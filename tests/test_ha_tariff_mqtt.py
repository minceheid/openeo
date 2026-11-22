"""Tariff rate and HA status wiring in the Home Assistant plugin."""
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


def test_receipt_logged_at_debug_not_info(plugin, state, caplog):
    with caplog.at_level(logging.DEBUG):
        plugin._on_message(None, None, msg(RATE_TOPIC, "0.07"))
        plugin._on_message(None, None, msg(STATUS_TOPIC, "online"))
    received = [r for r in caplog.records if "Received command" in r.getMessage()]
    assert received == []
    assert not [r for r in caplog.records if r.levelno >= logging.INFO
                and ("tariff_rate" in r.getMessage() or "status" in r.getMessage())]


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
