#################################################################################
"""
OpenEO Module: Charger Options
Change charger behaviour based on configuration.

Configuration example:
"chargeroptions": 
{
    "always_supply_current": true
}
"""
#################################################################################
import logging,re
import globalState, util

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class chargeroptionsClassPlugin:
    PRETTY_NAME = "Charger Options"  # @FUTURE: i18n?
    CORE_PLUGIN = True
    pluginConfig={}
    myName=""
    
    def __str__(self):
        return self.myName

    def __init__(self, configParam):
       # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        _LOGGER.debug("Initialising Module: "+self.myName)

    def configure(self, configParam):
        _LOGGER.info("Plugin Configured: " + type(self).__name__)
        self.pluginConfig = configParam
        if ("always_supply_current" in self.pluginConfig and isinstance(self.pluginConfig["always_supply_current"], bool)):
            globalState.stateDict["eo_always_supply_current"] = self.pluginConfig["always_supply_current"]
        if ("overall_limit_current" in self.pluginConfig and isinstance(self.pluginConfig["overall_limit_current"], int)):
            globalState.stateDict["eo_overall_limit_current"] = self.pluginConfig["overall_limit_current"]
        if ("charger_name" in self.pluginConfig and isinstance(self.pluginConfig["charger_name"], str)):
            globalState.stateDict["charger_name"] = self.pluginConfig["charger_name"]
        if ("charger_id" in self.pluginConfig and isinstance(self.pluginConfig["charger_id"], str)):
            globalState.stateDict["charger_id"] = self.pluginConfig["charger_id"]

    def get_config(self):
        return self.pluginConfig
        
    def poll(self):
        return 0

    def get_user_settings(self):
        settings = []
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "chargeroptions", ("charger_name",), 'Charger Name', note='Friendly name for your charger, used by APIs and the home screen.')
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "chargeroptions", ("charger_id",), 'Charger ID', note='For some APIs like OCPP.  Alphanumeric plus underscore only.',
            pattern='([A-Za-z0-9_])+')
        util.add_simple_setting(self.pluginConfig, settings, 'boolean', "chargeroptions", ("always_supply_current",), 'Always Supply Current', \
            note="Puts the charge point into 'dumb' mode.  All smart functions are disabled, and only the Overall Current Limit will apply.", default=False)
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "chargeroptions", ("overall_limit_current",), 'Overall Current Limit', \
            note="Does not override the PCB current limit setting.  This will prevent higher current limits from being used from e.g. the home screen and remote plugins.", \
            range=(6,32), default=32, value_unit="A")
        return settings