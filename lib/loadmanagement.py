#################################################################################
"""
OpenEO Module: Load Management
A simple module implementing solar and site load management

"""
#################################################################################

import logging,statistics,datetime
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
			"solar_enable":	{"type": "bool", "default":False},
			"site_limit_current":	{"type": "int", "default": 60},
            "ct_calibration_site":   {"type": "float", "default": 1.0},
            "ct_calibration_vehicle":{"type": "float", "default": 1.0},
            "ct_calibration_solar":  {"type": "float", "default": 1.0},
            "ct_offset_site":   {"type": "float", "default": 0.0},
            "ct_offset_vehicle":{"type": "float", "default": 0.0},
            "ct_offset_solar":  {"type": "float", "default": 0.0},
            "solar_enable_threshold": {"type": "int", "default":7},
            "schedule": {"type": "json","default":'[{"start": "0000", "end": "2359", "amps": 0}]'},
            }

    solar_ct_readings=[0]*2
    solar_active=False
    parsedSchedule = []


    def get_active_schedule(self):
        # Determines whether there is a solar schedule active, and if there is, return the 
        # reservation value. Also updates globalState with solar_active and solar_reservation
        now=datetime.datetime.now().time()
        amps=None

        # if solar is not enabled, then skip the schedule checks
        if (self.pluginConfig.get("solar_enable",False)):
            # if there was no schedules defined, then default to solar being active
            if len(self.parsedSchedule)==0:
                amps=0
            else:
                # Check each defined schedule in the configuration
                for i in self.parsedSchedule:
                    schedule_amps = i.get("amps", 0)

                    if i['start'] < i['end'] and (now > i['start'] and now < i['end']):
                        if not amps:
                            amps=0
                        amps = max(amps, schedule_amps)
                    if i['end'] < i['start'] and (now > i['start'] or now < i['end']):
                        if not amps:
                            amps=0
                        amps = max(amps, schedule_amps)
            
        if amps is None:
            globalState.stateDict["eo_solar_active"]=False
            globalState.stateDict["eo_solar_reservation"]=0
        else:
            
            globalState.stateDict["eo_solar_active"]=True
            globalState.stateDict["eo_solar_reservation"]=amps

        return amps


    def poll(self):
        # Add current CT reading to the moving average calculation
        self.solar_ct_readings.append(globalState.stateDict["eo_current_solar"])
        del self.solar_ct_readings[0]

        return_value=0
        solar_reservation_current=self.get_active_schedule()

        if (self.pluginConfig.get("solar_enable",False)):

            if solar_reservation_current is not None:
                # Solar schedule is active
                ct_reading=int(statistics.mean(self.solar_ct_readings))
                solar_current=ct_reading - solar_reservation_current
                if self.solar_active:
                    if solar_current>=6:
                        return_value=solar_current
                    else:
                        self.solar_active=False
                else:
                    if solar_current>=self.pluginConfig.get("solar_enable_threshold",7):
                        self.solar_active=True
                        return_value=solar_current

        globalState.stateDict["eo_solar_charge_current"]=return_value
        return return_value

       
       


    def get_user_settings(self):
        settings = []
        util.add_simple_setting(self.pluginConfig, settings, 'boolean', "loadmanagement", ("solar_enable",), 'Solar Charging Enabled', \
            note="This setting will allow openeo to charge, regardless of whether the manual or schedule mode is enabled", default=False)
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "loadmanagement", ("site_limit_current",), 'Maximum Site Consumption', \
            note="When a current sensor is installed on the site electrical feed, setting this value may restrict charger output if electricity consumption measured at the sensor is high.", \
            range=(1,100), default=60, value_unit="A")
        return settings

    def get_user_settings_v2(self):
        return [{"type": "boolean", "name": "solar_enable",       "label": "Solar Charging Enabled",   "default":self.pluginConfig.get("solar_enable",False),     "note":"This setting will allow openeo to charge, regardless of whether the manual or schedule mode is enabled"},
                {"type": "slider",  "name": "site_limit_current", "label": "Maximum Site Consumption", "default":self.pluginConfig.get("site_limit_current",60),  "range": [1,100], "value_unit":"A", "note":"When a current sensor is installed on the site electrical feed, setting this value may restrict charger output if electricity consumption measured at the sensor is high."}];


    def configure(self,configParam):
        super().configure(configParam)
        self.parsedSchedule=[]
        for n, i in enumerate(self.pluginConfig["schedule"]):
            sched = {}
            sched['start'] = datetime.time(int(i['start'][:2]), int(i['start'][-2:]),0,0)
            sched['end'] = datetime.time(int(i['end'][:2]), int(i['end'][-2:]),0,0)
            sched['amps'] = int(i['amps'])
            self.parsedSchedule.append(sched)    
        