#################################################################################
"""
OpenEO Module: PluginSuperClass

Configuration example:

"""
#################################################################################

import logging
import re, numbers

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

class PluginSuperClass:

    def _convertType(self,value,typeClass):
        match typeClass:
            case "bool":
                return ((isinstance(value,numbers.Number) and value==1) or (isinstance(value,str) and value.lower()=="true") or (isinstance(value,str) and value.isnumeric() and int(value)==1))
            case "int":
                if isinstance(value,(float,int)) or (isinstance(value,str) and re.match(r'^-?\d+(?:\.?\d+)$', value)):
                    return int(float(value))
            case "float":
                if isinstance(value,(float,int)) or (isinstance(value,str) and re.match(r'^-?\d+(?:\.?\d+)$', value)):
                    return float(value)

    
#################################################################################
    PRETTY_NAME = "PluginSuperClass"
    CORE_PLUGIN = True  
    pluginConfig={}
    pluginParamSpec={}
    myName=""
    
    def __str__(self):
        return self.myName
    
        

    def configure(self,configParam):
        _LOGGER.debug("Plugin Configured: "+self.myName)
        self.pluginConfig=configParam

        # Does type conversion
        for attribute,type in self.pluginParamSpec.items():
            self.pluginConfig[attribute]=self._convertType(self.pluginConfig[attribute],type)

    def get_config(self):
        return self.pluginConfig
        
    def poll(self):
        return 0
            
    def get_user_settings(self):
        return []
    
    def __init__(self,configParam):
        # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        _LOGGER.debug("Initialising Module: "+self.myName)
        print("configuring")
        try:
            self.configure(configParam)
        except Exception as e:
                print("Aborting %s" % (repr(e)))


