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
import logging
import datetime
import re

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class schedulerClassPlugin:
    myName=""

    PRETTY_NAME = "Scheduler"
    CORE_PLUGIN = True  
    pluginConfig = []
    myName=""

    def __str__(self):
        return self.myName

    def configure(self,configParam):
        _LOGGER.debug("Plugin Configured: "+type(self).__name__)
        self.pluginConfig=configParam
        for i in self.pluginConfig["schedule"]:
            i['start']=datetime.time(int(i['start'][:2]),int(i['start'][-2:]),0,0)
            i['end']=datetime.time(int(i['end'][:2]),int(i['end'][-2:]),0,0)
        
    def get_config(self):
        return self.pluginConfig
        
    def poll(self):
        now=datetime.datetime.now().time()
        amps=0
        # Check each defined schedule in the configuration
        for i in self.pluginConfig["schedule"]:
            schedule_amps=i.get("amps",32)

            if i['start']<i['end'] and ( now>i['start'] and now<i['end'] ):
                amps=max(amps,schedule_amps)
            if i['end']<i['start'] and ( now>i['start'] or now<i['end'] ):
                amps=max(amps,schedule_amps)

        return amps

    def __init__(self,configParam):
        _LOGGER.debug("Initialising Module: Scheduler")
        # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        self.configure(configParam)