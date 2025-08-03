#!/usr/bin/env python3
"""
MIT License

Copyright (c)2025 mike@scott.land and contriutors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import logging
import logging.handlers
import json, os, time, subprocess, math

import globalState, util
from openeoCharger import openeoChargerClass

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
# Read Configuration File

def readConfiguration(filename):
    #######
    # Read config file to determine which modules to look for. If it doesn't exist, 
    # then write a default version. If the JSON can't be interpreted, then abort and
    # return nothing. I don't think we want to overwrite a configuration file if there
    # is a typo in it from a manual edit.
    try:
        with open(filename,"r") as file:
            try:
                return(json.load(file))
            except ValueError:
                _LOGGER.error("JSON decode failed in config file ("+filename+")")
                return(None)
    except (FileNotFoundError):
        # If the config is not loadable, create a default configuration.
        _LOGGER.error("Config file couldn't be loaded, recreating defaults ("+filename+")")
        myConfig = {
            "scheduler" : { "enabled" : False, "schedule" : [{"start" : "2200", "end" : "0400", "amps" : 32}] },
            "switch" : { "enabled" : True, "on" : True, "amps" : 32 },
            "configserver": { "enabled": True, "port": 80, "charger_name" : "openeo Charger", "charger_id" : "openeo_1" },
            "chargeroptions" : { "mode" : "manual" },
            "logger": {
                "enabled": True,
                "hires_interval": 2,        # 2 seconds
                "hires_maxage": 60*10,      # 10 minutes
                "lowres_interval": 60*5,    # 5 minutes
                "lowres_maxage": 60*60*48   # 48 hours
            },
        }
        open(filename, "w").write(json.dumps(myConfig, indent=2))
        return(myConfig)


#################################################################################
# Main Program

def main():    
    charger = openeoChargerClass()
    config_file_modification = 0
    import importlib

    # "globalConfig" is the entire configuration file
    globalConfig=readConfiguration(globalState.stateDict["eo_config_file"])
    if globalConfig is None:
        # No configuration, likely due to JSON error, which has already been reported
        # Probably best just to exit.
        _LOGGER.error("Aborting")
        exit(1)
        
    # Set logging level from config file.  Use the common dict to look up log levels to 
    # avoid a possible eval exploit from crafted config json.
    logLevel = str(globalConfig["chargeroptions"].get("log_level","info")).upper()

    if logLevel in logging._nameToLevel:
        _LOGGER.setLevel(logging._nameToLevel[logLevel])
    else:
        _LOGGER.error("Invalid log level "+logLevel+"in config file - ignoring")

    # Main loop
    loop = 0
    globalState.stateDict["_moduleDict"]={}
    while True:
        _LOGGER.debug("-- START LOOP --")

        # Check and reload config, if necessary
        new_config_file_modification = os.path.getmtime(globalState.stateDict["eo_config_file"])

        # Reload Schedule from file
        if new_config_file_modification > config_file_modification:
            _LOGGER.info("Reload Config File: "+globalState.stateDict["eo_config_file"])

            # Config file has changed, so we need to reload
            newGlobalConfig=readConfiguration(globalState.stateDict["eo_config_file"])
            if newGlobalConfig is None:
                # No configuration, likely due to JSON error, which has already been reported
                _LOGGER.error("Ignoring contents of configuration file %s",globalState.stateDict["eo_config_file"])
            else:
                #########################################
                # Make the newly read configuration active and take any reconfiguration actions necessary
                globalConfig=newGlobalConfig

                config_file_modification = new_config_file_modification

                for modulename, pluginConfig in globalConfig.items():
                    # Modue should be enabled
                    if modulename in globalState.stateDict["_moduleDict"]:
                        # Module already loaded, so just configure it
                        _LOGGER.info("Configuring %s with %s",modulename,pluginConfig)
                        globalState.stateDict["_moduleDict"][modulename].configure(pluginConfig)
                    else:
                        _LOGGER.info("Initialising %s",modulename)

                        try:
                            # module is in configfile, but not running - we need to instantiate it
                            moduleClass=getattr(importlib.import_module("lib."+modulename),modulename+"ClassPlugin")
                            # instantiate an object, configure it, and add to the list of active modules
                            mod = moduleClass(pluginConfig)
                            mod.configure(pluginConfig)
                            globalState.stateDict["_moduleDict"][modulename] = mod
                        except ImportError as e:
                            _LOGGER.error("Aborting - Module '%s' defined and enabled in config file but could not be imported - %s" % (modulename, repr(e)))
                        except Exception as e:
                            _LOGGER.error("Aborting - Module '%s' defined and enabled in config file but another error occurred loading  - %s" % (modulename, repr(e)))

                # Do we have any modules that are currently loaded, but not in the configfile
                # file (for example, perhaps the config file has been updated to remove one)
                for modulename,module in globalState.stateDict["_moduleDict"].copy().items():
                    if not modulename in globalConfig:
                        # module has recently been disabled in configfile, so unload
                        _LOGGER.info("Unloading %s",modulename)
                        del globalState.stateDict["_moduleDict"][modulename]


        # Take any action necessary - the module poll() function should return a numeric value
        # the maximum value returned by any module will be the max amp setting for the charger
        # If all modules return 0, then the charger will be set to "off"
        globalState.stateDict["eo_amps_requested"] = 0
        
        for modulename,module in globalState.stateDict["_moduleDict"].items():
            if module.get_config().get("enabled", True):
                globalState.stateDict["eo_amps_requested"] = max(globalState.stateDict["eo_amps_requested"],module.poll())
                _LOGGER.debug("polled "+modulename+" max_amps_requested="+str(globalState.stateDict["eo_amps_requested"]))
        
        if globalState.stateDict["eo_always_supply_current"]:
            globalState.stateDict["eo_amps_requested"] = 32
        
        globalState.stateDict["eo_amps_requested"] = min(globalState.stateDict["eo_overall_limit_current"], globalState.stateDict["eo_amps_requested"])
        
        _LOGGER.info("Amps Requested: %d amps (overall limit: %d amps, always supply: %r)" % \
            (int(globalState.stateDict["eo_amps_requested"]), globalState.stateDict["eo_overall_limit_current"], globalState.stateDict["eo_always_supply_current"]))

        # In order for us to find the status of the charger (e.g. whether a car is connected), we
        # need to set the amp limit first as part of the request. Action may be taken off the back of that 
        # status on the next iteration (e.g. if the car is unplugged, then we'll need to wait for the next
        # iteration to set amps_limit to zero)
        try:
            _LOGGER.debug("Setting amp limit: %d" % globalState.stateDict["eo_amps_requested"])
            result = charger.set_amp_limit(globalState.stateDict["eo_amps_requested"])
        except:
            _LOGGER.exception("Problem getting result from serial command: ("+str(result)+")")
            result = None

        # decode the charger status
        if result != None:
            # Perhaps stupidly, we've already stripped off the prefix, which puts the positions
            # for slicing the result string out by one, so let's put that prefix back on..
            result="!"+result
            try:
                # Live voltage is in hex, and seems to be peak to peak
                # Convert to int, divide by 2, then by sqrt(2) to get RMS
                # Apply a correction factor of ~0.77 to get correct-ish value
                globalState.stateDict["eo_live_voltage"] = round(
                    (
                    int(result[13:16], 16)
                    / 2
                    / math.sqrt(2)
                    * 0.776231001
                    ),
                    2,
                )
                globalState.stateDict["eo_p1_current"] = round(int(result[67:70], 16) / 10, 2)
                globalState.stateDict["eo_power_delivered"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_p1_current"]) / 1000, 2)        # P=VA
                globalState.stateDict["eo_power_requested"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_amps_requested"]) / 1000, 2)    # P=VA
                globalState.stateDict["eo_mains_frequency"] = int(result[22:25], 16)
                globalState.stateDict["eo_charger_state_id"] = int(result[25:27], 16)
                globalState.stateDict["eo_charger_state"] = openeoChargerClass.CHARGER_STATES[globalState.stateDict["eo_charger_state_id"]]
            except ValueError:
                _LOGGER.exception("Problem decoding status: ("+str(result)+")")

            # If we are ready to charge (that is, there is a cable/car connected), and there is demand from the 
            # modules, then raise the Amp limit to the maximum requested by the modules
            if (globalState.stateDict["eo_charger_state"] == "charge-unknown-state" or 
                globalState.stateDict["eo_charger_state"] == "charging" or 
                globalState.stateDict["eo_charger_state"] == "car-connected" or 
                globalState.stateDict["eo_charger_state"] == "plug-present") and (globalState.stateDict["eo_amps_requested"] > 0):
                globalState.stateDict["eo_amps_limit"]=globalState.stateDict["eo_amps_requested"]
            else:
                globalState.stateDict["eo_amps_limit"]=0
            _LOGGER.debug("Amps Limit: "+str(globalState.stateDict["eo_amps_limit"])+"A")
            
        else:
            _LOGGER.debug("Ignoring State Update, we probably had a serial overrun")

        # Measure Pi CPU temperature. This is returned via OCPP and might be exposed in other interfaces later.
        # I'm not sure how useful this is, but presumably on a hot day under high CPU load whilst charging, 
        # the CPU temperature could be something to be concerned about.
        #
        # Pi Zero is max 85C and I found at room temperature it runs at 51C already, so max ambient (inside EO Pro 
        # case, which is a nice black body) may be only 55C.  That feels achieveable in the summer sun, even in 
        # good old England, so something to watch out for. 
        #
        # We only measure temperature every 5 loops.
        if (loop % 5) == 0:
            try:
                temp_str = subprocess.check_output("vcgencmd measure_temp", shell=True)
                temp_str = temp_str.decode('ascii').strip()
                parts = temp_str.split('=')
                temp_val = float(parts[1].rstrip("'C"))
                globalState.stateDict["cpu_temperature"] = temp_val
            except Exception as e:
                _LOGGER.warning("Couldn't measure Pi temperature: %r" % e)
                globalState.stateDict["cpu_temperature"] = -999
        
        globalState.stateDict["eo_connected_to_controller"] = charger.connected
        
        # Notify submodules about new state.  Not all modules want to hear about state changes.
        # @TODO: actually -track- changes and only generate an event when something relevant changes
        for module,modulename in globalState.stateDict["_moduleDict"].items():
            try:
                getattr(module, "sync_state")
            except AttributeError:
                pass
            else:
                module.sync_state(globalState.stateDict)

        time.sleep(1)
        loop += 1

#################################################################################
# Initialisation

if __name__ == "__main__":
    # create Syslog and Console handlers
    syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
    syslog_handler.setFormatter(
        logging.Formatter(
            "openeo: %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            "openeo: %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
    )

    # Defaults to INFO level, but can be overridden in config.json
    logging.basicConfig(level=logging.INFO, handlers=[syslog_handler, console_handler])

    # logging for use in this module
    _LOGGER = logging.getLogger(__name__)
    
    _LOGGER.info("Starting openeo main loop")
    main()  # Run the main program
