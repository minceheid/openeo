#################################################################################
"""
OpenEO Module: Load Management
A simple module implementing solar and site load management

"""
#################################################################################

import logging,statistics
from lib.PluginSuperClass import PluginSuperClass
import util
import globalState


# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class loadmanagementClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Site and Solar Load Management"
    CORE_PLUGIN = True  
    pluginParamSpec={	
            "enabled":	{"type": "bool","default": True},
			"solar_enable":	{"type": "bool", "default":False},
			"solar_reservation_current":	{"type": "int", "default": 1},
			"site_limit_current":	{"type": "int", "default": 60},
            "simulate_ct_solar":    {"type": "float", "default": 0.0},
            "simulate_ct_site":     {"type": "float", "default": 0.0},
            "ct_calibration_site":   {"type": "float", "default": 1.0},
            "ct_calibration_vehicle":{"type": "float", "default": 1.0},
            "ct_calibration_solar":  {"type": "float", "default": 1.0},
            "ct_offset_site":   {"type": "float", "default": 0.0},
            "ct_offset_vehicle":{"type": "float", "default": 0.0},
            "ct_offset_solar":  {"type": "float", "default": 0.0},
            "solar_enable_threshold": {"type": "int", "default":7}
            }

    solar_ct_readings=[0,0,0,0,0,0]
    solar_active=False
        
    def poll(self):
        # Add current CT reading to the moving average calculation
        self.solar_ct_readings.append(globalState.stateDict["eo_current_solar"])
        del self.solar_ct_readings[0]

        if (self.pluginConfig.get("solar_enable",False)):
            solar_current=int(statistics.mean(self.solar_ct_readings) - self.pluginConfig.get("solar_reservation_current",1))

            if self.solar_active:
                if solar_current>=6:
                    return solar_current
                else:
                    self.solar_active=False
                    return 0
            else:
                if solar_current>=self.pluginConfig.get("solar_enable_threshold",7):
                    self.solar_active=True
                    return solar_current
                else:
                    return 0


    def get_user_settings(self):
        settings = []
        util.add_simple_setting(self.pluginConfig, settings, 'boolean', "loadmanagement", ("solar_enable",), 'Solar Charging Enabled', \
            note="This setting will allow openeo to charge, regardless of whether the manual or schedule mode is enabled", default=False)
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "loadmanagement", ("solar_reservation_current",), 'Solar Reservation Current', \
            note="Solar charging will be reduced by this number of amps to reserve some capacity for site base load.", \
            range=(0,8), default=1, value_unit="A")
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "loadmanagement", ("site_limit_current",), 'Maximum Site Consumption', \
            note="When a current sensor is installed on the site electrical feed, setting this value may restrict charger output if electricity consumption measured at the sensor is high.", \
            range=(1,100), default=60, value_unit="A")
        return settings