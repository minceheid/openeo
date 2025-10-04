#################################################################################
"""
OpenEO Module: CheckVersion
A module to periodically check the running release against the latest that is on
GitHub.

"""
#################################################################################

import logging,time
import globalState
import json
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

from lib.PluginSuperClass import PluginSuperClass



# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class checkversionClassPlugin(PluginSuperClass):
    PRETTY_NAME = "CheckVersion"
    GITHUB_REPO = "minceheid/openeo"

    CORE_PLUGIN = True  
    pollfrequency = 1000  # Check version every 1000 iterations of the main loop

    def poll(self):
        latest_release=self.get_releases()[0]
        globalState.stateDict["openeo_last_version_check"]=str(time.time())
        globalState.stateDict["openeo_latest_version"]=latest_release
        
        return 0
    

    def fetch_json(self,url: str) -> dict:
        """Fetch and parse JSON from a URL."""
        with urlopen(url) as response:
            return json.load(response)
 

    def get_releases(self) -> list[str]:
        """Return a list of valid release tags from the GitHub repository."""
        releases = []

        # Fetch releases 
        for release in self.fetch_json(f"https://api.github.com/repos/{self.GITHUB_REPO}/releases"):
            releases.append(release["name"])

        return releases