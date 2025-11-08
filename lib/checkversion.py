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
from urllib.request import urlopen

from lib.PluginSuperClass import PluginSuperClass



# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class checkversionClassPlugin(PluginSuperClass):
    PRETTY_NAME = "CheckVersion"
    GITHUB_REPO = "minceheid/openeo"

    CORE_PLUGIN = True  
    pollfrequency = 12 * 60 * 24 * 7  # Check version once a week 
                                      # (assumes a 5 second main loop, so in reality will be slightly more than a week)

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

        # Fetch releases from github
        try:
            URL=f"https://api.github.com/repos/{self.GITHUB_REPO}/releases"
            github_releases=self.fetch_json(URL)
            
            for release in github_releases:
                releases.append(release["name"])

        except:
            print(f"Github API call to {URL} failed.. ignoring version check")
            releases.append("Unknown")

        return releases
