#################################################################################
"""
This is the place for global shared values. Only ephermeral values should be stored here
configuration settings should be persisted in the configuration database and set as a default
value where necessary. For consistency all globals should be prefixed with "eo_"
and any "private" globals that should not be exported through public means 
(e.g. Prometheus or Home Assistant exporters) should be prefixed with underscore.
Values don't *need* to be predeclared here, but probably important that we document the
critical ones.
"""

import logging, os
from openeoConfig  import openeoConfigClass

_LOGGER = logging.getLogger(__name__)

# Read the application version; if not present, default to 0.0.
try:
    appVer = open("version.txt", "r").read()
except:
    _LOGGER.warning("Unable to get application version")
    appVer = "0.0"
    
stateDict={
    # amps_requested: This is the number of Amps that will are requested by the polling
    # of the plugin modules (e.g. time scheduler)
    # amps_limit: This is the final amps limit after it has been moderated by the charger
    # status (that is, if the car is not plugged in, it will be moderated down to zero)
    "eo_amps_requested":0,
    "eo_amps_limit": 0,

    # Numeric and descriptive (text) state identifier for the status of the charger
    "eo_charger_state_id":0,
    "eo_charger_state":"",

    # CT Sensor Current (Amps)
    "eo_current_site":0,  #site
    "eo_current_vehicle":0,  #vehicle
    "eo_current_solar":0,  #solar
    
    # Power Delivered and requested (kW). Calculated from current and voltage
    "eo_power_delivered":0,
    "eo_power_requested":0,

    # Voltage
    "eo_live_voltage": 0,

    # Mains Frequency, in Hz
    "eo_mains_frequency":0,

    # Always set charger to requested current, even if no car is connected
    "eo_always_supply_current": False,
    
    # Set if there is an overriding total current limit.  ConfigServer should generally not
    # offer the user the ability to set currents above this amount.
    "eo_overall_limit_current" : 32,
    
    # Name and ID of the charger, used for web interface, APIs, etc.
    "charger_name" : "openeo Charger",
    "charger_id" : "openeo_1",

    # Counter of the number of serial overruns
    "eo_serial_errors": 0,
    
    # Application (openeo) version
    "app_version" : appVer,
    
    # This confirms the commit id of the branch or version that is running
    "app_deploy_directory" : os.path.basename(os.path.realpath(os.getcwd()))
}


defaultConfig = {
        "scheduler" : { "enabled" : True },
        "switch" : { "enabled" : False },
        "configserver" : { "enabled" : True },
        "logger" : { "enabled" : True },
        "chargeroptions" : { "enabled" : True, "mode" : "schedule" },
        "loadmanagement" : { "enabled" : True }}

configDB = openeoConfigClass(defaultConfig)
