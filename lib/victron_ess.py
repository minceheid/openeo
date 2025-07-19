#################################################################################
"""
OpenEO Module: Victron Inverter Integration
Acts as the "scheduler" plugin as a simple timer, but introduces soc_min_pct 
constraints, so that the charger will not switch on, if the ESS state of charge
is below the minimum constraint. The idea behind this is to allow excess stored
energy to be dumped into the car, on a schedule that makes sense for the energy
generation.

Retrieves the ESS SOC from the inverter endpoint using TCP modbus, and stores it
in a cfg global. This is done as a separate thread, on the polling interval
defined in the configuration to ensure that the poll() method is not dependant
on the network.

Configuration example:
"victron_ess": {"endpoint": "192.168.123.77", "poll_interval":600,
	"schedule": [
		{"start": "2200", "end": "2359","amps":8,"soc_min_pct":25},
		{"start": "0000", "end": "0212","amps":12,"soc_min_pct":10}
	]}

"""
#################################################################################

import logging
import datetime
import time
import threading
import globalState
import re
from pyModbusTCP.client import ModbusClient

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class victron_essClassPlugin:
    PRETTY_NAME = "Victron ESS Integration"
    CORE_PLUGIN = False

    pluginConfig={}
    
    # State of Charge
    globalState.stateDict["eo_victron_ess_soc"]=0

    def __str__(self):
        return self.myName

    def get_config(self):
        return self.pluginConfig
        
    def configure(self,configParam):
        _LOGGER.debug("Plugin Configured: "+type(self).__name__)
        self.pluginConfig=configParam
        for i in self.pluginConfig["schedule"]:
            i['start']=datetime.time(int(i['start'][:2]),int(i['start'][-2:]),0,0)
            i['end']=datetime.time(int(i['end'][:2]),int(i['end'][-2:]),0,0)
        
    def poll(self):
        now=datetime.datetime.now().time()
        amps=0
         # Check Schedule
        charger_schedule_active=False
        for i in self.pluginConfig["schedule"]:
            try:
                schedule_amps=i["amps"]
            except:
                schedule_amps=16
            
            # Only charge if the ESS State of Charge is above the defined minimum threshold
            if (globalState.stateDict["eo_victron_ess_soc"]>i["soc_min_pct"]):
                if i['start']<i['end'] and ( now>i['start'] and now<i['end'] ):
                    amps=max(amps,schedule_amps)
                if i['end']<i['start'] and ( now>i['start'] or now<i['end'] ):
                    amps=max(amps,schedule_amps)

        return amps

    def __init__(self,configParam):
        # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        _LOGGER.debug("Initialising Module: Victron ESS")
        self.configure(configParam)

        # make a global var for storing the ESS State of Charge
        globalState.stateDict["eo_victron_ess_soc"]=0

        serverthread=threading.Thread(target=self.ess_poller, name='serverthread')
        serverthread.start()

    def ess_poller(self):
        while True:
            _LOGGER.debug("Polling ESS ("+self.pluginConfig["endpoint"]+")")

            # Ref:
            # https://communityarchive.victronenergy.com/questions/47637/multiplus-ii-gx-modbus-tcp-required-configuration.html
            # https://www.victronenergy.com/live/ccgx:modbustcp_faq
            # https://www.victronenergy.com/upload/documents/CCGX-Modbus-TCP-register-list-3.60.xlsx

            reg_battery_soc=843
            modbus_client = ModbusClient(host="192.168.123.40", port=502, unit_id=100, auto_open=True, auto_close=True, timeout=5)
            regs = modbus_client.read_holding_registers(reg_battery_soc, 1)

            if regs and len(regs)>0:
                globalState.stateDict["eo_victron_ess_soc"]=(regs[0])
            else:
                globalState.stateDict["eo_victron_ess_soc"]=0
                
            _LOGGER.debug("Victron ESS SoC: "+str(globalState.stateDict["eo_victron_ess_soc"])+"%")

            time.sleep(self.pluginConfig["poll_interval"])
