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
    pluginConfig={}
    pluginParamSpec={"enabled":"bool","on": "bool","amps":"int"}
    myName=""
        

    def poll(self):

        print("xxx switchpoll")
        if (self.pluginConfig.get("on",False)):
            print("xxx on")
            return self.pluginConfig.get("amps",32)
        else:
            print("xxx off")
            return 0