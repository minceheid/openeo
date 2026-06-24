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
                        "overall_limit_current":  {"type": "int","default":32},
                        "overall_property_limit_current":  {"type": "int","default":60},
                        "limit_current_to_solar_output":  {"type": "bool","default":False},
                        "charger_name":  {"type": "str","default":"openeo"},
                        "charger_id":  {"type": "str","default":"openeo_1"},
                        "mains_voltage_correction":  {"type": "float","default":77.8},
                    }

    def configure(self, configParam):
        super().configure(configParam)
        globalState.stateDict["eo_overall_limit_current"] = self.pluginConfig["overall_limit_current"]
        globalState.stateDict["charger_name"] = self.pluginConfig["charger_name"]
        globalState.stateDict["charger_id"] = self.pluginConfig["charger_id"]


    def get_user_settings(self):
        return [{"type": "textinput", "name": "charger_name", "label": "Charger Name", "default":self.pluginConfig.get("charger_name",False), "note":"Friendly name for your charger, used by APIs and the home screen."},
                {"type": "textinput", "name": "charger_id", "label": "Charger ID", "default":self.pluginConfig.get("charger_id",False), "note":"For some APIs like OCPP.  Alphanumeric plus underscore only.","pattern":'([A-Za-z0-9_])+'},
                {"type": "slider", "name": "overall_limit_current", "label": "Overall Current Limit", "default":self.pluginConfig.get("overall_limit_current",False), "range": [globalState.MIN_CHARGING_CURRENT, globalState.MAX_CHARGING_CURRENT], "value_unit":"A", "note":"Does not override the PCB current limit setting.  This will prevent higher current limits from being used from e.g. the home screen and remote plugins."},
                {"type": "slider", "name": "mains_voltage_correction", "label": "Mains Voltage Correction", "default":self.pluginConfig.get("mains_voltage_correction",77.8), "range": [50,150], "step":0.1, "value_unit":"%", "note":"Scaling factor used for calculating the mains voltage from the value provided by the charger.  The default value of 77% is based on the measured voltage of a typical UK mains supply on a Mini Pro 2. This value can be fine tuned against local voltmeter readings. The power delivered to the car (kWh) is calculated from the voltage and the current measured over time, so fine tuning this may help improve accuracy of session logging."},];
