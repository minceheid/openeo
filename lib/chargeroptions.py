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
from lib.PluginSuperClass import PluginSuperClass

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class chargeroptionsClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Charger Options"  # @FUTURE: i18n?
    CORE_PLUGIN = True
    pluginParamSpec={   "enabled":      {"type": "bool","default": True},
                        "always_supply_current":   {"type": "bool", "default":False},
                        "overall_limit_current":  {"type": "int","default":32},
                        "overall_property_limit_current":  {"type": "int","default":60},
                        "limit_current_to_solar_output":  {"type": "bool","default":False},
                        "charger_name":  {"type": "str","default":"openeo"},
                        "charger_id":  {"type": "str","default":"openeo_1"}}

    def configure(self, configParam):
        super().configure(configParam)
        globalState.stateDict["eo_always_supply_current"] = self.pluginConfig["always_supply_current"]
        globalState.stateDict["eo_overall_limit_current"] = self.pluginConfig["overall_limit_current"]
        globalState.stateDict["charger_name"] = self.pluginConfig["charger_name"]
        globalState.stateDict["charger_id"] = self.pluginConfig["charger_id"]

    def get_user_settings(self):
        settings = []
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "chargeroptions", ("charger_name",), 'Charger Name', note='Friendly name for your charger, used by APIs and the home screen.')
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "chargeroptions", ("charger_id",), 'Charger ID', note='For some APIs like OCPP.  Alphanumeric plus underscore only.',
            pattern='([A-Za-z0-9_])+')
        util.add_simple_setting(self.pluginConfig, settings, 'boolean', "chargeroptions", ("always_supply_current",), 'Always Supply Current', \
            note="Puts the charge point into 'dumb' mode.  All smart functions are disabled, and only the Overall Current Limit will apply.", default=False)
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "chargeroptions", ("overall_limit_current",), 'Overall Current Limit', \
            note="Does not override the PCB current limit setting.  This will prevent higher current limits from being used from e.g. the home screen and remote plugins.", \
            range=(globalState.MIN_CHARGING_CURRENT, globalState.MAX_CHARGING_CURRENT), default=globalState.MAX_CHARGING_CURRENT, value_unit="A")

        return settings
