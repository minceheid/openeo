#################################################################################
"""
OpenEO Module: Home Assistant MQTT Integration
Publishes OpenEO charger state to Home Assistant via MQTT with auto-discovery.

Configuration example:
"homeassistant": {
    "enabled": true,
    "mqtt_host": "localhost",
    "mqtt_port": 1883,
    "mqtt_username": "",
    "mqtt_password": "",
    "mqtt_discovery_prefix": "homeassistant",
    "device_name": "OpenEO Charger",
    "device_id": "openeo_charger_1",
    "publish_interval": 5
}
"""
#################################################################################

import datetime
import logging
import json
import time
import threading
from lib.PluginSuperClass import PluginSuperClass
import globalState
import util
from lib import wifi_status
from lib import tariffrate

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.getLogger(__name__).warning("paho-mqtt not available - Home Assistant integration disabled")

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

# paho's own log (keepalive pings, socket errors, retries) goes to a child logger.
# Only its warnings and errors are kept. To see every keepalive ping, set this to
# logging.DEBUG: the root logger runs at INFO, so the child's level must be set here.
PAHO_LOG_LEVEL = logging.WARNING
_PAHO_LOGGER = _LOGGER.getChild("paho")
_PAHO_LOGGER.setLevel(PAHO_LOG_LEVEL)

# During an outage, log the first few failed reconnects one by one, then one
# "still down" line per interval until it reconnects.
CONNECT_FAILS_LOGGED = 5
STILL_DOWN_LOG_INTERVAL = 30 * 60  # seconds


def _fmt_duration(seconds):
    """42 -> '42s', 282 -> '4m42s', 7980 -> '2h13m'"""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def _reason_text(reason_code):
    """'reason="Keep alive timeout" (code 141)' for a paho ReasonCode; never raises."""
    try:
        return f'reason="{reason_code.getName()}" (code {reason_code.value})'
    except Exception:
        return f"reason={reason_code!r}"

#################################################################################
class homeassistantClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Home Assistant MQTT"
    CORE_PLUGIN = False
    
    pluginParamSpec = {
        "enabled": {"type": "bool", "default": False},
        "mqtt_host": {"type": "str", "default": "localhost"},
        "mqtt_port": {"type": "int", "default": 1883},
        "mqtt_username": {"type": "str", "default": ""},
        "mqtt_password": {"type": "str", "default": ""},
        "mqtt_discovery_prefix": {"type": "str", "default": "homeassistant"},
        "device_name": {"type": "str", "default": "OpenEO Charger"},
        "device_id": {"type": "str", "default": "openeo_charger_1"},
        "publish_interval": {"type": "int", "default": 5}
    }
    
    def __init__(self, configParam):
        self.mqtt_client = None
        self.connected = False
        self.last_publish = 0
        self.discovery_sent = False
        self._published_schedule_count = 0
        self._published_solar_schedule_count = 0
        # Connection bookkeeping for the log (time.monotonic() seconds)
        self._up_since = None
        self._down_since = None
        self._failed_attempts = 0
        self._failed_publishes = 0
        self._outage_events = 0      # failures logged or suppressed in this outage
        self._still_down_logged = 0  # "still down" lines written in this outage
        self._tariff_warned_units = set()
        super().__init__(configParam)
        
        if not MQTT_AVAILABLE:
            _LOGGER.error("paho-mqtt library not available - install with: pip install paho-mqtt")
            return
            
        if self.get_config("enabled"):
            self._setup_mqtt()
    
    def _setup_mqtt(self):
        """Initialize MQTT client and connect to broker"""
        try:
            # A stable client_id lets the broker take over our old session the moment we
            # reconnect. With paho's default empty id each reconnect is a new client, so the
            # old session lingers until its keepalive expires (1.5x) and its retained
            # "offline" will then overwrites the "online" we just published, leaving every
            # HA entity unavailable while we carry on publishing state.
            client_id = f"openeo-{self.get_config('device_id')}"
            if hasattr(mqtt, "CallbackAPIVersion"):
                self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
                on_connect, on_disconnect = self._on_connect, self._on_disconnect
            else:
                # paho-mqtt 1.x (Debian bookworm and older): v1 callbacks, adapted to the v2 signatures.
                self.mqtt_client = mqtt.Client(client_id=client_id)
                on_connect = lambda c, u, flags, rc: self._on_connect(c, u, flags, rc, None)
                on_disconnect = lambda c, u, rc: self._on_disconnect(c, u, None, rc, None)
            self.mqtt_client.enable_logger(_PAHO_LOGGER)

            # Set authentication if provided
            username = self.get_config("mqtt_username")
            password = self.get_config("mqtt_password")
            if username:
                self.mqtt_client.username_pw_set(username, password)
            
            # Set callbacks
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.on_disconnect = on_disconnect
            self.mqtt_client.on_connect_fail = self._on_connect_fail  # paho >= 1.6
            self.mqtt_client.on_message = self._on_message

            self.mqtt_client.will_set(
                self._get_availability_topic(),
                payload="offline",
                qos=1,
                retain=True,
            )

            # Connect to broker
            host = self.get_config("mqtt_host")
            port = self.get_config("mqtt_port")
            
            _LOGGER.info(f"Connecting to MQTT broker at {host}:{port}")
            self.mqtt_client.connect_async(host, port, 60)
            self.mqtt_client.loop_start()
            
        except Exception as e:
            _LOGGER.error(f"Failed to setup MQTT connection: {e}")
    
    def _broker(self):
        return f"{self.get_config('mqtt_host')}:{self.get_config('mqtt_port')}"

    def _start_outage(self, now):
        """Note when the link went down; a second callback for the same drop keeps the first time."""
        if self._down_since is None:
            self._down_since = now

    def _log_connected(self, now):
        """Log a successful connect, with the outage summary when it ends one, and reset the counters."""
        try:
            if self._down_since is None:
                _LOGGER.info(f"MQTT connected to {self._broker()}")
            else:
                _LOGGER.info(
                    f"MQTT connected to {self._broker()} after {_fmt_duration(now - self._down_since)} down, "
                    f"{self._failed_attempts + 1} attempt(s), "
                    f"{self._failed_publishes} state publish(es) failed while down")
        except Exception:
            _LOGGER.exception("Failed to log MQTT connect")
        self._up_since = now
        self._down_since = None
        self._failed_attempts = 0
        self._failed_publishes = 0
        self._outage_events = 0
        self._still_down_logged = 0

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        """Callback for MQTT connection"""
        now = time.monotonic()
        if not getattr(reason_code, "is_failure", reason_code != 0):
            self.connected = True
            globalState.stateDict["eo_mqtt_connected"] = True
            self._log_connected(now)
            # An exception here would kill paho's network thread and stop reconnects for good.
            try:
                self.mqtt_client.publish(
                    self._get_availability_topic(),
                    payload="online",
                    qos=1,
                    retain=True,
                )
                # Subscribe to command topics
                self._subscribe_to_commands()
                # Send discovery messages after connection
                threading.Thread(target=self._send_discovery, daemon=True).start()
            except Exception:
                _LOGGER.exception("Failed to finish MQTT connect setup")
        else:
            try:
                self._start_outage(now)
                self._failed_attempts += 1
                _LOGGER.error(f"MQTT broker {self._broker()} refused connection: {_reason_text(reason_code)}")
            except Exception:
                _LOGGER.exception("Failed to log MQTT connection refusal")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Callback for MQTT disconnection"""
        self.connected = False
        self.discovery_sent = False
        # The last rate is kept: the stale timer decides when it is too old to use, so a brief
        # broker blip does not drop costing to the schedule rate.
        globalState.stateDict["eo_mqtt_connected"] = False
        # HA's birth message is not retained, so its status is unknown until the next one.
        globalState.stateDict["eo_ha_online"] = None
        try:
            if reason_code == 0:
                _LOGGER.info("Disconnected from MQTT broker")
                return
            now = time.monotonic()
            from_broker = "yes" if getattr(disconnect_flags, "is_disconnect_packet_from_server", False) else "no"
            if self._down_since is not None:
                # Already down: a doubled callback, or a reconnect attempt that died before CONNACK.
                link = f"up_for=none down_for={_fmt_duration(now - self._down_since)}"
            elif self._up_since is None:
                link = "up_for=unknown"
            else:
                link = f"up_for={_fmt_duration(now - self._up_since)}"
            if from_broker == "no" and getattr(reason_code, "value", None) == 128:
                # paho v2 reports a dropped socket as 128 "Unspecified error"; nothing came from the broker.
                reason = 'reason="Connection lost"'
            else:
                reason = _reason_text(reason_code)
            message = f"MQTT disconnected: {reason} from_broker={from_broker} broker={self._broker()} {link}"
            if self._down_since is None:
                self._start_outage(now)
                _LOGGER.warning(message)
            else:
                self._log_outage_event(now, message)
        except Exception:
            _LOGGER.exception("Failed to log MQTT disconnect")

    def _on_connect_fail(self, client, userdata):
        """Callback for a failed connection attempt (paho retries on its own)"""
        try:
            now = time.monotonic()
            self._start_outage(now)
            self._failed_attempts += 1
            self._log_outage_event(now, f"MQTT connect attempt {self._failed_attempts} failed, "
                                        f"down for {_fmt_duration(now - self._down_since)}")
        except Exception:
            _LOGGER.exception("Failed to log MQTT connect failure")

    def _log_outage_event(self, now, message):
        """Log a failure during an outage: the first few one by one, then a 'still down' line per interval.

        paho keeps retrying every 2 minutes at most, which would be ~720 lines a day in a long outage.
        """
        self._outage_events += 1
        if self._outage_events < CONNECT_FAILS_LOGGED:
            _LOGGER.warning(message)
        elif self._outage_events == CONNECT_FAILS_LOGGED:
            _LOGGER.warning(f"{message}; further failures summarised every {_fmt_duration(STILL_DOWN_LOG_INTERVAL)}")
        else:
            down_for = now - self._down_since
            if down_for >= STILL_DOWN_LOG_INTERVAL * (self._still_down_logged + 1):
                self._still_down_logged = int(down_for // STILL_DOWN_LOG_INTERVAL)
                _LOGGER.warning(f"MQTT still down after {_fmt_duration(down_for)}, "
                                f"{self._failed_attempts} failed attempt(s)")

    def _subscribe_to_commands(self):
        """Subscribe to MQTT command topics for control"""
        if not self.connected:
            return
        
        device_id = self.get_config("device_id")
        command_topics = [
            f"openeo/{device_id}/command/switch/set",
            f"openeo/{device_id}/command/current_limit/set",
            f"openeo/{device_id}/command/enable_plugin/set",
            f"openeo/{device_id}/command/schedule/#",
            f"openeo/{device_id}/command/solar_schedule/#",
            f"openeo/{device_id}/command/solar_enable/set",
            f"openeo/{device_id}/command/ha_rate_enabled/set",
            f"openeo/{device_id}/command/tariff_rate/set",
            f"{self.get_config('mqtt_discovery_prefix')}/status",
        ]
        
        for topic in command_topics:
            try:
                self.mqtt_client.subscribe(topic)
                _LOGGER.info(f"Subscribed to command topic: {topic}")
            except Exception as e:
                _LOGGER.error(f"Failed to subscribe to {topic}: {e}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT command messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8').strip()
            device_id = self.get_config("device_id")
            
            prefix = self.get_config("mqtt_discovery_prefix")

            # Logged at INFO so the incoming rate can be checked in the journal. The payload is
            # truncated because the topic is writable by anything with broker credentials.
            if topic == f"openeo/{device_id}/command/tariff_rate/set":
                _LOGGER.info(f"Received tariff rate on {topic}: {payload[:64]!r}")
                tariffrate.apply_rate_message(
                    payload, time.time(), globalState.stateDict,
                    self._tariff_warned_units, self._tariff_log)
                return
            if topic == f"{prefix}/status":
                _LOGGER.info(f"Received HA status on {topic}: {payload[:64]!r}")
                status = payload.lower()
                if status in ("online", "offline"):
                    globalState.stateDict["eo_ha_online"] = (status == "online")
                return

            _LOGGER.info(f"Received command on {topic}: {payload}")
            
            if topic == f"openeo/{device_id}/command/switch/set":
                self._handle_switch_command(payload)
            elif topic == f"openeo/{device_id}/command/current_limit/set":
                self._handle_current_limit_command(payload)
            elif topic == f"openeo/{device_id}/command/enable_plugin/set":
                self._handle_enable_plugin_command(payload)
            elif topic.startswith(f"openeo/{device_id}/command/schedule/"):
                self._handle_indexed_schedule_command(topic, payload, solar=False)
            elif topic.startswith(f"openeo/{device_id}/command/solar_schedule/"):
                self._handle_indexed_schedule_command(topic, payload, solar=True)
            elif topic == f"openeo/{device_id}/command/solar_enable/set":
                enabled = payload.lower() in ["on", "true", "1"]
                globalState.configDB.set("loadmanagement", "solar_enable", enabled)
                self._publish_state()
            elif topic == f"openeo/{device_id}/command/ha_rate_enabled/set":
                enabled = payload.lower() in ["on", "true", "1"]
                globalState.configDB.set("chargersession", "ha_rate_enabled", enabled)
                self._publish_state()
            else:
                _LOGGER.warning(f"Unknown command topic: {topic}")
                
        except Exception as e:
            _LOGGER.error(f"Error processing MQTT command: {e}")
    
    @staticmethod
    def _tariff_log(level, message):
        """Log to the journal and to System Logs (App Events)."""
        _LOGGER.log(level, message)
        try:
            globalState.configDB.logwrite(message)
        except Exception as e:
            _LOGGER.debug(f"Could not write tariff message to app events: {e}")

    def _handle_switch_command(self, payload):
        """Handle switch on/off commands"""
        try:
            # Parse command - expect "ON" or "OFF"
            switch_on = payload.upper() in ["ON", "TRUE", "1"]
            
            # Enable switch plugin and set state
            globalState.configDB.set("switch", "enabled", True)
            globalState.configDB.set("switch", "on", switch_on)

            _LOGGER.info(f"Switch command executed: {switch_on}")
            self._publish_state()

        except Exception as e:
            _LOGGER.error(f"Error handling switch command '{payload}': {e}")
    
    def _handle_current_limit_command(self, payload):
        """Handle current limit commands"""
        try:
            # Parse and validate current value using global constants
            current_limit = int(float(payload))
            
            # Also respect the user-configured overall limit
            max_allowed = min(globalState.MAX_CHARGING_CURRENT, 
                            globalState.stateDict.get("eo_overall_limit_current", globalState.MAX_CHARGING_CURRENT))
            
            if not globalState.MIN_CHARGING_CURRENT <= current_limit <= max_allowed:
                _LOGGER.error(f"Invalid current limit: {current_limit}. Must be {globalState.MIN_CHARGING_CURRENT}-{max_allowed} amps")
                return
            
            # Set current limit for switch plugin
            globalState.configDB.set("switch", "amps", current_limit)
            globalState.configDB.set("switch", "enabled", True)

            _LOGGER.info(f"Current limit set to {current_limit}A")
            
        except (ValueError, TypeError) as e:
            _LOGGER.error(f"Invalid current limit value '{payload}': {e}")
        except Exception as e:
            _LOGGER.error(f"Error handling current limit command '{payload}': {e}")
    
    
    def _handle_enable_plugin_command(self, payload):
        """Handle plugin enable/disable commands"""
        try:
            # Expected format: "plugin_name:enabled" e.g. "scheduler:true"
            if ":" not in payload:
                _LOGGER.error(f"Invalid plugin command format '{payload}'. Expected 'plugin:true/false'")
                return
                
            plugin_name, enabled_str = payload.split(":", 1)
            enabled = enabled_str.lower() in ["true", "on", "1", "enabled"]
            
            # Validate plugin name (basic security)
            valid_plugins = ["scheduler", "switch", "loadmanagement"]
            if plugin_name not in valid_plugins:
                _LOGGER.error(f"Plugin '{plugin_name}' not allowed for remote control")
                return
            
            globalState.configDB.set(plugin_name, "enabled", enabled)
            _LOGGER.info(f"Plugin '{plugin_name}' {'enabled' if enabled else 'disabled'}")
            self._publish_state()

        except Exception as e:
            _LOGGER.error(f"Error handling plugin command '{payload}': {e}")
    
    def _get_schedules(self):
        """Return live schedule list from scheduler plugin"""
        module = globalState.stateDict["_moduleDict"].get("scheduler")
        return (module.get_config("schedule") or []) if module else []

    def _get_solar_schedules(self):
        """Return live schedule list from loadmanagement plugin"""
        module = globalState.stateDict["_moduleDict"].get("loadmanagement")
        return (module.get_config("schedule") or []) if module else []

    def _handle_indexed_schedule_command(self, topic, payload, solar):
        """Handle add/edit/delete commands for indexed charging or solar schedule slots"""
        try:
            device_id = self.get_config("device_id")
            prefix = "solar_schedule" if solar else "schedule"
            base = f"openeo/{device_id}/command/{prefix}/"
            parts = topic[len(base):].split("/")

            schedules = self._get_solar_schedules() if solar else self._get_schedules()
            plugin = "loadmanagement" if solar else "scheduler"
            default = {"start": "0000", "end": "2359", "amps": 0} if solar \
                      else {"start": "2200", "end": "0600", "amps": 16}
            max_allowed = min(globalState.MAX_CHARGING_CURRENT,
                              globalState.stateDict.get("eo_overall_limit_current", globalState.MAX_CHARGING_CURRENT))

            if parts == ["add"]:
                if solar and not self._bool_config("loadmanagement", "solar_enable"):
                    _LOGGER.warning("Cannot add solar schedule: solar charging is disabled")
                    return
                schedules.append(dict(default))
                globalState.configDB.set(plugin, "schedule", json.dumps(schedules))
                self.discovery_sent = False
                self._publish_state()
                _LOGGER.info(f"Added new {prefix} (total: {len(schedules)})")

            elif len(parts) == 2 and parts[1] == "delete":
                if not parts[0].isdigit():
                    _LOGGER.error(f"Invalid schedule index '{parts[0]}'")
                    return
                n = int(parts[0])
                if not (1 <= n <= len(schedules)):
                    _LOGGER.error(f"Schedule index {n} out of range (1..{len(schedules)})")
                    return
                if len(schedules) == 1:
                    schedules[0] = dict(default)
                else:
                    del schedules[n - 1]
                globalState.configDB.set(plugin, "schedule", json.dumps(schedules))
                self.discovery_sent = False
                self._publish_state()
                _LOGGER.info(f"Deleted {prefix} {n}")

            elif len(parts) == 3 and parts[2] == "set" and parts[1] in ("start", "end"):
                if not parts[0].isdigit():
                    _LOGGER.error(f"Invalid schedule index '{parts[0]}'")
                    return
                n = int(parts[0])
                if not (1 <= n <= len(schedules)):
                    _LOGGER.error(f"Schedule index {n} out of range (1..{len(schedules)})")
                    return
                value = self._normalize_time(payload)
                if value is None:
                    return
                schedules[n - 1][parts[1]] = value
                globalState.configDB.set(plugin, "schedule", json.dumps(schedules))
                self._publish_state()
                _LOGGER.info(f"Set {prefix} {n} {parts[1]} to {value}")

            elif len(parts) == 3 and parts[2] == "set" and parts[1] == "amps":
                if not parts[0].isdigit():
                    _LOGGER.error(f"Invalid schedule index '{parts[0]}'")
                    return
                n = int(parts[0])
                if not (1 <= n <= len(schedules)):
                    _LOGGER.error(f"Schedule index {n} out of range (1..{len(schedules)})")
                    return
                try:
                    amps = int(float(payload))
                except (ValueError, TypeError):
                    _LOGGER.error(f"Invalid amps value '{payload}'")
                    return
                min_amps = 0 if solar else globalState.MIN_CHARGING_CURRENT
                if not (min_amps <= amps <= max_allowed):
                    _LOGGER.error(f"Amps {amps} out of range ({min_amps}..{max_allowed})")
                    return
                schedules[n - 1]["amps"] = amps
                globalState.configDB.set(plugin, "schedule", json.dumps(schedules))
                self._publish_state()
                _LOGGER.info(f"Set {prefix} {n} amps to {amps}")

            else:
                _LOGGER.warning(f"Unrecognised schedule command topic: {topic}")

        except Exception as e:
            _LOGGER.error(f"Error handling schedule command '{topic}': {e}")
    
    def _normalize_time(self, time_str):
        """Convert time to HHMM format with basic validation"""
        time_str = time_str.strip()
        # HA time entities send HH:MM:SS — drop the seconds component
        if len(time_str) == 8 and time_str[2] == ':' and time_str[5] == ':':
            time_str = time_str[:5]
        time_str = time_str.replace(':', '')

        if len(time_str) == 4 and time_str.isdigit():
            hour, minute = int(time_str[:2]), int(time_str[2:])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time_str

        _LOGGER.error(f"Invalid time format '{time_str}'. Expected HH:MM:SS, HH:MM or HHMM")
        return None
    
    def _get_availability_topic(self):
        device_id = self.get_config("device_id")
        return f"openeo/{device_id}/availability"

    def _bool_config(self, module, key, default=False):
        val = globalState.configDB.get(module, key, default)
        return val in (True, "True", "true", "1", 1)

    def _get_device_info(self):
        """Generate device information for Home Assistant"""
        return {
            "identifiers": [self.get_config("device_id")],
            "name": self.get_config("device_name"),
            "manufacturer": "OpenEO",
            "model": "EV Charger Controller",
            "sw_version": globalState.stateDict.get("app_version", "unknown")
        }


    
    def _send_discovery(self):
        """Send Home Assistant auto-discovery messages"""
        if not self.connected:
            return
        
        device_info = self._get_device_info()
        discovery_prefix = self.get_config("mqtt_discovery_prefix")
        device_id = self.get_config("device_id")
        availability_topic = self._get_availability_topic()
        
        # Define all sensors to create in Home Assistant
        sensors = [
            {
                "component": "sensor",
                "object_id": "charger_state",
                "name": "Charger State",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.charger_state }}",
                "icon": "mdi:ev-station"
            },
            {
                "component": "sensor", 
                "object_id": "amps_requested",
                "name": "Amps Requested",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.amps_requested }}",
                "unit_of_measurement": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "mdi:current-ac"
            },
            {
                "component": "sensor",
                "object_id": "amps_limit",
                "name": "Amps Limit",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.amps_limit }}",
                "unit_of_measurement": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "mdi:current-ac"
            },
            {
                "component": "sensor",
                "object_id": "power_delivered",
                "name": "Power Delivered", 
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.power_delivered }}",
                "unit_of_measurement": "kW",
                "device_class": "power",
                "state_class": "measurement",
                "icon": "mdi:flash"
            },
            {
                "component": "sensor",
                "object_id": "power_requested",
                "name": "Power Requested",
                "state_topic": f"openeo/{device_id}/state", 
                "value_template": "{{ value_json.power_requested }}",
                "unit_of_measurement": "kW",
                "device_class": "power",
                "state_class": "measurement",
                "icon": "mdi:flash-outline"
            },
            {
                "component": "sensor",
                "object_id": "voltage",
                "name": "Voltage",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.voltage }}",
                "unit_of_measurement": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "icon": "mdi:lightning-bolt"
            },
            {
                "component": "sensor",
                "object_id": "frequency",
                "name": "Mains Frequency",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.frequency }}",
                "unit_of_measurement": "Hz",
                "device_class": "frequency",
                "state_class": "measurement",
                "icon": "mdi:sine-wave"
            },
            {
                "component": "sensor",
                "object_id": "current_site",
                "name": "Site Current", 
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.current_site }}",
                "unit_of_measurement": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "mdi:home-lightning-bolt"
            },
            {
                "component": "sensor",
                "object_id": "current_vehicle",
                "name": "Vehicle Current",
                "state_topic": f"openeo/{device_id}/state", 
                "value_template": "{{ value_json.current_vehicle }}",
                "unit_of_measurement": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "mdi:car-electric"
            },
            {
                "component": "sensor", 
                "object_id": "current_solar",
                "name": "Solar Current",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.current_solar }}",
                "unit_of_measurement": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "mdi:solar-power"
            },
            {
                "component": "binary_sensor",
                "object_id": "vehicle_connected",
                "name": "Vehicle Connected",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.vehicle_connected }}",
                "payload_on": "true",
                "payload_off": "false",
                "device_class": "connectivity",
                "icon": "mdi:car-connected"
            },
            {
                "component": "binary_sensor",
                "object_id": "cable_connected",
                "name": "Cable Connected",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.cable_connected }}",
                "payload_on": "true",
                "payload_off": "false",
                "device_class": "connectivity",
                "icon": "mdi:car-connected"
            },
            {
                "component": "binary_sensor",
                "object_id": "charging_active", 
                "name": "Charging Active",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.charging_active }}",
                "payload_on": "true",
                "payload_off": "false",
                "device_class": "battery_charging",
                "icon": "mdi:battery-charging"
            },
            {
                "component": "sensor",
                "object_id": "session_kwh",
                "name": "Session KWh", 
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.session_kwh }}",
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "state_class": "total_increasing",
                "icon": "mdi:home-lightning-bolt"
            },
            {
                "component": "sensor",
                "object_id": "session_cost",
                "name": "Session Cost", 
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.session_cost | round(2)}}",
                "unit_of_measurement": "GBP",
                "device_class": "monetary",
                "state_class": "total",
                "last_reset_value_template": "{{ value_json.session_cost_reset }}",
                "icon": "mdi:currency-gbp"
            },
            {
                "component": "sensor",
                "object_id": "current_rate",
                "name": "Current Rate",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.current_rate }}",
                "unit_of_measurement": "GBP/kWh",
                "state_class": "measurement",
                "icon": "mdi:cash"
            },
            {
                "component": "sensor",
                "object_id": "rate_source",
                "name": "Rate Source",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.rate_source }}",
                "icon": "mdi:swap-horizontal",
                "json_attributes_topic": f"openeo/{device_id}/state",
                "json_attributes_template": "{{ {'reason': value_json.rate_reason} | tojson }}"
            },
            {
                "component": "sensor",
                "object_id": "ha_rate_received",
                "name": "HA Rate Received",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.ha_rate_received }}",
                "unit_of_measurement": "GBP/kWh",
                "state_class": "measurement",
                "icon": "mdi:cash-check",
                "json_attributes_topic": f"openeo/{device_id}/state",
                "json_attributes_template": "{{ {'received_at': value_json.ha_rate_received_at} | tojson }}"
            },
        ]
        
        # Get dynamic current limits
        max_allowed_current = min(globalState.MAX_CHARGING_CURRENT, 
                                globalState.stateDict.get("eo_overall_limit_current", globalState.MAX_CHARGING_CURRENT))
        
        # Define control entities for Home Assistant
        control_entities = [
            {
                "component": "switch",
                "object_id": "charging",
                "name": "Charging",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/switch/set",
                "value_template": "{{ 'ON' if (value_json.switch_enabled and value_json.switch_on) else 'OFF' }}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:ev-station",
                "device_class": "switch"
            },
            {
                "component": "number",
                "object_id": "current_limit",
                "name": "Current Limit",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/current_limit/set",
                "value_template": "{{ value_json.current_limit_setting }}",
                "min": globalState.MIN_CHARGING_CURRENT,
                "max": max_allowed_current,
                "step": 1,
                "unit_of_measurement": "A",
                "device_class": "current",
                "icon": "mdi:current-ac"
            },
            {
                "component": "switch",
                "object_id": "timers_switch",
                "name": "Timers",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/enable_plugin/set",
                "value_template": "{{ 'ON' if value_json.scheduler_enabled else 'OFF' }}",
                "payload_on": "scheduler:true",
                "payload_off": "scheduler:false",
                "state_on": "ON",
                "state_off": "OFF",
                "icon": "mdi:timer",
                "device_class": "switch"
            },
        ]
        
        # Build dynamic entities for each charging schedule slot
        schedules = self._get_schedules()
        schedule_entities = []
        for n, _ in enumerate(schedules, 1):
            schedule_entities += [
                {
                    "component": "time",
                    "object_id": f"schedule_{n}_start",
                    "name": f"Charge Schedule {n} Start",
                    "state_topic": f"openeo/{device_id}/state",
                    "command_topic": f"openeo/{device_id}/command/schedule/{n}/start/set",
                    "value_template": (
                        f"{{{{ value_json.charging_schedule_{n}_start[:2] + ':' + "
                        f"value_json.charging_schedule_{n}_start[2:] "
                        f"if value_json.get('charging_schedule_{n}_start') else '22:00' }}}}"
                    ),
                    "icon": "mdi:clock-start"
                },
                {
                    "component": "time",
                    "object_id": f"schedule_{n}_end",
                    "name": f"Charge Schedule {n} End",
                    "state_topic": f"openeo/{device_id}/state",
                    "command_topic": f"openeo/{device_id}/command/schedule/{n}/end/set",
                    "value_template": (
                        f"{{{{ value_json.charging_schedule_{n}_end[:2] + ':' + "
                        f"value_json.charging_schedule_{n}_end[2:] "
                        f"if value_json.get('charging_schedule_{n}_end') else '06:00' }}}}"
                    ),
                    "icon": "mdi:clock-end"
                },
                {
                    "component": "number",
                    "object_id": f"schedule_{n}_amps",
                    "name": f"Charge Schedule {n} Current",
                    "state_topic": f"openeo/{device_id}/state",
                    "command_topic": f"openeo/{device_id}/command/schedule/{n}/amps/set",
                    "value_template": f"{{{{ value_json.get('charging_schedule_{n}_amps', {globalState.MIN_CHARGING_CURRENT}) }}}}",
                    "min": globalState.MIN_CHARGING_CURRENT,
                    "max": max_allowed_current,
                    "step": 1,
                    "unit_of_measurement": "A",
                    "device_class": "current",
                    "icon": "mdi:current-ac"
                },
                {
                    "component": "button",
                    "object_id": f"schedule_{n}_delete",
                    "name": f"Delete Charge Schedule {n}",
                    "command_topic": f"openeo/{device_id}/command/schedule/{n}/delete",
                    "payload_press": "delete",
                    "icon": "mdi:delete"
                },
            ]
        schedule_entities.append({
            "component": "button",
            "object_id": "schedule_add",
            "name": "Add Charge Schedule",
            "command_topic": f"openeo/{device_id}/command/schedule/add",
            "payload_press": "add",
            "icon": "mdi:plus-circle",
            "availability": [
                {"topic": availability_topic},
                {
                    "topic": f"openeo/{device_id}/state",
                    "value_template": "{{ 'online' if value_json.scheduler_enabled else 'offline' }}"
                }
            ],
            "availability_mode": "all"
        })

        # Build dynamic entities for each solar schedule slot
        solar_schedules = self._get_solar_schedules()
        solar_schedule_entities = []
        solar_availability = [
            {"topic": availability_topic},
            {
                "topic": f"openeo/{device_id}/state",
                "value_template": "{{ 'online' if value_json.solar_enabled else 'offline' }}"
            }
        ]
        for n, _ in enumerate(solar_schedules, 1):
            solar_schedule_entities += [
                {
                    "component": "time",
                    "object_id": f"solar_schedule_{n}_start",
                    "name": f"Solar Schedule {n} Start",
                    "state_topic": f"openeo/{device_id}/state",
                    "command_topic": f"openeo/{device_id}/command/solar_schedule/{n}/start/set",
                    "value_template": (
                        f"{{{{ value_json.solar_schedule_{n}_start[:2] + ':' + "
                        f"value_json.solar_schedule_{n}_start[2:] "
                        f"if value_json.get('solar_schedule_{n}_start') else '00:00' }}}}"
                    ),
                    "icon": "mdi:weather-sunny-clock",
                    "availability": solar_availability,
                    "availability_mode": "all"
                },
                {
                    "component": "time",
                    "object_id": f"solar_schedule_{n}_end",
                    "name": f"Solar Schedule {n} End",
                    "state_topic": f"openeo/{device_id}/state",
                    "command_topic": f"openeo/{device_id}/command/solar_schedule/{n}/end/set",
                    "value_template": (
                        f"{{{{ value_json.solar_schedule_{n}_end[:2] + ':' + "
                        f"value_json.solar_schedule_{n}_end[2:] "
                        f"if value_json.get('solar_schedule_{n}_end') else '23:59' }}}}"
                    ),
                    "icon": "mdi:weather-sunny-off",
                    "availability": solar_availability,
                    "availability_mode": "all"
                },
                {
                    "component": "number",
                    "object_id": f"solar_schedule_{n}_amps",
                    "name": f"Solar Schedule {n} Reservation",
                    "state_topic": f"openeo/{device_id}/state",
                    "command_topic": f"openeo/{device_id}/command/solar_schedule/{n}/amps/set",
                    "value_template": f"{{{{ value_json.get('solar_schedule_{n}_amps', 0) }}}}",
                    "min": 0,
                    "max": 8,
                    "step": 1,
                    "unit_of_measurement": "A",
                    "device_class": "current",
                    "icon": "mdi:solar-power",
                    "availability": solar_availability,
                    "availability_mode": "all"
                },
                {
                    "component": "button",
                    "object_id": f"solar_schedule_{n}_delete",
                    "name": f"Delete Solar Schedule {n}",
                    "command_topic": f"openeo/{device_id}/command/solar_schedule/{n}/delete",
                    "payload_press": "delete",
                    "icon": "mdi:delete",
                    "availability": solar_availability,
                    "availability_mode": "all"
                },
            ]
        solar_schedule_entities += [
            {
                "component": "switch",
                "object_id": "solar_enabled",
                "name": "Solar Charging",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/solar_enable/set",
                "value_template": "{{ 'ON' if value_json.solar_enabled else 'OFF' }}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "icon": "mdi:solar-power-variant",
                "device_class": "switch"
            },
            {
                "component": "switch",
                "object_id": "ha_rate_enabled",
                "name": "Use Live Rate",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/ha_rate_enabled/set",
                "value_template": "{{ 'ON' if value_json.ha_rate_enabled else 'OFF' }}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "icon": "mdi:cash-sync",
                "device_class": "switch"
            },
            {
                "component": "button",
                "object_id": "solar_schedule_add",
                "name": "Add Solar Schedule",
                "command_topic": f"openeo/{device_id}/command/solar_schedule/add",
                "payload_press": "add",
                "icon": "mdi:plus-circle",
                "availability": [
                    {"topic": availability_topic},
                    {
                        "topic": f"openeo/{device_id}/state",
                        "value_template": "{{ 'online' if value_json.solar_enabled else 'offline' }}"
                    }
                ],
                "availability_mode": "all"
            },
        ]

        sensors += wifi_status.ha_entities(f"openeo/{device_id}/state")

        # Combine sensors and control entities for discovery
        all_entities = sensors + control_entities + schedule_entities + solar_schedule_entities
        
        # Send discovery message for each entity
        for entity in all_entities:
            config = {
                "name": entity["name"],
                "unique_id": f"{device_id}_{entity['object_id']}",
                "device": device_info
            }
            if "state_topic" in entity:
                config["state_topic"] = entity["state_topic"]

            # Add optional fields if present
            for field in ["value_template", "unit_of_measurement", "device_class", "state_class",
                         "last_reset_value_template", "icon", "payload_on", "payload_off", "payload_press", "state_on", "state_off",
                         "command_topic", "min", "max", "step", "options",
                         "json_attributes_topic", "json_attributes_template"]:
                if field in entity:
                    config[field] = entity[field]

            config["availability"] = entity.get("availability", [{"topic": availability_topic}])
            if "availability_mode" in entity:
                config["availability_mode"] = entity["availability_mode"]

            topic = f"{discovery_prefix}/{entity['component']}/{device_id}/{entity['object_id']}/config"
            payload = json.dumps(config)
            
            try:
                self.mqtt_client.publish(topic, payload, retain=True)
                _LOGGER.debug(f"Published discovery for {entity['name']}")
            except Exception as e:
                _LOGGER.error(f"Failed to publish discovery for {entity['name']}: {e}")
        
        # Remove retired slot entities for any schedule slots that no longer exist
        new_count = len(schedules)
        new_solar_count = len(solar_schedules)
        slot_sub_entities = ["start", "end", "amps", "delete"]
        for n in range(new_count + 1, self._published_schedule_count + 1):
            for sub in slot_sub_entities:
                stale = f"{discovery_prefix}/{'button' if sub == 'delete' else ('time' if sub in ('start','end') else 'number')}/{device_id}/schedule_{n}_{sub}/config"
                try:
                    self.mqtt_client.publish(stale, "", retain=True)
                    _LOGGER.debug(f"Cleared stale discovery topic: {stale}")
                except Exception as e:
                    _LOGGER.error(f"Failed to clear stale topic {stale}: {e}")
        for n in range(new_solar_count + 1, self._published_solar_schedule_count + 1):
            for sub in slot_sub_entities:
                stale = f"{discovery_prefix}/{'button' if sub == 'delete' else ('time' if sub in ('start','end') else 'number')}/{device_id}/solar_schedule_{n}_{sub}/config"
                try:
                    self.mqtt_client.publish(stale, "", retain=True)
                    _LOGGER.debug(f"Cleared stale solar discovery topic: {stale}")
                except Exception as e:
                    _LOGGER.error(f"Failed to clear stale solar topic {stale}: {e}")

        # Remove renamed/deprecated entities by publishing empty retained payloads
        deprecated_topics = [
            f"{discovery_prefix}/switch/{device_id}/charger_switch/config",
            f"{discovery_prefix}/select/{device_id}/charger_mode/config",
            f"{discovery_prefix}/time/{device_id}/schedule_start/config",
            f"{discovery_prefix}/time/{device_id}/schedule_end/config",
            f"{discovery_prefix}/number/{device_id}/schedule_amps/config",
        ]
        for topic in deprecated_topics:
            try:
                self.mqtt_client.publish(topic, "", retain=True)
                _LOGGER.debug(f"Removed deprecated discovery topic: {topic}")
            except Exception as e:
                _LOGGER.error(f"Failed to remove deprecated discovery topic {topic}: {e}")

        self._published_schedule_count = new_count
        self._published_solar_schedule_count = new_solar_count
        self.discovery_sent = True
        _LOGGER.info("Home Assistant discovery messages sent")
    
    def _publish_state(self):
        """Publish current state to MQTT"""
        if not self.connected:
            self._failed_publishes += 1  # reported in the reconnect summary
            return
        
        # Determine vehicle connection and charging status from charger state
        charger_state = globalState.stateDict.get("eo_charger_state", "")
        charger_state_id = globalState.stateDict.get("eo_charger_state_id", 0)
        
        # Vehicle is connected if state indicates plug present, car connected, or charging
        vehicle_connected = charger_state_id in [9, 10, 11, 12, 13, 14, 15, 16]  # Based on CHARGER_STATES from openeoCharger.py
        cable_connected = charger_state_id in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]  # Based on CHARGER_STATES from openeoCharger.py
        
        # Charging is active if in charging or charge-complete states
        charging_active = charger_state_id in [11, 12, 13, 14]
        
        
        ha_rate = globalState.stateDict.get("eo_ha_rate")

        state_payload = {
            "charger_state": charger_state,
            "charger_state_id": charger_state_id,
            "amps_requested": globalState.stateDict.get("eo_amps_requested", 0),
            "amps_limit": globalState.stateDict.get("eo_amps_limit", 0),
            "power_delivered": globalState.stateDict.get("eo_power_delivered", 0),
            "power_requested": globalState.stateDict.get("eo_power_requested", 0),
            "voltage": globalState.stateDict.get("eo_live_voltage", 0),
            "frequency": globalState.stateDict.get("eo_mains_frequency", 0),
            "current_site": globalState.stateDict.get("eo_current_site", 0),
            "current_vehicle": globalState.stateDict.get("eo_current_vehicle", 0),
            "current_solar": globalState.stateDict.get("eo_current_solar", 0),
            "vehicle_connected": "true" if vehicle_connected else "false",
            "cable_connected": "true" if cable_connected else "false",
            "charging_active": "true" if charging_active else "false",
            "switch_on": self._bool_config("switch", "on"),
            "switch_enabled": self._bool_config("switch", "enabled"),
            "scheduler_enabled": self._bool_config("scheduler", "enabled"),
            "current_limit_setting": globalState.configDB.get("switch", "amps", globalState.MIN_CHARGING_CURRENT),
            "solar_enabled": self._bool_config("loadmanagement", "solar_enable"),
            "serial_errors": globalState.stateDict.get("eo_serial_errors", 0),
            "app_version": globalState.stateDict.get("app_version", "unknown"),
            "openeo_latest_version": globalState.stateDict.get("openeo_latest_version", "unknown"),
            "session_kwh":globalState.stateDict.get("eo_session_kwh", 0.0),
            "session_cost":globalState.stateDict.get("eo_session_cost", 0.0),
            "session_cost_reset":globalState.stateDict.get("eo_session_cost_reset"),
            "current_rate":globalState.stateDict.get("eo_session_current_tariff", 0.0),
            "rate_source":globalState.stateDict.get("eo_tariff_rate_source", "schedule"),
            "rate_reason":globalState.stateDict.get("eo_tariff_rate_reason", ""),
            "ha_rate_enabled": self._bool_config("chargersession", "ha_rate_enabled"),
            "ha_rate_received": ha_rate.get("value") if ha_rate else None,
            "ha_rate_received_at": (datetime.datetime.fromtimestamp(ha_rate["received_at"]).astimezone().isoformat(timespec="seconds")
                                    if ha_rate and ha_rate.get("received_at") is not None else None),
            "timestamp": int(time.time())
        }
        
        for n, s in enumerate(self._get_schedules(), 1):
            state_payload[f"charging_schedule_{n}_start"] = s.get("start", "2200")
            state_payload[f"charging_schedule_{n}_end"] = s.get("end", "0600")
            state_payload[f"charging_schedule_{n}_amps"] = s.get("amps", globalState.MIN_CHARGING_CURRENT)

        for n, s in enumerate(self._get_solar_schedules(), 1):
            state_payload[f"solar_schedule_{n}_start"] = s.get("start", "0000")
            state_payload[f"solar_schedule_{n}_end"] = s.get("end", "2359")
            state_payload[f"solar_schedule_{n}_amps"] = s.get("amps", 0)

        state_payload.update(wifi_status.ha_payload(globalState.stateDict))

        device_id = self.get_config("device_id")
        topic = f"openeo/{device_id}/state"
        payload = json.dumps(state_payload)
        
        try:
            info = self.mqtt_client.publish(topic, payload, retain=True)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                # Not logged one by one; reported in the reconnect summary.
                self._failed_publishes += 1
            _LOGGER.debug("Published state to MQTT")
        except Exception as e:
            _LOGGER.error(f"Failed to publish state: {e}")
    
    def poll(self):
        """Called by main loop - publish state at configured interval"""
        if not MQTT_AVAILABLE or not self.get_config("enabled"):
            return 0
        
        current_time = time.time()
        publish_interval = self.get_config("publish_interval")
        
        # Detect schedule count changes from native UI and trigger re-discovery
        if self.connected and self.discovery_sent:
            if (len(self._get_schedules()) != self._published_schedule_count or
                    len(self._get_solar_schedules()) != self._published_solar_schedule_count):
                self.discovery_sent = False

        # Send discovery messages if not sent yet and connected
        if self.connected and not self.discovery_sent:
            threading.Thread(target=self._send_discovery, daemon=True).start()
        
        # Publish state at configured interval
        if current_time - self.last_publish >= publish_interval:
            self._publish_state()
            self.last_publish = current_time
        
        # Return 0 - this plugin doesn't control charging
        return 0
    
    def get_user_settings(self):
        return [{"type": "textinput", "name": "mqtt_host", "label": "MQTT Broker Host", "default":self.pluginConfig.get("mqtt_host",""), "note":"Hostname or IP address of the MQTT broker that Home Assistant is connected to, for example the Mosquitto add-on on your Home Assistant server."},
                {"type": "textinput", "name": "mqtt_port", "label": "MQTT Broker Port", "default":self.pluginConfig.get("mqtt_port",""), "note":"The port the broker accepts MQTT connections on, normally 1883. Encrypted (TLS) connections, usually on port 8883, are not supported."},
                {"type": "textinput", "name": "mqtt_username",  "default":self.pluginConfig.get("mqtt_username",""), "label": "MQTT Username (optional)", "note":"Username for the MQTT broker. Leave blank if your broker accepts connections without a login. With the Home Assistant Mosquitto add-on, use a Home Assistant user or a login set in the add-on's configuration."},
                {"type": "textinput", "name": "mqtt_password",  "default":self.pluginConfig.get("mqtt_password",""), "label": "MQTT Password (optional)", "note":"Password for the MQTT username above. Leave blank if you have not set a username."},
                {"type": "textinput", "name": "mqtt_discovery_prefix", "label": "HA Discovery Prefix", "default":self.pluginConfig.get("mqtt_discovery_prefix",""), "note":"The MQTT topic prefix Home Assistant watches to discover new devices. Leave this as homeassistant unless you have changed the discovery prefix in Home Assistant's MQTT integration."},
                {"type": "textinput", "name": "device_name", "label": "Device Name in HA", "default":self.pluginConfig.get("device_name",""), "note":"The name Home Assistant shows for this charger. Home Assistant also uses it to name the charger's entities when they are first created. Renaming it later does not change existing entity IDs."},
                {"type": "textinput", "name": "device_id", "label": "Device ID", "default":self.pluginConfig.get("device_id",""), "pattern":'([A-Za-z0-9_])+', "note":"Identifies this charger in its MQTT topics and to Home Assistant. Each charger connected to the same broker needs a different Device ID. Letters, numbers and underscores only. Changing it creates a new device in Home Assistant."},
                {"type": "slider", "name": "publish_interval", "label": "Publish Interval (seconds)",  "default":self.pluginConfig.get("publish_interval","300"), "range": [5,3600], "step":5, "value_unit":"s", "note":"How often the charger's status (charging state, current, power and energy) is sent to Home Assistant. A shorter interval keeps Home Assistant more up to date but sends more MQTT messages."}
                ];

    
    def __del__(self):
        """Cleanup MQTT connection on plugin destruction"""
        if self.mqtt_client and self.connected:
            try:
                self.mqtt_client.publish(
                    self._get_availability_topic(),
                    payload="offline",
                    qos=1,
                    retain=True,
                )
            except Exception:
                pass
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()