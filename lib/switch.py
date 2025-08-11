#################################################################################
"""
OpenEO Module: Switch
A simple module implementing an on/off switch

Configuration example:
"switch": {"on": True, "amps": 32}

"""
#################################################################################

import logging
from lib.PluginSuperClass import PluginSuperClass


# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class switchClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Switch"
    CORE_PLUGIN = True  
    pluginParamSpec={	"enabled":	{"type": "bool","default": True},
			"on":	{"type": "bool", "default":False},
			"amps":	{"type": "int","default":32}}
        
    def poll(self):
        if (self.pluginConfig.get("on",False)):
            return self.pluginConfig.get("amps",32)
        else:
            return 0
