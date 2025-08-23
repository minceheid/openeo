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
import logging,numbers
import logging.handlers
import time, math
import importlib

import globalState, util
from openeoCharger import openeoChargerClass
from openeoConfig  import openeoConfigClass

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

# Main Program

def main():    
    charger = openeoChargerClass()
        
    # Set logging level from config file.  Use the common dict to look up log levels to 
    # avoid a possible eval exploit from crafted config json.
    logLevel = str(globalState.configDB.get("chargeroptions","log_level","info")).upper()

    if logLevel in logging._nameToLevel:
        _LOGGER.setLevel(logging._nameToLevel[logLevel])
    else:
        _LOGGER.error("Invalid log level "+logLevel+"in config file - ignoring")

    # Main loop
    loop = 0
    globalState.stateDict["_moduleDict"]={}
    while True:
        _LOGGER.debug("-- START LOOP --")

        if globalState.configDB.changed:
            _LOGGER.info("Configuration flagged as changed")
            # Reset the changed flag
            globalState.configDB.changed=False
            for modulename, pluginConfig in globalState.configDB.dict().items():
                # Modue should be enabled
                if modulename in globalState.stateDict["_moduleDict"]:
                    # Module already loaded, so just configure it
                    _LOGGER.info("Configuring %s with %s",modulename,pluginConfig)
                    globalState.stateDict["_moduleDict"][modulename].configure(pluginConfig)
                else:
                    _LOGGER.info("openeo initialising %s",modulename)

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
                if not modulename in globalState.configDB.dict().keys():
                    # module has recently been disabled in configfile, so unload
                    _LOGGER.info("Unloading %s",modulename)
                    del globalState.stateDict["_moduleDict"][modulename]


        # Take any action necessary - the module poll() function should return a numeric value
        # the maximum value returned by any module will be the max amp setting for the charger
        # If all modules return 0, then the charger will be set to "off"
        globalState.stateDict["eo_amps_requested"] = 0
        

        for module_name, module in globalState.stateDict["_moduleDict"].items():
            if module.get_config().get("enabled", True):
                module_current = module.poll()
                if (not isinstance(module_current, numbers.Number)):
                    _LOGGER.error(f"ERROR: Module {module} returned "+str(type(module_current))+"- Ignoring")
                else:
                    globalState.stateDict["eo_amps_requested"] = max(globalState.stateDict["eo_amps_requested"], module_current)
                    _LOGGER.debug("polled %s, amps_requested=%d" % (module_name, module_current))
        
        if globalState.stateDict["eo_always_supply_current"]:
            globalState.stateDict["eo_amps_requested"] = 32
        
        globalState.stateDict["eo_amps_requested"] = min(globalState.stateDict["eo_overall_limit_current"], globalState.stateDict["eo_amps_requested"])
        
        _LOGGER.info("Amps Requested: %d amps (overall limit: %d amps, always supply: %r), Charger State: %s" % \
            (int(globalState.stateDict["eo_amps_requested"]), globalState.stateDict["eo_overall_limit_current"], globalState.stateDict["eo_always_supply_current"],
             globalState.stateDict["eo_charger_state"]))

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

        if result:
            # Take values that have been recorded by the charger object, and squirrel them away in 
            # globalState.stateDict{}.

                        # Live voltage is in hex, and seems to be peak to peak
            # Convert to int, divide by 2, then by sqrt(2) to get RMS
            # Apply a default correction factor of ~0.77 to get correct-ish value. User can override this in config.json
            globalState.stateDict["eo_live_voltage"] = round(
                (
                int(charger.live_voltage, 16)
                / 2
                / math.sqrt(2)
                * float(globalState.configDB.get("chargeroptions","mains_voltage_correction", 0.776231001))
                ),
                2,
            )
            globalState.stateDict["eo__firmware_version"] = int(charger.version, 16)
            globalState.stateDict["eo_p1_current"] = round(int(charger.p1_current, 16) / 10, 2)
            globalState.stateDict["eo_p2_current"] = round(int(charger.p2_current, 16) / 10, 2)
            globalState.stateDict["eo_p3_current"] = round(int(charger.p3_current, 16) / 10, 2)
            globalState.stateDict["eo_power_delivered"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_p1_current"]) / 1000, 2)        # P=VA
            globalState.stateDict["eo_power_requested"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_amps_requested"]) / 1000, 2)    # P=VA
            globalState.stateDict["eo_mains_frequency"] = int(charger.mains_frequency, 16)
            globalState.stateDict["eo_charger_state_id"] = int(charger.charger_state, 16)
            globalState.stateDict["eo_charger_state"] = openeoChargerClass.CHARGER_STATES[globalState.stateDict["eo_charger_state_id"]]

            # If we are ready to charge (that is, there is a cable/car connected), and there is demand from the 
            # modules, then raise the Amp limit to the maximum requested by the modules
            # Note - we have had some unusual states reported here, preventing charging, so we are now checking
            # for state_id >= 5 to eliminate suspected error states, but to otherwise be permissive.
            if (globalState.stateDict["eo_charger_state_id"] >= 5) and (globalState.stateDict["eo_amps_requested"] > 0):
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
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp_val = float(f.read().strip()) / 1000.0
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
    #logging.basicConfig(level=logging.INFO, handlers=[syslog_handler, console_handler])
    # MMS: disabling console_handler as the journal is getting pretty noisy when running under
    # systemd
    logging.basicConfig(level=logging.INFO, handlers=[syslog_handler])

    # logging for use in this module
    _LOGGER = logging.getLogger(__name__)
    
    _LOGGER.info("Starting openeo main loop")
    main()  # Run the main program
