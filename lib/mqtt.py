#################################################################################
"""
OpenEO Module: MQTT Support
Allows MQTT communication with the OpenEO system.

Configuration example:
"mqtt":  {
    "enabled":1,
        "server": "mqtt.example.com",
    "port": 1883
    "username": "user",
    "password": "pass"

"""
#################################################################################
import logging
import datetime
import re
import paho.mqtt.client as mqtt
import json
import time
import copy
import globalState

# logging for use in this module
_LOGGER = logging.getLogger(__name__)


#################################################################################
class mqttClassPlugin:
    PRETTY_NAME = "MQTT"
    CORE_PLUGIN = False
    pluginConfig = []
    parsedSchedule = []
    myName = "mqtt"

    def __str__(self):
        return self.myName

    mqtt_base_config = {
        "state_topic": "",
        "unique_id": "{}_eominipro2",
        "device": {
            "identifiers": ["eominipro2"],
            "name": "EV Charger",
            "manufacturer": "EO",
            "model": "Mini Pro 2",
        },
        "name": "{}",
    }

    mqtt_topic_prefix = "evcharger/eominipro2/"
    mqtt_sensors = [
        {
            "type": "binary_sensor",
            "name": "Cable Connected",
            "topic": mqtt_topic_prefix + "cable_connected",
            "rest_name": "has_cable",
            "last_published": None,
        },
        {
            "type": "binary_sensor",
            "name": "Car Connected",
            "topic": mqtt_topic_prefix + "car_connected",
            "rest_name": "has_car",
            "last_published": None,
        },
        {
            "type": "binary_sensor",
            "name": "Charging",
            "topic": mqtt_topic_prefix + "charging",
            "rest_name": "charging",
            "last_published": None,
        },
        {
            "type": "sensor",
            "name": "CT Reading",
            "unit_of_measurement": "A",
            "device_class": "current",
            "state_class": "measurement",
            "topic": mqtt_topic_prefix + "ct_reading",
            "rest_name": "last_ct_reading",
            "last_published": None,
        },
        {
            "type": "sensor",
            "name": "Mains Voltage",
            "unit_of_measurement": "V",
            "device_class": "voltage",
            "state_class": "measurement",
            "topic": mqtt_topic_prefix + "mains_voltage",
            "rest_name": "mains_voltage",
            "last_published": None,
        },
        {
            "type": "sensor",
            "name": "Power",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "topic": mqtt_topic_prefix + "power",
            "rest_name": "power",
            "last_published": None,
        },
        {
            "type": "switch",
            "name": "Charging Override",
            "topic": mqtt_topic_prefix + "override",
            "command_topic": mqtt_topic_prefix + "override/set",
            "last_published": None,
        },
        {
            "type": "switch",
            "name": "Pause",
            "topic": mqtt_topic_prefix + "pause",
            "command_topic": mqtt_topic_prefix + "pause/set",
            "last_published": None,
        },
        {
            "type": "number",
            "name": "Override Current Limit",
            "unit_of_measurement": "A",
            "device_class": "current",
            "topic": mqtt_topic_prefix + "override_current_limit",
            "command_topic": mqtt_topic_prefix + "override_current_limit/set",
            "max": 32,
            "min": 6,
            "last_published": None,
        },
    ]

    def on_connect(self, client, userdata, flags, rc):
        _LOGGER.debug("Connected to MQTT broker with result code: " + str(rc))
        for sensor in self.mqtt_sensors:
            this_config = self.mqtt_base_config.copy()
            # Fill out the base config with this sensor's details
            this_config["state_topic"] = sensor["topic"]
            this_config["unique_id"] = this_config["unique_id"].format(
                sensor["name"].replace(" ", "_").lower()
            )
            this_config["name"] = this_config["name"].format(sensor["name"])

            # Add unit of measurement if it exists
            if "unit_of_measurement" in sensor:
                this_config["unit_of_measurement"] = sensor["unit_of_measurement"]
            # Add device class if it exists
            if "device_class" in sensor:
                this_config["device_class"] = sensor["device_class"]
            # Add state class if it exists
            if "state_class" in sensor:
                this_config["state_class"] = sensor["state_class"]
            # Add command topic if it exists
            if "command_topic" in sensor:
                this_config["command_topic"] = sensor["command_topic"]
                # Subscribe to the command topic
                client.subscribe(sensor["command_topic"])
            # Add min and max if they exist
            if "min" in sensor:
                this_config["min"] = sensor["min"]
            if "max" in sensor:
                this_config["max"] = sensor["max"]

            # Add expiry to the config of 30 seconds
            this_config["expire_after"] = 30

            # Construct the config topic for this sensor
            this_topic = f"homeassistant/{sensor['type']}/eominipro2_{sensor['name'].replace(' ', '_').lower()}/config"
            # Publish the config for this sensor
            client.publish(
                this_topic,
                json.dumps(this_config),
                retain=True,
            )

    def on_message(self, client, userdata, msg):
        _LOGGER.debug("Received message on topic: " + msg.topic + " with payload: " + str(msg.payload))
        # Handle incoming messages for command topics
        # Load config to access global state
        self.load_config()
        mqtt_topic_prefix = "evcharger/eominipro2/"
        if msg.topic == mqtt_topic_prefix + "pause/set":
            # Handle pause command
            topic_to_update = mqtt_topic_prefix + "pause"
            if msg.payload.decode() == "ON":
                self.config["switch"]["on"] = False
                updated_value = "OFF"
            elif msg.payload.decode() == "OFF":
                self.config["switch"]["on"] = True
                updated_value = "ON"
        elif msg.topic == mqtt_topic_prefix + "override/set":
            # Handle override command
            topic_to_update = mqtt_topic_prefix + "override"
            # If this is turned on, we enable the switch module and disable the scheduler module and vice versa
            if msg.payload.decode() == "ON":
                self.config["switch"]["enabled"] = True
                self.config["scheduler"]["enabled"] = False
                updated_value = "ON"
            elif msg.payload.decode() == "OFF":
                self.config["switch"]["enabled"] = False
                self.config["scheduler"]["enabled"] = True
                updated_value = "OFF"
        elif msg.topic == mqtt_topic_prefix + "override_current_limit/set":
            # Handle override current limit command
            topic_to_update = mqtt_topic_prefix + "override_current_limit"
            new_limit = int(msg.payload.decode())
            self.config["switch"]["amps"] = new_limit
            updated_value = new_limit

        # Save the updated configuration
        self.save_config()
        # Publish the updated value to the corresponding topic
        client.publish(topic_to_update, updated_value, retain=True)


    def load_config(self):
        try:
            with open(globalState.stateDict["eo_config_file"], "r") as f:
                self.config = json.load(f)
                return True
        except (FileNotFoundError, ValueError):
            self.config = {}
            return False

    def save_config(self):
        with open(globalState.stateDict["eo_config_file"], "w") as f:
            f.write(json.dumps(self.config, indent=2))

    def configure(self, configParam):
        _LOGGER.debug("Plugin Configured: " + type(self).__name__)
        self.pluginConfig = configParam
        # Create MQTT client
        self.client = mqtt.Client()
        self.client.username_pw_set(
            self.pluginConfig["username"], self.pluginConfig["password"]
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        # Connect to the MQTT broker
        self.client.connect(self.pluginConfig["server"], self.pluginConfig["port"])
        # Start MQTT client loop in background thread
        self.client.loop_start()
        # Set the polls value to 0
        self.polls = 0

    def get_config(self):
        return self.pluginConfig

    def poll(self):
        amps = 0
        # Waiting for 2 polls to have passed before sending updates to ensure we've got some initial data
        if self.polls < 2:
            self.polls += 1
            return amps
        # Poll the charger and send updates to MQTT
        status = copy.copy(globalState.stateDict)
        for x in globalState.stateDict:
            if x[0] == "_":
                # an underscore denotes a private configuration that probably shouldn't be exposed
                status.pop(x, None)

        for sensor in self.mqtt_sensors:
            if sensor["type"] == "binary_sensor":
                # Binary sensors are for cable plugged / car plugged / charging
                if sensor["name"] == "Cable Connected":
                    if any(
                        state in globalState.stateDict["eo_charger_state"]
                        for state in [
                            "plug-present",
                            "car-connected",
                            "charging",
                            "charge",
                        ]
                    ):
                        value_to_publish = "ON"
                    else:
                        value_to_publish = "OFF"
                    retain = True
                elif sensor["name"] == "Car Connected":
                    if any(
                        state in globalState.stateDict["eo_charger_state"]
                        for state in ["car-connected", "charging", "charge"]
                    ):
                        value_to_publish = "ON"
                    else:
                        value_to_publish = "OFF"
                    retain = True
                elif sensor["name"] == "Charging":
                    if "charging" in globalState.stateDict["eo_charger_state"]:
                        value_to_publish = "ON"
                    else:
                        value_to_publish = "OFF"
                    retain = True
            elif sensor["type"] == "sensor":
                if sensor["name"] == "CT Reading":
                    value_to_publish = globalState.stateDict["eo_p1_current"]
                    retain = True
                elif sensor["name"] == "Mains Voltage":
                    value_to_publish = globalState.stateDict["eo_live_voltage"]
                    retain = True
                elif sensor["name"] == "Power":
                    # Calculating power so we can send W to HASS instead of kW
                    value_to_publish = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_p1_current"]), 2)  
                    retain = True
            elif sensor["type"] == "switch" or sensor["type"] == "number":
                # For switches and numbers (charging override, pause, override current limit) we need to check the status of the 'switch' module
                self.load_config()
                if sensor["name"] == "Charging Override":
                    if self.config["switch"]["enabled"]:
                        value_to_publish = "ON"
                    else:
                        value_to_publish = "OFF"
                    retain = False
                elif sensor["name"] == "Override Current Limit":
                    value_to_publish = self.config["switch"]["amps"]
                    retain = True
                elif sensor["name"] == "Pause":
                    if self.config["switch"]["enabled"] and not self.config["switch"]["on"]:
                        value_to_publish = "ON"
                    else:
                        value_to_publish = "OFF"
                    retain = True

            self.client.publish(
                sensor["topic"],
                value_to_publish,
                retain=retain,
            )

        return amps

    def __init__(self, configParam):
        _LOGGER.debug("Initialising Module: MQTT")
        # Store the name of the plugin for reuse elsewhere
        self.configure(configParam)
