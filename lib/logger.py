#################################################################################
"""
OpenEO Module: Logger
A module to implement the logging of operational metrics (e.g. power delivered)
Implemented with fixed size lists. At the moment it does not persist data through
reboots, but I expect this will come.

The interval (measured in minutes) can be configured in the config file, as can the
number of datapoints. Default is 5mins and 576 datapoints, for 48 hours of data.

If we have memory issues, we may need to take a different approach.

Configuration example:
"logger": {
    "enabled": True, 
    "hires_interval": 30, # 30 seconds
    "hires_maxage": 60*60, # 1 hour
    "lowres_interval": 5*60, # 5 mintues
    "lowres_maxage": 60*60*48 # 2 days
}

"""
#################################################################################

import logging
from datetime import datetime, timedelta
import json
import globalState
import re

# logging for use in this module
_LOGGER = logging.getLogger(__name__)


#################################################################################
class loggerClassPlugin: 
    pretty_name = "Data Logger"
    CORE_PLUGIN = True # Can't be disabled from the UI 
    pluginConfig={}
    myName=""
 #   myData=None
    nextDatapoint=None

    def __str__(self):
        return self.myName

    def get_config(self):
        return self.pluginConfig
        
    def configure(self,configParam):
        _LOGGER.debug("Plugin Configured: "+self.myName)

        if (not isinstance(configParam.get("hires_interval",0),(int))):
            del configParam["hires_interval"]
            _LOGGER.error("logger hires_interval parameter malformed ("+str(configParam["hires_interval"])+"). Ignoring and will use default value")
        if (not isinstance(configParam.get("hires_maxage",0),(int))):
            del configParam["hires_maxage"]
            _LOGGER.error("logger hires_maxage parameter malformed ("+str(configParam["hires_maxage"])+"). Ignoring and will use default value")
        if (not isinstance(configParam.get("lowres_interval",0),(int))):
            del configParam["lowres_interval"]
            _LOGGER.error("logger lowres_interval parameter malformed ("+str(configParam["lowres_interval"])+"). Ignoring and will use default value")
        if (not isinstance(configParam.get("lowres_maxage",0),(int))):
            del configParam["lowres_maxage"]
            _LOGGER.error("logger lowres_maxage parameter malformed ("+str(configParam["lowres_maxage"])+"). Ignoring and will use default value")

        self.pluginConfig["hires_interval"]=configParam.get("hires_interval",30)
        self.pluginConfig["hires_maxage"]=configParam.get("hires_maxage",60*60)
        self.pluginConfig["lowres_interval"]=configParam.get("lowres_interval",5*60)
        self.pluginConfig["lowres_maxage"]=configParam.get("lowres_maxage",60*60*48)
        
    def poll(self):
        if datetime.now()>self.nextDatapoint:
            # Time to record 
            globalState.stateDict["_dataLog"].push(globalState.stateDict)
            self.nextDatapoint=self.nextDatapoint+timedelta(seconds=self.pluginConfig["hires_interval"])

        return 0

    def __init__(self,configParam):
       # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        _LOGGER.debug("Initialising Module: "+self.myName)
        self.configure(configParam)        

        self.nextDatapoint=datetime.now()

        # Create data buffer. The dict in the intitialiser is a lookup of globalState.stateDict{} keys and 
        # friendly names for that metric that will be used in creating the data for any
        # charts requested
        globalState.stateDict["_dataLog"]=databufferClass(self.pluginConfig,{"eo_power_requested":"Power Requested (kW)",
                                                       "eo_power_delivered":"Power Delivered (kW)",
                                                       "eo_charger_state_id":"Charger State"})


#################################################################################
class databufferClass:
    databuffer={}

    def __str__(self):
        return json.dumps(self.databuffer,default=str)
    
    def get_plotly(self,since=None):
        myData=self.get_data(since)

        series=[]

        for key,value in myData.items():
            if key!="time":
                if key=="eo_charger_state_id":
                    series.append({
                        "type": "line",
                        "line": {"shape": 'hv'},
                        "mode": "lines",
                        "name": self.seriesDict[key],
                        "x": myData["time"],
                        "y": value})
                else:
                    series.append({
                        "type": "line",
                        "mode": "lines",
                        "name": self.seriesDict[key],
                        "x": myData["time"],
                        "y": value})

        return series


    def get_data(self,since=None):
        # Get and return raw data, with optionally providing a subset based on time.
        # the idea there is to allow dynamic updates to a chart, without having to transfer
        # the whole dataset on each update. The javascript could poll based on the maximum
        # time value that it knows about, and request additional datapoints on a regular interval
        
        i=None

        if since==None:
            # Retrieving all datapoints, so look for the first non-null data point and send
            # all following data points.
            i=0
            while (i<len(self.databuffer["time"]) and self.databuffer["time"][i]==None):
                i=i+1

            # We want to count from the end of the list, so    
            i=len(self.databuffer["time"])-i

        else:
            # We only want to send the data since the time specified, so locate the 
            # list element that we're interested in
            i=len(self.databuffer["time"])-1
            while (i>=0 and self.databuffer["time"][i]!=None and self.databuffer["time"][i]>since):
                i=i-1

            # We want to count from the end of the list, so    
            i=len(self.databuffer["time"])-i-1

        newdatabuffer={}

        for key,value in self.databuffer.items():
            newdatabuffer[key]=[] if i==0 else value[-i:]   # [-0:] will return whole list, so if required
                                                            # to return an empty list here 

        return newdatabuffer

        


    def push(self,datapoint):
        # datapoint is a dict containing one value per dataseries to store
        # it is important that we store one point for all series.

        # Only 1:n datapoints should be deleted from the head of the data structure
        # the remainder should be deleted from the hires/lowres boundary, so we use the
        # datapoint number and the ratio between hires/lowres to calculate which to delete
        modulus=self.count%self.ratio

        #if self.databuffer["time"][self.resolution_boundary] is None:
        #    # We haven't got enough data to care, so simply delete fifo
        #    deletion_index=0
        #elif modulus==0:
        #    deletion_index=0
        #else:
        #    deletion_index=self.resolution_boundary

        deletion_index=(self.count%self.ratio!=0)*self.resolution_boundary

        for key in self.databuffer:

            if (key=="time"):
                self.databuffer["time"].append(datetime.now())
                del self.databuffer["time"][deletion_index]
            elif (key in datapoint) and (isinstance(datapoint[key],(int,float))):

                self.databuffer[key].append(datapoint[key])
                del self.databuffer[key][deletion_index]
            else:
                self.databuffer[key].append(None)
                del self.databuffer[key][deletion_index]
        self.count=self.count+1

    def __init__(self,config,seriesDict):
        self.config=config
        self.seriesDict=seriesDict
        # calculate the number of datapoints
        datapoints=round(config["hires_maxage"]/config["hires_interval"]) + \
            round((config["lowres_maxage"]-config["hires_maxage"])/config["lowres_interval"])

        # Construct the datastore
        self.databuffer["time"]=[None] * datapoints
        for series in seriesDict:
            self.databuffer[series]=[None] * datapoints

        
        # find ratio of hires/lowres
        self.ratio=self.config["lowres_interval"]/self.config["hires_interval"]
        # find hires/lowres boundary
        self.resolution_boundary=datapoints-int(self.config["hires_maxage"]/self.config["hires_interval"])

        # datapoint count
        self.count=0