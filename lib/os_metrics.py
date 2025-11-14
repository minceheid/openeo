#################################################################################
"""
OpenEO Module: os_metrics
A module to periodically check OS statistics that are not necessary to check every cycle

"""
#################################################################################

import logging,re,subprocess
import globalState
from urllib.request import urlopen

from lib.PluginSuperClass import PluginSuperClass



# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class os_metricsClassPlugin(PluginSuperClass):
    PRETTY_NAME = "OS_Statistics"

    CORE_PLUGIN = True  
    pollfrequency = 60/5  # Check version once a minute  

    def poll(self):


        globalState.stateDict["sys_cpu_temperature"]=self.get_temperature()
        globalState.stateDict["sys_wifi_strength"]=self.get_wifi_strength_percent()
        
        return 0
    

    def get_temperature(self):
    # Measure Pi CPU temperature. This is returned via OCPP and might be exposed in other interfaces later.
            # I'm not sure how useful this is, but presumably on a hot day under high CPU load whilst charging, 
            # the CPU temperature could be something to be concerned about.
            #
            # Pi Zero is max 85C and I found at room temperature it runs at 51C already, so max ambient (inside EO Pro 
            # case, which is a nice black body) may be only 55C.  That feels achieveable in the summer sun, even in 
            # good old England, so something to watch out for. 
            #
            # We only measure temperature every 5 loops.
            
            temp=-999
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = float(f.read().strip()) / 1000.0
            except Exception as e:
                _LOGGER.warning("Couldn't measure Pi temperature: %r" % e)
                temp = -999

            return(temp)
            
    def get_wifi_strength_percent(self,interface="wlan0"):
        """
        Returns WiFi signal strength as a percentage (0–100).
        Uses `iw` for accurate RSSI readings.
        """

        try:
            # Query link info
            result = subprocess.check_output(
                ["iw", interface, "link"], stderr=subprocess.STDOUT
            ).decode()

            # Look for "signal: -58 dBm"
            match = re.search(r"signal:\s*(-?\d+)\s*dBm", result)
            if not match:
                return None

            rssi = int(match.group(1))  # dBm

            # Convert RSSI → percentage
            #
            #  -30 dBm  = 100%
            #  -67 dBm  = 50%
            #  -90 dBm  = 0%
            #
            # Formula clamps values between -30 and -90.
            quality = 2 * (rssi + 90)  # scale to 0–120
            quality = max(0, min(100, int((quality / 120) * 100)))

            return quality

        except Exception as e:
            print("Error:", e)
            return None
