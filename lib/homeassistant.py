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

import logging
import json
import time
import threading
from lib.PluginSuperClass import PluginSuperClass
import globalState
import util

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.getLogger(__name__).warning("paho-mqtt not available - Home Assistant integration disabled")

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

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
        super().__init__(configParam)
        
        if not MQTT_AVAILABLE:
            _LOGGER.error("paho-mqtt library not available - install with: pip install paho-mqtt")
            return
            
        if self.get_config("enabled"):
            self._setup_mqtt()
    
    def _setup_mqtt(self):
        """Initialize MQTT client and connect to broker"""
        try:
            self.mqtt_client = mqtt.Client()
            
            # Set authentication if provided
            username = self.get_config("mqtt_username")
            password = self.get_config("mqtt_password")
            if username:
                self.mqtt_client.username_pw_set(username, password)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
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
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            self.connected = True
            _LOGGER.info("Connected to MQTT broker")
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
        else:
            _LOGGER.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        self.connected = False
        self.discovery_sent = False
        if rc != 0:
            _LOGGER.warning("Unexpected MQTT disconnection")
        else:
            _LOGGER.info("Disconnected from MQTT broker")
    
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
            else:
                _LOGGER.warning(f"Unknown command topic: {topic}")
                
        except Exception as e:
            _LOGGER.error(f"Error processing MQTT command: {e}")
    
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
                "state_class": "total_increasing",
                "icon": "mdi:currency-gbp"
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
                    "icon": "mdi:weather-sunny-clock"
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
                    "icon": "mdi:weather-sunny-off"
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
                    "icon": "mdi:solar-power"
                },
                {
                    "component": "button",
                    "object_id": f"solar_schedule_{n}_delete",
                    "name": f"Delete Solar Schedule {n}",
                    "command_topic": f"openeo/{device_id}/command/solar_schedule/{n}/delete",
                    "payload_press": "delete",
                    "icon": "mdi:delete"
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
                         "icon", "payload_on", "payload_off", "payload_press", "state_on", "state_off",
                         "command_topic", "min", "max", "step", "options"]:
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
            return
        
        # Determine vehicle connection and charging status from charger state
        charger_state = globalState.stateDict.get("eo_charger_state", "")
        charger_state_id = globalState.stateDict.get("eo_charger_state_id", 0)
        
        # Vehicle is connected if state indicates plug present, car connected, or charging
        vehicle_connected = charger_state_id in [9, 10, 11, 12, 13, 14, 15, 16]  # Based on CHARGER_STATES from openeoCharger.py
        cable_connected = charger_state_id in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]  # Based on CHARGER_STATES from openeoCharger.py
        
        # Charging is active if in charging or charge-complete states
        charging_active = charger_state_id in [11, 12, 13, 14]
        
        
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

        device_id = self.get_config("device_id")
        topic = f"openeo/{device_id}/state"
        payload = json.dumps(state_payload)
        
        try:
            self.mqtt_client.publish(topic, payload, retain=True)
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
        return [{"type": "textinput", "name": "mqtt_host", "label": "MQTT Broker Host", "default":self.pluginConfig.get("mqtt_host",""), "note":"MQTT Broker Host."},
                {"type": "textinput", "name": "mqtt_port", "label": "MQTT Broker Port", "default":self.pluginConfig.get("mqtt_port",""), "note":"MQTT Broker Port."},
                {"type": "textinput", "name": "mqtt_username",  "default":self.pluginConfig.get("mqtt_username",""), "label": "MQTT Username (optional)"},
                {"type": "textinput", "name": "mqtt_password",  "default":self.pluginConfig.get("mqtt_password",""), "label": "MQTT Password (optional)"},
                {"type": "textinput", "name": "mqtt_discovery_prefix", "label": "HA Discovery Prefix", "default":self.pluginConfig.get("mqtt_discovery_prefix","")},
                {"type": "textinput", "name": "device_name", "label": "Device Name in HA", "default":self.pluginConfig.get("device_name","")},
                {"type": "textinput", "name": "device_id", "label": "Device ID", "default":self.pluginConfig.get("device_id","")},
                {"type": "slider", "name": "publish_interval", "label": "Publish Interval (seconds)",  "default":self.pluginConfig.get("publish_interval","300"), "range": [5,3600], "step":5, "value_unit":"s"}
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