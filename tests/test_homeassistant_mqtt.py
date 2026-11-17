#!/usr/bin/env python3
"""Tests for the Home Assistant plugin's MQTT connection handling and logging."""

import logging, os, sys, types, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# lib.homeassistant imports globalState (opens /home/pi/etc) and util (needs psutil).
# Neither is needed for the MQTT callbacks, so stub them before the import.
for _name in ("globalState", "util"):
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)
sys.modules["globalState"].stateDict = getattr(sys.modules["globalState"], "stateDict", {})

from lib import homeassistant  # noqa: E402

try:
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.reasoncodes import ReasonCode
    PAHO = True
except ImportError:
    PAHO = False

BROKER_HOST = "192.168.1.20"
BROKER_PORT = 1883


def make_plugin(**config):
    """A plugin that hasn't connected, with a fake client attached."""
    cfg = {"enabled": False, "mqtt_host": BROKER_HOST, "mqtt_port": BROKER_PORT}
    cfg.update(config)
    plugin = homeassistant.homeassistantClassPlugin(cfg)
    plugin.mqtt_client = mock.Mock()
    return plugin


@unittest.skipUnless(PAHO and homeassistant.MQTT_AVAILABLE, "needs paho-mqtt 2.x")
class SetupTests(unittest.TestCase):
    def test_setup_uses_callback_api_v2(self):
        with mock.patch.object(homeassistant.mqtt, "Client") as Client:
            p = make_plugin()
            p._setup_mqtt()
        Client.assert_called_once_with(callback_api_version=homeassistant.mqtt.CallbackAPIVersion.VERSION2,
                                       client_id="openeo-openeo_charger_1")
        c = Client.return_value
        self.assertEqual(c.on_connect_fail, p._on_connect_fail)
        c.connect_async.assert_called_once_with(BROKER_HOST, BROKER_PORT, 60)

    def test_setup_attaches_paho_logger(self):
        with mock.patch.object(homeassistant.mqtt, "Client") as Client:
            make_plugin()._setup_mqtt()
        Client.return_value.enable_logger.assert_called_once_with(homeassistant._PAHO_LOGGER)
        self.assertEqual(homeassistant._PAHO_LOGGER.name, homeassistant._LOGGER.name + ".paho")
        self.assertEqual(homeassistant._PAHO_LOGGER.level, logging.DEBUG)  # testing build; Task 4 → WARNING

    def test_connect_success_still_announces_online_and_subscribes(self):
        p = make_plugin()
        with mock.patch.object(homeassistant.threading, "Thread"):
            p._on_connect(p.mqtt_client, None, mock.Mock(),
                          ReasonCode(PacketTypes.CONNACK, "Success"), None)
        self.assertTrue(p.connected)
        p.mqtt_client.publish.assert_any_call(p._get_availability_topic(),
                                              payload="online", qos=1, retain=True)
        self.assertTrue(p.mqtt_client.subscribe.called)


# Stable client_id (#282), using a fake paho module so it runs without paho installed.
def _plugin(config):
    plugin = homeassistant.homeassistantClassPlugin.__new__(homeassistant.homeassistantClassPlugin)
    plugin.mqtt_client = None
    plugin.connected = False
    plugin.get_config = config.get
    return plugin


def test_client_uses_stable_client_id_so_broker_takes_over_stale_session():
    # With an empty client_id the broker treats each reconnect as a new client, so the old
    # session lingers until its keepalive expires and its retained "offline" will then
    # overwrites the new "online" (HA entities stuck unavailable).
    plugin = _plugin({"device_id": "openeo_charger", "mqtt_host": "broker", "mqtt_port": 1883})
    with mock.patch.object(homeassistant, "mqtt", create=True) as fake_mqtt:
        plugin._setup_mqtt()
    client_cls = fake_mqtt.Client
    assert client_cls.call_args.kwargs.get("client_id") == "openeo-openeo_charger"


if __name__ == "__main__":
    unittest.main()
