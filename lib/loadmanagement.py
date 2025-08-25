#################################################################################
"""
OpenEO Module: Load Management
A simple module implementing solar and site load management

"""
#################################################################################

import logging
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
			"solar_trickle":	{"type": "bool", "default":False},
			"solar_reservation_current":	{"type": "int", "default": 1},
            "solar_limit_all_output":  {"type": "bool","default":False},
			"site_limit_current":	{"type": "int", "default": 60},
            "simulate_ct_solar":    {"type": "int", "default": 0},
            "simulate_ct_site":     {"type": "int", "default": 0}
            }
        
    def poll(self):
        if (self.pluginConfig.get("solar_trickle",False)):
            return globalState.stateDict["eo_current_solar"] - self.pluginConfig.get("solar_reservation_current",1)
        else:
            return 0

    def get_user_settings(self):
        settings = []
        util.add_simple_setting(self.pluginConfig, settings, 'boolean', "loadmanagement", ("solar_trickle",), 'Solar charging at all times ', \
            note="This setting will allow openeo to charge, regardless of whether the manual or schedule mode is enabled", default=False)
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "loadmanagement", ("solar_reservation_current",), 'Solar Reservation Current', \
            note="Solar charging will be reduced by this number of amps to reserve some capacity for site base load.", \
            range=(0,8), default=1, value_unit="A")
        util.add_simple_setting(self.pluginConfig, settings, 'boolean', "loadmanagement", ("solar_limit_all_output",), 'Limit all charging current to solar output', \
            note="Tracks solar current generation through the current sensor, and limits vehicle charging current to match", default=False)
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "loadmanagement", ("site_limit_current",), 'Maximum site consumption', \
            note="When a current sensor is installed on the site electrical feed, setting this value may restrict charger output if electricity consumption measured at the sensor is high.", \
            range=(16,100), default=60, value_unit="A")
        return settings
