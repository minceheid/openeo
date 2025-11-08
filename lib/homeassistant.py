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
            f"openeo/{device_id}/command/mode/set",
            f"openeo/{device_id}/command/enable_plugin/set",
            f"openeo/{device_id}/command/schedule_start/set",
            f"openeo/{device_id}/command/schedule_end/set",
            f"openeo/{device_id}/command/schedule_amps/set"
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
            elif topic == f"openeo/{device_id}/command/mode/set":
                self._handle_mode_command(payload)
            elif topic == f"openeo/{device_id}/command/enable_plugin/set":
                self._handle_enable_plugin_command(payload)
            elif topic == f"openeo/{device_id}/command/schedule_start/set":
                self._handle_schedule_start_command(payload)
            elif topic == f"openeo/{device_id}/command/schedule_end/set":
                self._handle_schedule_end_command(payload)
            elif topic == f"openeo/{device_id}/command/schedule_amps/set":
                self._handle_schedule_amps_command(payload)
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
            
            # Disable scheduler when manually controlling
            globalState.configDB.set("scheduler", "enabled", False)
            
            _LOGGER.info(f"Switch command executed: {switch_on}")
            
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
            
            # Disable scheduler when manually controlling
            globalState.configDB.set("scheduler", "enabled", False)
            
            _LOGGER.info(f"Current limit set to {current_limit}A")
            
        except (ValueError, TypeError) as e:
            _LOGGER.error(f"Invalid current limit value '{payload}': {e}")
        except Exception as e:
            _LOGGER.error(f"Error handling current limit command '{payload}': {e}")
    
    def _handle_mode_command(self, payload):
        """Handle mode change commands using existing plugin system"""
        try:
            mode = payload.lower()
            
            # Use existing plugin configuration system
            if mode == "manual":
                globalState.configDB.set("switch", "enabled", True)
                globalState.configDB.set("scheduler", "enabled", False)
                _LOGGER.info("Switched to manual mode")
                
            elif mode == "schedule":
                globalState.configDB.set("scheduler", "enabled", True)
                globalState.configDB.set("switch", "enabled", False)
                _LOGGER.info("Switched to schedule mode")
                
            elif mode == "off":
                globalState.configDB.set("scheduler", "enabled", False)
                globalState.configDB.set("switch", "enabled", False)
                _LOGGER.info("All charging modes disabled")
                
            else:
                _LOGGER.error(f"Unknown mode '{mode}'. Valid modes: manual, schedule, off")
                
        except Exception as e:
            _LOGGER.error(f"Error handling mode command '{payload}': {e}")
    
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
            
        except Exception as e:
            _LOGGER.error(f"Error handling plugin command '{payload}': {e}")
    
    def _handle_schedule_start_command(self, payload):
        """Handle schedule start time command"""
        try:
            start_time = self._normalize_time(payload)
            if start_time:
                self._update_schedule_field("start", start_time)
                _LOGGER.info(f"Schedule start time set to {start_time}")
        except Exception as e:
            _LOGGER.error(f"Error handling schedule start command '{payload}': {e}")
    
    def _handle_schedule_end_command(self, payload):
        """Handle schedule end time command"""
        try:
            end_time = self._normalize_time(payload)
            if end_time:
                self._update_schedule_field("end", end_time)
                _LOGGER.info(f"Schedule end time set to {end_time}")
        except Exception as e:
            _LOGGER.error(f"Error handling schedule end command '{payload}': {e}")
    
    def _handle_schedule_amps_command(self, payload):
        """Handle schedule current limit command"""
        try:
            current_limit = int(float(payload))
            max_allowed = min(globalState.MAX_CHARGING_CURRENT, 
                            globalState.stateDict.get("eo_overall_limit_current", globalState.MAX_CHARGING_CURRENT))
            
            if globalState.MIN_CHARGING_CURRENT <= current_limit <= max_allowed:
                self._update_schedule_field("amps", current_limit)
                _LOGGER.info(f"Schedule current limit set to {current_limit}A")
            else:
                _LOGGER.error(f"Invalid schedule current limit: {current_limit}. Must be {globalState.MIN_CHARGING_CURRENT}-{max_allowed} amps")
                
        except (ValueError, TypeError):
            _LOGGER.error(f"Invalid schedule current limit value '{payload}'")
        except Exception as e:
            _LOGGER.error(f"Error handling schedule amps command '{payload}': {e}")
    
    def _normalize_time(self, time_str):
        """Convert time to HHMM format with basic validation"""
        time_str = time_str.strip().replace(':', '')
        
        if len(time_str) == 4 and time_str.isdigit():
            hour, minute = int(time_str[:2]), int(time_str[2:])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time_str
        
        _LOGGER.error(f"Invalid time format '{time_str}'. Expected HH:MM or HHMM")
        return None
    
    def _update_schedule_field(self, field, value):
        """Update schedule field using existing plugin system"""
        scheduler_module = globalState.stateDict["_moduleDict"].get("scheduler")
        if not scheduler_module:
            _LOGGER.error("Scheduler module not available")
            return
        
        # Get current schedule from plugin (already parsed)
        current_schedule = scheduler_module.get_config("schedule") or []
        
        # Ensure we have at least one schedule entry
        if not current_schedule:
            current_schedule = [{"start": "2200", "end": "0600", "amps": globalState.MIN_CHARGING_CURRENT}]
        
        # Update the field
        current_schedule[0][field] = value
        
        # Save using config system (will trigger plugin reconfiguration)
        globalState.configDB.set("scheduler", "schedule", current_schedule)
        globalState.configDB.set("scheduler", "enabled", True)
    
    def _get_current_limit_setting(self):
        """Get the configured current limit based on current mode"""
        current_mode = self._get_current_mode()
        
        if current_mode == "manual":
            # Use switch plugin's configured amps - already type-converted by plugin system
            switch_module = globalState.stateDict["_moduleDict"].get("switch")
            if switch_module:
                return max(globalState.MIN_CHARGING_CURRENT, switch_module.get_config("amps"))
                
        elif current_mode == "schedule":
            # Use scheduler plugin's configured amps - already type-converted by plugin system  
            scheduler_module = globalState.stateDict["_moduleDict"].get("scheduler")
            if scheduler_module:
                schedule = scheduler_module.get_config("schedule")
                if schedule and len(schedule) > 0:
                    return max(globalState.MIN_CHARGING_CURRENT, schedule[0].get("amps", globalState.MIN_CHARGING_CURRENT))
        
        # Safe fallback
        return globalState.MIN_CHARGING_CURRENT
    
    def _get_schedule_field(self, field):
        """Get schedule field using plugin system"""
        scheduler_module = globalState.stateDict["_moduleDict"].get("scheduler")
        if scheduler_module:
            schedule = scheduler_module.get_config("schedule") or []
            if schedule:
                return schedule[0].get(field, self._get_schedule_default(field))
        
        return self._get_schedule_default(field)
    
    def _get_schedule_default(self, field):
        """Get default value for schedule field"""
        defaults = {
            "start": "2200",
            "end": "0600", 
            "amps": globalState.MIN_CHARGING_CURRENT
        }
        return defaults.get(field, "")
    
    def _get_current_mode(self):
        """Helper method to determine current operating mode"""
        switch_enabled = globalState.configDB.get("switch", "enabled", False)
        scheduler_enabled = globalState.configDB.get("scheduler", "enabled", False)
        
        if switch_enabled and not scheduler_enabled:
            return "manual"
        elif scheduler_enabled and not switch_enabled:
            return "schedule"
        else:
            return "off"
    
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
                "object_id": "charging_active", 
                "name": "Charging Active",
                "state_topic": f"openeo/{device_id}/state",
                "value_template": "{{ value_json.charging_active }}",
                "payload_on": "true",
                "payload_off": "false",
                "device_class": "battery_charging",
                "icon": "mdi:battery-charging"
            }
        ]
        
        # Get dynamic current limits
        max_allowed_current = min(globalState.MAX_CHARGING_CURRENT, 
                                globalState.stateDict.get("eo_overall_limit_current", globalState.MAX_CHARGING_CURRENT))
        
        # Define control entities for Home Assistant
        control_entities = [
            {
                "component": "switch",
                "object_id": "charger_switch",
                "name": "Charger Switch",
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
                "component": "select",
                "object_id": "charger_mode",
                "name": "Charger Mode",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/mode/set",
                "value_template": "{{ 'manual' if value_json.mode == 'manual' else ('schedule' if value_json.mode == 'schedule' else 'off') }}",
                "options": ["manual", "schedule", "off"],
                "icon": "mdi:cog"
            },
            {
                "component": "time",
                "object_id": "schedule_start",
                "name": "Schedule Start Time",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/schedule_start/set",
                "value_template": "{{ value_json.schedule_start[:2] + ':' + value_json.schedule_start[2:] if value_json.schedule_start and value_json.schedule_start|length == 4 else '22:00' }}",
                "icon": "mdi:clock-start"
            },
            {
                "component": "time",
                "object_id": "schedule_end",
                "name": "Schedule End Time",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/schedule_end/set",
                "value_template": "{{ value_json.schedule_end[:2] + ':' + value_json.schedule_end[2:] if value_json.schedule_end and value_json.schedule_end|length == 4 else '06:00' }}",
                "icon": "mdi:clock-end"
            },
            {
                "component": "number",
                "object_id": "schedule_amps",
                "name": "Schedule Current Limit",
                "state_topic": f"openeo/{device_id}/state",
                "command_topic": f"openeo/{device_id}/command/schedule_amps/set",
                "value_template": "{{ value_json.schedule_amps }}",
                "min": globalState.MIN_CHARGING_CURRENT,
                "max": max_allowed_current,
                "step": 1,
                "unit_of_measurement": "A",
                "device_class": "current",
                "icon": "mdi:current-ac"
            }
        ]
        
        # Combine sensors and control entities for discovery
        all_entities = sensors + control_entities
        
        # Send discovery message for each entity
        for entity in all_entities:
            config = {
                "name": entity["name"],
                "unique_id": f"{device_id}_{entity['object_id']}",
                "state_topic": entity["state_topic"],
                "device": device_info
            }
            
            # Add optional fields if present
            for field in ["value_template", "unit_of_measurement", "device_class", 
                         "icon", "payload_on", "payload_off", "command_topic", "min", "max", "step", "options"]:
                if field in entity:
                    config[field] = entity[field]
            
            topic = f"{discovery_prefix}/{entity['component']}/{device_id}/{entity['object_id']}/config"
            payload = json.dumps(config)
            
            try:
                self.mqtt_client.publish(topic, payload, retain=True)
                _LOGGER.debug(f"Published discovery for {entity['name']}")
            except Exception as e:
                _LOGGER.error(f"Failed to publish discovery for {entity['name']}: {e}")
        
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
        vehicle_connected = charger_state_id in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]  # Based on CHARGER_STATES from openeoCharger.py
        
        # Charging is active if in charging or charge-complete states
        charging_active = charger_state_id in [11, 12, 13, 14]
        
        # Determine current operating mode
        current_mode = self._get_current_mode()
        
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
            "charging_active": "true" if charging_active else "false",
            "mode": current_mode,
            "switch_on": globalState.configDB.get("switch", "on", False),
            "switch_enabled": globalState.configDB.get("switch", "enabled", False),
            "current_limit_setting": self._get_current_limit_setting(),
            "schedule_start": self._get_schedule_field("start"),
            "schedule_end": self._get_schedule_field("end"),
            "schedule_amps": self._get_schedule_field("amps"),
            "serial_errors": globalState.stateDict.get("eo_serial_errors", 0),
            "app_version": globalState.stateDict.get("app_version", "unknown"),
            "timestamp": int(time.time())
        }
        
        device_id = self.get_config("device_id")
        topic = f"openeo/{device_id}/state"
        payload = json.dumps(state_payload)
        
        try:
            self.mqtt_client.publish(topic, payload)
            _LOGGER.debug("Published state to MQTT")
        except Exception as e:
            _LOGGER.error(f"Failed to publish state: {e}")
    
    def poll(self):
        """Called by main loop - publish state at configured interval"""
        if not MQTT_AVAILABLE or not self.get_config("enabled"):
            return 0
        
        current_time = time.time()
        publish_interval = self.get_config("publish_interval")
        
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
        """Return configuration options for web interface"""
        settings = []

        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "homeassistant", ("mqtt_host",), 'MQTT Broker Host', note='MQTT Broker Host.')
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "homeassistant", ("mqtt_port",), 'MQTT Broker Port', note='MQTT Broker Port.')

        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "homeassistant", ("mqtt_username",), 'MQTT Username (optional)', note='MQTT Username (optional)')
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "homeassistant", ("mqtt_password",), 'MQTT Password (optional)', note='MQTT Password (optional)')
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "homeassistant", ("mqtt_discovery_prefix",), 'HA Discovery Prefix', note='HA Discovery Prefix')
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "homeassistant", ("device_name",), 'Device Name in HA', note='Device Name in HA')
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "homeassistant", ("device_id",), 'Device ID', note='Device ID')
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "chargeroptions", ("publish_interval",), 'Publish Interval (seconds)', \
            note="Publish Interval (seconds)", \
            range=(30,3600), default=300, step=30, value_unit="s")
        
        return settings

    
    def __del__(self):
        """Cleanup MQTT connection on plugin destruction"""
        if self.mqtt_client and self.connected:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()