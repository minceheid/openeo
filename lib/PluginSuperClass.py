#################################################################################
"""
OpenEO Module: PluginSuperClass

Parent class for all plugin modules, providing common functions. The configure() method
will automatically do type conversion/checks and handle default values based on the 
pluginParamSpec{} dict. Format as follows:

pluginParamSpec= { "<attributename>": {"type": "(bool|int|float|str|json", "default": <defaultvalue> )}}

"""
#################################################################################

import logging,json
import re, numbers

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

class PluginSuperClass:
    
    # Class variable to indicate how often the poll() method should be called. A value of 1 will
    # cause poll() to be called every iteration of the main loop, a value of 100 will indicate that
    # we expect poll() to be called every 100 iterations. A value of 0 indicated that poll() will never be 
    # called.
    
    pollfrequency = 1

    def _convertType(self,attribute,value,typeClass,default=None):
        """
        Internal method used by the configure() method. This attempts to do type conversion, or
        if not possible, returns a default value.    
        """

        if value is not None:
            match typeClass:
                case "bool":
                    return ((isinstance(value,numbers.Number) and value==1) or (isinstance(value,str) and value.lower()=="true") or (isinstance(value,str) and value.isnumeric() and int(value)==1))
                case "int":
                    if isinstance(value,(float,int)) or (isinstance(value,str) and re.match(r'^-?\d+(?:\.?\d+)?$', value)):
                        return int(float(value))
                case "float":
                    if isinstance(value,(float,int)) or (isinstance(value,str) and re.match(r'^-?\d+(?:\.?\d+)?$', value)):
                        return float(value)
                case "str":
                    if isinstance(value,(str)):
                        return value
                case "json":
                    if isinstance(value,(str)):
                        try:
                            return(json.loads(value))
                        except Exception as e:
                            _LOGGER.error(f"Invalid JSON syntax ({value})")
                            return json.loads(default)
                    else:
                        _LOGGER.error(f"Non-str value passed to json decoder")
                        return(value)
                            

	# If we didn't match any of these conditions, then we should return the default value
	# But we should also check to see that the default value is either None
	# or matches the type we expect.
        defaultType=type(default).__name__
        if typeClass=="json":
            return json.loads(default)
        elif default==None or defaultType==typeClass or (defaultType=="int" and typeClass=="float"):
            return(default)
        else:
            _LOGGER.error(f"Given default value ({default}({defaultType})) for {attribute} that does not match given typeClass ({typeClass}). Returning None from _convertType - check pluginParamSpec")
            return(None)

    
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
        # Does type conversion, based on the pluginParamSpec{} dict
        for attribute,spec in self.pluginParamSpec.items():
            self.pluginConfig[attribute]=self._convertType(attribute,self.pluginConfig.get(attribute,None),spec["type"],spec["default"])

    def get_config(self,key=None):
        if key is None:
            return self.pluginConfig
        else:
            return self.pluginConfig[key]
            
    def get_user_settings(self):
        return []
    
    def __init__(self,configParam):
        # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        _LOGGER.debug("Initialising Module: "+self.myName)
        self.configure(configParam)


