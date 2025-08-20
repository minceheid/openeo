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
import util
import globalState


# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class switchClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Switch"
    CORE_PLUGIN = True  
    pluginParamSpec={	"enabled":	{"type": "bool","default": True},
			"on":	{"type": "bool", "default":False},
			"retain_state_on_start":	{"type": "bool", "default":True},
			"amps":	{"type": "int","default":32}}
        
    def poll(self):
        if (self.pluginConfig.get("on",False)):
            return self.pluginConfig.get("amps",32)
        else:
            return 0

    def __init__(self,configParam):
        super().__init__(configParam)
        if not self.pluginConfig.get("retain_state_on_startup"):
            globalState.configDB.set("switch","on",False)