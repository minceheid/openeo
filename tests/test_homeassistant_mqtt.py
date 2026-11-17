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
_gs = sys.modules["globalState"]
if not hasattr(_gs, "stateDict"):
    _gs.stateDict = {}
    _gs.MIN_CHARGING_CURRENT = 6
    # configDB.get(module, key, default) -> default
    _gs.configDB = mock.Mock(get=lambda module, key, default=None: default)

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

    def test_setup_falls_back_to_v1_callbacks_on_paho_1x(self):
        # Debian bookworm/bullseye ship paho 1.6/1.5, which has no CallbackAPIVersion.
        fake_mqtt = mock.Mock(spec=["Client", "MQTT_ERR_SUCCESS"])
        with mock.patch.object(homeassistant, "mqtt", fake_mqtt), \
                mock.patch.object(homeassistant.threading, "Thread"):
            p = make_plugin()
            p._setup_mqtt()
            fake_mqtt.Client.assert_called_once_with(client_id="openeo-openeo_charger_1")
            c = fake_mqtt.Client.return_value
            c.connect_async.assert_called_once_with(BROKER_HOST, BROKER_PORT, 60)
            with self.assertLogs(homeassistant._LOGGER, level="INFO") as cm:
                c.on_connect(c, None, {}, 0)          # v1 signature
                c.on_disconnect(c, None, 7)           # v1 signature, MQTT_ERR_CONN_LOST
        self.assertTrue(p.connected is False)
        self.assertTrue(any("MQTT connected to 192.168.1.20:1883" in l for l in cm.output))
        self.assertTrue(any("MQTT disconnected: reason=7" in l for l in cm.output))

    def test_connect_success_still_announces_online_and_subscribes(self):
        p = make_plugin()
        with mock.patch.object(homeassistant.threading, "Thread"):
            p._on_connect(p.mqtt_client, None, mock.Mock(),
                          ReasonCode(PacketTypes.CONNACK, "Success"), None)
        self.assertTrue(p.connected)
        p.mqtt_client.publish.assert_any_call(p._get_availability_topic(),
                                              payload="online", qos=1, retain=True)
        self.assertTrue(p.mqtt_client.subscribe.called)


def _at(t):
    return mock.patch.object(homeassistant.time, "monotonic", return_value=t)


def connect(p, at, reason="Success"):
    with _at(at), mock.patch.object(homeassistant.threading, "Thread"):
        p._on_connect(p.mqtt_client, None, mock.Mock(), ReasonCode(PacketTypes.CONNACK, reason), None)


def disconnect(p, reason, at, from_broker=False):
    flags = mock.Mock(is_disconnect_packet_from_server=from_broker)
    with _at(at):
        p._on_disconnect(p.mqtt_client, None, flags, ReasonCode(PacketTypes.DISCONNECT, reason), None)


def fail(p, at):
    with _at(at):
        p._on_connect_fail(p.mqtt_client, None)


@unittest.skipUnless(PAHO and homeassistant.MQTT_AVAILABLE, "needs paho-mqtt 2.x")
class OutageLoggingTests(unittest.TestCase):
    def setUp(self):
        self.cm = self.enterContext(self.assertLogs(homeassistant._LOGGER, level="INFO"))
        # assertLogs fails on an empty block; make sure there is always one record.
        homeassistant._LOGGER.info("test start")

    @property
    def logs(self):
        return self.cm.output

    def test_fmt_duration(self):
        for s, want in [(0, "0s"), (42, "42s"), (282, "4m42s"), (7980, "2h13m")]:
            self.assertEqual(homeassistant._fmt_duration(s), want)

    def test_disconnect_logs_reason_broker_and_uptime(self):
        p = make_plugin(); connect(p, at=1000); disconnect(p, "Keep alive timeout", at=1000 + 7980)
        self.assertIn('WARNING:lib.homeassistant:MQTT disconnected: reason="Keep alive timeout" (code 141) '
                      'from_broker=no broker=192.168.1.20:1883 up_for=2h13m', self.logs)

    def test_double_disconnect_keeps_first_outage_start(self):
        p = make_plugin(); connect(p, at=0); disconnect(p, "Unspecified error", at=100)
        disconnect(p, "Unspecified error", at=100.4)
        self.assertEqual(p._down_since, 100)

    def test_disconnect_before_connect_says_unknown(self):
        p = make_plugin(); disconnect(p, "Unspecified error", at=5)
        self.assertTrue(any("up_for=unknown" in l for l in self.logs))

    def test_disconnect_with_plain_int_reason_does_not_raise(self):
        p = make_plugin()
        p._on_disconnect(p.mqtt_client, None, mock.Mock(is_disconnect_packet_from_server=False), 7, None)
        self.assertTrue(any("reason=7" in l for l in self.logs))

    def test_connect_fail_counts_attempts(self):
        p = make_plugin(); connect(p, at=0); disconnect(p, "Unspecified error", at=10)
        fail(p, at=11); fail(p, at=13)
        self.assertIn("WARNING:lib.homeassistant:MQTT connect attempt 2 failed, down for 3s", self.logs)

    def test_reconnect_reports_outage_attempts_and_failed_publishes(self):
        p = make_plugin(); connect(p, at=0); disconnect(p, "Unspecified error", at=10)
        fail(p, at=11)
        p.mqtt_client.publish.return_value.rc = homeassistant.mqtt.MQTT_ERR_NO_CONN
        p._publish_state()
        connect(p, at=292)
        self.assertIn("INFO:lib.homeassistant:MQTT connected to 192.168.1.20:1883 after 4m42s down, "
                      "2 attempt(s), 1 state publish(es) failed while down", self.logs)

    def test_first_connect_line(self):
        p = make_plugin(); connect(p, at=0)
        self.assertIn("INFO:lib.homeassistant:MQTT connected to 192.168.1.20:1883", self.logs)

    def test_broker_refusal_logged_and_counted(self):
        p = make_plugin(); connect(p, at=0, reason="Not authorized")
        self.assertTrue(any(l.startswith("ERROR") and 'reason="Not authorized" (code 135)' in l
                            for l in self.logs))
        self.assertEqual(p._failed_attempts, 1)

    def test_expected_disconnect_is_info(self):
        p = make_plugin(); connect(p, at=0); disconnect(p, "Success", at=5)
        self.assertIn("INFO:lib.homeassistant:Disconnected from MQTT broker", self.logs)

    def test_disconnect_during_outage_reports_down_for_not_uptime(self):
        # A reconnect whose TCP connect works but dies before CONNACK fires on_disconnect, not on_connect_fail.
        p = make_plugin(); connect(p, at=0); disconnect(p, "Unspecified error", at=100)
        fail(p, at=110); disconnect(p, "Unspecified error", at=160)
        last = [l for l in self.logs if "MQTT disconnected" in l][-1]
        self.assertIn("up_for=none down_for=1m00s", last)
        self.assertEqual(p._down_since, 100)

    def test_connect_success_side_effects_cannot_raise_into_paho(self):
        p = make_plugin()
        with mock.patch.object(p, "_subscribe_to_commands", side_effect=RuntimeError("boom")):
            connect(p, at=0)  # must not raise
        self.assertTrue(any(l.startswith("ERROR") and "boom" in l for l in self.logs))

    def test_no_credentials_in_logs(self):
        with mock.patch.object(homeassistant.mqtt, "Client"):
            p = make_plugin(mqtt_username="user1", mqtt_password="s3cret")
            p._setup_mqtt()
        connect(p, at=0); disconnect(p, "Unspecified error", at=1); fail(p, at=2); connect(p, at=3)
        self.assertFalse(any("user1" in l or "s3cret" in l for l in self.logs))


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
