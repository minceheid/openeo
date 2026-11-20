"""MQTT client setup in the Home Assistant plugin."""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# globalState builds the live config under /home/pi on import; the plugin only needs the name.
sys.modules.setdefault("globalState", mock.MagicMock())

from lib import homeassistant as ha  # noqa: E402


def _plugin(config):
    plugin = ha.homeassistantClassPlugin.__new__(ha.homeassistantClassPlugin)
    plugin.mqtt_client = None
    plugin.connected = False
    plugin.get_config = config.get
    return plugin


def test_client_uses_stable_client_id_so_broker_takes_over_stale_session():
    # With an empty client_id the broker treats each reconnect as a new client, so the old
    # session lingers until its keepalive expires and its retained "offline" will then
    # overwrites the new "online" (HA entities stuck unavailable).
    plugin = _plugin({"device_id": "openeo_charger", "mqtt_host": "broker", "mqtt_port": 1883})
    with mock.patch.object(ha, "mqtt", create=True) as fake_mqtt:
        plugin._setup_mqtt()
    client_cls = fake_mqtt.Client
    assert client_cls.call_args.kwargs.get("client_id") == "openeo-openeo_charger"
