#!/usr/bin/env python3
"""
MIT License

Copyright (c)2025 mike@scott.land and contributors

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
import logging,numbers,copy,statistics
import logging.handlers
import time, math, datetime
import importlib
import psutil

import globalState, util
from openeoCharger import openeoChargerClass

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

# Main Program

def main():    
    charger = openeoChargerClass()
        
    _LOGGER.setLevel(logging.WARNING)

    globalState.configDB.logwrite(f"+++++ startup:{globalState.stateDict['app_version']} directory:{globalState.stateDict['app_deploy_directory']}")

    # Make a snapshot of the stateDict for the configserver module to refer to
    globalState.stateSnapshot=copy.copy(globalState.stateDict)

    # Main loop
    loop = 0
    lastloop=datetime.datetime.now()
    globalState.stateDict["_moduleDict"]={}

    # For keeping track of the moving average of requested charging rate
    smooth_requested_amps=[0]*9

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
                    # Sanitize sensitive config for logging
                    safe_config = pluginConfig.copy()
                    if modulename == "homeassistant" and isinstance(safe_config, dict):
                        if "mqtt_password" in safe_config:
                            safe_config["mqtt_password"] = "***"
                        if "mqtt_username" in safe_config:
                            safe_config["mqtt_username"] = "***"
                    _LOGGER.info("Configuring %s with %s", modulename, safe_config)
                    globalState.stateDict["_moduleDict"][modulename].configure(pluginConfig)
                else:
                    _LOGGER.info("openeo initialising %s",modulename)

                    try:
                        # module is in configfile, but not running - we need to instantiate it
                        moduleClass=getattr(importlib.import_module("lib."+modulename),modulename+"ClassPlugin")
                        # instantiate an object, configure it, and add to the list of active modules
                        mod = moduleClass(pluginConfig)
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
        globalState.stateDict["eo_amps_requested_grid"] = 0
        globalState.stateDict["eo_amps_requested_solar"] = 0
        globalState.stateDict["eo_amps_requested_site_limit"] = 0
        

        for module_name, module in globalState.stateDict["_moduleDict"].items():
            if module.get_config().get("enabled", True):
                if module.pollfrequency>0 and (loop % module.pollfrequency) == 0:
                    if callable(getattr(module,"poll",None)):
                        # Get the current from a module, whilst ensuring that it's an integer,
                        # and also between 0>=x>=32
                        module_current = max(min(int(module.poll()),32),0)

                        # This check is entirely aesthetic - it's not required for correct behaviour of the charger
                        # but including it will ensure that the charts on the statistics page reflect what the charger
                        # is actually doing.
                        
                        if module_current<6:
                            module_current=0

                        globalState.configDB.logwrite(f"module:{module_name} current:{module_current}")
                        if (not isinstance(module_current, numbers.Number)):
                            _LOGGER.error(f"ERROR: Module {module} returned "+str(type(module_current))+"- Ignoring")
                        else:
                            globalState.stateDict["eo_amps_requested"] = max(globalState.stateDict["eo_amps_requested"], module_current)

                            #if module_name=="loadmanagement":
                            #    globalState.stateDict["eo_amps_requested_solar"] = max(globalState.stateDict["eo_amps_requested_solar"], module_current)

                            _LOGGER.debug("polled %s, amps_requested=%d" % (module_name, module_current))
        
        if globalState.stateDict["eo_always_supply_current"]:
            globalState.stateDict["eo_amps_requested"] = 32
        
        globalState.stateDict["eo_amps_requested"] = min(globalState.stateDict["eo_overall_limit_current"], globalState.stateDict["eo_amps_requested"])
        
        _LOGGER.info("Amps Requested: %d amps (overall limit: %d amps, always supply: %r), Charger State: %s" % \
            (int(globalState.stateDict["eo_amps_requested"]), globalState.stateDict["eo_overall_limit_current"], globalState.stateDict["eo_always_supply_current"],
             globalState.stateDict["eo_charger_state"]))

        #############
        # Global Load Management Logic 
        # This is the final thing done before we set the amp limit

        if "loadmanagement" in globalState.stateDict["_moduleDict"]:
            lm_config=globalState.stateDict["_moduleDict"]["loadmanagement"].pluginConfig
            ############
            # Handle Limiting for Load Management CT data
            site_limit_current=lm_config.get("site_limit_current",60)

            # We need to account for any power that the EO charger is currently drawing.
            ct_vehicle=globalState.stateDict['eo_current_vehicle']
            ct_site=globalState.stateDict['eo_current_site']

            non_eo_current_usage=round(ct_site-ct_vehicle,2)

            # Calculate the available current. This might be a negative number!
            available_current=int(site_limit_current - non_eo_current_usage)

            globalState.configDB.logwrite(f"site_limit_current={site_limit_current} site_ct={ct_site} vehicle_ct={ct_vehicle} non_eo_current_usage={non_eo_current_usage} available_current={available_current} amps_requested={globalState.stateDict['eo_amps_requested']}")
            if globalState.stateDict["eo_amps_requested"]>available_current:
                globalState.configDB.logwrite(f"CT - site limit active (available_current={available_current})")
                # Site load is too high - we need to reduce
                globalState.stateDict["eo_amps_requested_site_limit"] = globalState.stateDict["eo_amps_requested"] - available_current
                # If available_current is a negative number, we need to ensure that it is stored as zero, so that we're not doing something daft.
                globalState.stateDict["eo_amps_requested"]=max(0,available_current)

        ###############
        # Load smoothing
        # For rapidly changing eo_amps_requested (which might be generated by solar or load balancing),
        # we will generate a moving average over 45 seconds (9 cycles). This is intended to avoid rapidly cycling
        # values.

        smooth_requested_amps.append(globalState.stateDict["eo_amps_requested"])
        del smooth_requested_amps[0]

        ###############

        # In order for us to find the status of the charger (e.g. whether a car is connected), we
        # need to set the amp limit first as part of the request. Action may be taken off the back of that 
        # status on the next iteration 
        try:
            moving_average=int(statistics.mean(smooth_requested_amps))
            globalState.stateDict['eo_amps_requested_moving_average']=moving_average
            _LOGGER.debug(f"Setting amp limit: {moving_average}")
            globalState.configDB.logwrite(f"site_ct={globalState.stateDict['eo_current_site']} vehicle_ct={globalState.stateDict['eo_current_vehicle']} solar_ct={globalState.stateDict['eo_current_solar']}")
            globalState.configDB.logwrite(f"sending amp limit={moving_average}")
            result = charger.set_amp_limit(moving_average)
        except:
            _LOGGER.error("Problem getting result from serial command: ("+str(result)+")")
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
            globalState.stateDict["eo_firmware_version"] = int(charger.version, 16)
            globalState.stateDict["eo_current_switch_setting"] = int(charger.current_switch_setting, 16)
            globalState.stateDict["eo_current_site"] = charger.current_site
            globalState.stateDict["eo_current_vehicle"] = charger.current_vehicle
            globalState.stateDict["eo_current_solar"] = charger.current_solar
            globalState.stateDict["eo_power_delivered"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_current_vehicle"]) / 1000, 2)        # P=VA
            globalState.stateDict["eo_mains_frequency"] = int(charger.mains_frequency, 16)
            globalState.stateDict["eo_charger_state_id"] = int(charger.charger_state, 16)
            globalState.stateDict["eo_charger_state"] = openeoChargerClass.CHARGER_STATES[globalState.stateDict["eo_charger_state_id"]]

            globalState.stateDict["eo_amps_requested_solar"] = min(globalState.stateDict["eo_current_solar"], globalState.stateDict["eo_amps_requested"])
            globalState.stateDict["eo_amps_requested_grid"] = globalState.stateDict["eo_amps_requested"] - globalState.stateDict["eo_amps_requested_solar"]

            globalState.stateDict["eo_power_requested"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_amps_requested"]) / 1000, 2)    # P=VA
            globalState.stateDict["eo_power_requested_solar"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_amps_requested_solar"]) / 1000, 2)    # P=VA
            globalState.stateDict["eo_power_requested_grid"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_amps_requested_grid"]) / 1000, 2)    # P=VA
            globalState.stateDict["eo_power_requested_site_limit"] = round((globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_amps_requested_site_limit"]) / 1000, 2)    # P=VA
            globalState.stateDict["eo_amps_delivered"] = round(((globalState.stateDict["eo_power_delivered"] * 1000) / globalState.stateDict["eo_live_voltage"]), 2)    # P=VA

            # Record the current time - this can be used to show on the web interface, to allow the user to confirm that the correct time is
            # visible for scheduling purposes
            myTime=time.localtime()
            globalState.stateDict["eo_localtime"] = f"{myTime.tm_hour:02}:{myTime.tm_min:02}"

            # After all adjustments have been made, record data for the logger
            if "logger" in globalState.stateDict["_moduleDict"]:
                globalState.stateDict["_moduleDict"]["logger"].late_poll()

            # And make a snapshot of the stateDict for the configserver module to refer to
            globalState.stateSnapshot=copy.copy(globalState.stateDict)

        else:
            _LOGGER.debug("Ignoring State Update, we probably had a serial overrun")

        # Housekeeping actions
        if (loop % 12) == 0:
            # Once a minute, purge the log table
            globalState.configDB.logpurge()
        #########
        # System Metrics
        globalState.stateDict["sys_available_memory"]=psutil.virtual_memory().available/1024/1024
        globalState.stateDict["sys_free_memory"]=psutil.virtual_memory().free/1024/1024
        globalState.stateDict["sys_1m_load_average"]=psutil.getloadavg()[1]
        
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

        time.sleep(5)
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
