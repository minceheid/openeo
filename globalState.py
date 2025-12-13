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

# Charging current limits (based on EV charging standards)
MIN_CHARGING_CURRENT = 6  # Minimum safe charging current (IEC 61851)
MAX_CHARGING_CURRENT = 32  # Maximum hardware current limit

_LOGGER = logging.getLogger(__name__)

# Read the application version; if not present, default to 0.0.
try:
    appVer = open("release.txt", "r").read().strip()
except:
    _LOGGER.warning("Unable to get application version from release.txt")
    appVer = "0.0"
    
stateDict={
    # eo_serial_number: This is the serial number of the smart board in the charger that
    # the pi communicates with 
    "eo_serial_number":"",

    # amps_requested: This is the number of Amps that will are requested by the polling
    # of the plugin modules (e.g. time scheduler)
    # amps_limit: This is the final amps limit after it has been moderated by the charger
    # status (that is, if the car is not plugged in, it will be moderated down to zero)
    "eo_amps_requested":0,

    # The following three are subcomponents of eo_amps_requested, for the purpose of 
    # visualisation. It's an attempt to show the solar and grid requested amounts, and to
    # visualise when a site load limit is in play, and consequently blocking potnetial
    # charging capacity 
    "eo_amps_requested_grid":0,
    "eo_amps_requested_solar":0,
    "eo_amps_requested_site_limit":0,

    # Numeric and descriptive (text) state identifier for the status of the charger
    "eo_charger_state_id":0,
    "eo_charger_state":"",

    # Number of joules that the connected vehicle has recieved in this session
    # This figure is reset to zero when we detect that the car has been disconnected
    "eo_session_joules":0,
    "eo_session_kwh":0,
    "eo_session_timestamp":0,
    "eo_session_seconds_charged":0,

    # CT Sensor Current (Amps) - Adjusted figures with CT tuner modifiers applied
    "eo_current_site":0,  #site
    "eo_current_vehicle":0,  #vehicle
    "eo_current_solar":0,  #solar

    
    # Raw CT Sensor Current (Amps) - unadjusted figures
    "eo_current_raw_site":0,  #site
    "eo_current_raw_vehicle":0,  #vehicle
    "eo_current_raw_solar":0,  #solar
    
    # Power Delivered and requested (kW). Calculated from current and voltage
    "eo_power_delivered":0,
    "eo_power_requested":0,
    "eo_power_requested_grid":0,
    "eo_power_requested_solar":0,
    "eo_power_requested_site_limit":0,

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

    
    # Application (openeo) version
    "app_version" : appVer,
    
    # This confirms the commit id of the branch or version that is running
    "app_deploy_directory" : os.path.basename(os.path.realpath(os.getcwd())),

    # System metrics
    "sys_cpu_temperature" : 0,
    "sys_1m_load_average" : 0,
    "sys_available_memory" : 0,
    "sys_free_memory" : 0,
    "sys_wifi_strength" : 0,
    # Counter of the number of serial overruns
    "eo_serial_errors": 0,

}


defaultConfig = {
        "scheduler" : { "enabled" : True },
        "switch" : { "enabled" : False },
        "configserver" : { "enabled" : True },
        "chargersession" : { "enabled" : True },
        "logger" : { "enabled" : True },
        "checkversion" : { "enabled" : True },
        "chargeroptions" : { "enabled" : True, "mode" : "schedule" },
        "loadmanagement" : { "enabled" : True },
        "os_metrics" : { "enabled" : True },
        "homeassistant" : { "enabled" : False },
        "cloud" : {"enabled": True},
        }

configDB = openeoConfigClass(defaultConfig)
