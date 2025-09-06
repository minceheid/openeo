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
        
        # Send discovery message for each sensor
        for sensor in sensors:
            config = {
                "name": sensor["name"],
                "unique_id": f"{device_id}_{sensor['object_id']}",
                "state_topic": sensor["state_topic"],
                "device": device_info
            }
            
            # Add optional fields if present
            for field in ["value_template", "unit_of_measurement", "device_class", 
                         "icon", "payload_on", "payload_off"]:
                if field in sensor:
                    config[field] = sensor[field]
            
            topic = f"{discovery_prefix}/{sensor['component']}/{device_id}/{sensor['object_id']}/config"
            payload = json.dumps(config)
            
            try:
                self.mqtt_client.publish(topic, payload, retain=True)
                _LOGGER.debug(f"Published discovery for {sensor['name']}")
            except Exception as e:
                _LOGGER.error(f"Failed to publish discovery for {sensor['name']}: {e}")
        
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
            "vehicle_connected": vehicle_connected,
            "charging_active": charging_active,
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
        return [
            {"key": "enabled", "type": "bool", "title": "Enable Home Assistant MQTT"},
            {"key": "mqtt_host", "type": "str", "title": "MQTT Broker Host"},
            {"key": "mqtt_port", "type": "int", "title": "MQTT Broker Port"},
            {"key": "mqtt_username", "type": "str", "title": "MQTT Username (optional)"},
            {"key": "mqtt_password", "type": "str", "title": "MQTT Password (optional)"},
            {"key": "mqtt_discovery_prefix", "type": "str", "title": "HA Discovery Prefix"},
            {"key": "device_name", "type": "str", "title": "Device Name in HA"},
            {"key": "device_id", "type": "str", "title": "Device ID"},
            {"key": "publish_interval", "type": "int", "title": "Publish Interval (seconds)"}
        ]
    
    def __del__(self):
        """Cleanup MQTT connection on plugin destruction"""
        if self.mqtt_client and self.connected:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()