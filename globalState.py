#################################################################################
"""
This is the place for globals. For consistency all globals should be prefixed with "eo_"
and any "private" globals that should not be exported through public means 
(e.g. Prometheus or Home Assistant exporters) should be prefixed with underscore.
Values don't *need* to be predeclared here, but probably important that we document the
critical ones.
"""

import logging

_LOGGER = logging.getLogger(__name__)

# Read the application version; if not present, default to 0.0.
try:
    appVer = open("version.txt", "r").read()
except:
    _LOGGER.warning("Unable to get application version")
    appVer = "0.0"
    
stateDict={
    # Name of the Configuration File
    "eo_config_file": "config.json", 

    # amps_requested: This is the number of Amps that will are requested by the polling
    # of the plugin modules (e.g. time scheduler)
    # amps_limit: This is the final amps limit after it has been moderated by the charger
    # status (that is, if the car is not plugged in, it will be moderated down to zero)
    "eo_amps_requested":0,
    "eo_amps_limit": 0,

    # Numeric and descriptive (text) state identifier for the status of the charger
    "eo_charger_state_id":0,
    "eo_charger_state":"",

    # Phase 1 Current (Amps)
    "eo_p1_current":0,
    # Power Delivered and requested (kW). Calculated from current and voltage
    "eo_power_delivered":0,
    "eo_power_requested":0,

    # Voltage
    "eo_live_voltage": 0,

    # Mains Frequency, in Hz
    "eo_mains_frequency":0,

    # Always set charger to requested current, even if no car is connected
    "eo_always_supply_current": False,
    
    # Application (openeo) version
    "app_version" : appVer
}
