#################################################################################
"""
OpenEO Module: Simple Time Scheduler
Acts as the "scheduler" plugin as a simple timer. Multiple timeslots can be 
specified, along with the number of Amps (8-32) to set the charger to discharged
(32A~=7kW).

Configuration example:
"scheduler":  {
    "enabled":1,
	"schedule": [{"start": "0212", "end": "0705", "amps": 32}]},

"""
#################################################################################
import logging, datetime
from lib.PluginSuperClass import PluginSuperClass
import traceback
import util


# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class schedulerClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Scheduler"
    CORE_PLUGIN = True  
    pluginParamSpec={ "enabled":      {"type": "bool","default": True},
			"schedule": {"type": "json","default":'[{"start": "2200", "end": "0400", "amps": 32}]'},
            "scheduler_granularity": {"type": "int","default": 5}}
    parsedSchedule = []


    def configure(self,configParam):
        super().configure(configParam)
        self.parsedSchedule=[]
        for n, i in enumerate(self.pluginConfig["schedule"]):
            sched = {}
            sched['start'] = datetime.time(int(i['start'][:2]), int(i['start'][-2:]),0,0)
            sched['end'] = datetime.time(int(i['end'][:2]), int(i['end'][-2:]),0,0)
            sched['amps'] = int(i['amps'])
            self.parsedSchedule.append(sched)    
        

    def poll(self):
        now=datetime.datetime.now().time()
        amps=0
        # Check each defined schedule in the configuration
        for i in self.parsedSchedule:
            schedule_amps = i.get("amps", 32)

            if i['start'] < i['end'] and (now > i['start'] and now < i['end']):
                amps = max(amps, schedule_amps)
            if i['end'] < i['start'] and (now > i['start'] or now < i['end']):
                amps = max(amps, schedule_amps)

        return amps

    def get_user_settings(self):
        settings = []
        util.add_simple_setting(self.pluginConfig, settings, 'slider', "scheduler", ("scheduler_granularity",), 'Schedule Clockface Step Size', \
            note="This allows the granularity of the clock timer to be set", range=(5,15), step=5, default=5, value_unit="min")
        return settings