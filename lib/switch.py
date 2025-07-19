#################################################################################
"""
OpenEO Module: Switch
A simple module implementing an on/off switch

Configuration example:
"switch": {"on": True, "amps": 32}

"""
#################################################################################

import logging
import re

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class switchClassPlugin:
    PRETTY_NAME = "Switch"
    CORE_PLUGIN = True  
    pluginConfig={}
    myName=""
    
    def __str__(self):
        return self.myName

    def configure(self,configParam):
        _LOGGER.debug("Plugin Configured: "+self.myName)
        self.pluginConfig=configParam

    def get_config(self):
        return self.pluginConfig
        
    def poll(self):
        if (self.pluginConfig.get("on",False)):
            return self.pluginConfig.get("amps",32)
        else:
            return 0
            
    def get_user_settings(self):
        return []
    
    def __init__(self,configParam):
        # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        _LOGGER.debug("Initialising Module: "+self.myName)
        self.configure(configParam)
