#################################################################################
"""
OpenEO Module: wifi_health
Reads the Wi-Fi health status written by the root Wi-Fi watchdog and publishes it
in stateDict (so /getstatus, the portal UI, the cloud proxy and Home Assistant see
it). Changes are written to the App Events log.

poll() never raises: a problem here must not become a new failure mode in the charger app.
"""
#################################################################################

import logging, time
import globalState

from lib.PluginSuperClass import PluginSuperClass
from lib import wifi_status

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class wifi_healthClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Wi-Fi Health"

    CORE_PLUGIN = True
    pollfrequency = 2  # main loop runs every 5 s, so about every 10 s

    prev = None  # the last known (not unknown) status

    def poll(self):
        try:
            cur = wifi_status.read_status(wifi_status.STATUS_FILE, time.time())
            globalState.stateDict.update(wifi_status.state_fields(cur))
            for line in wifi_status.log_lines(self.prev, cur):
                globalState.configDB.logwrite(line)
            if cur.get("level") != "unknown":
                self.prev = cur     # the last known status, compared with after an unknown gap
        except Exception as e:
            _LOGGER.warning("wifi_health poll failed: %r" % e)
        return 0
