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
import json,hashlib
import globalState
import re
from lib.PluginSuperClass import PluginSuperClass
from openeoCharger import openeoChargerClass


# logging for use in this module
_LOGGER = logging.getLogger(__name__)


#################################################################################
class loggerClassPlugin(PluginSuperClass):
    pretty_name = "Data Logger"
    CORE_PLUGIN = True # Can't be disabled from the UI 
    pluginParamSpec={"enabled": {"type":"bool","default":True},
		"hires_interval": {"type":"int","default":5},
		"hires_maxage": {"type":"int","default":60*60},
		"lowres_interval": {"type":"int","default":5*60},
		"lowres_maxage": {"type":"int","default":60*60*48}}

    nextDatapoint=None
    nextWrite=None

    # The logger is a special case. We want the data to be recorded after all adjustments
    # have been made, and after all other modules have had a turn to speak, so we don't
    # do anything on the normal poll() method, but instead have a late_poll() method
    # that is called at the end of the main loop
    def late_poll(self):
        if datetime.now()>self.nextDatapoint:
            # Time to record 
            globalState.stateDict["_dataLog"].push(globalState.stateDict)
            self.nextDatapoint=self.nextDatapoint+timedelta(seconds=self.pluginConfig["hires_interval"])


        if datetime.now()>self.nextWrite:
            # Time to record - once every sixty seconds
            globalState.stateDict["_dataLog"].write()
            self.nextWrite=self.nextWrite+timedelta(seconds=60)


        return 0

    def __init__(self,configParam):
        super().__init__(configParam)

        self.nextDatapoint=datetime.now()
        self.nextWrite=datetime.now()

        # Create data buffer. The dict in the intitialiser is a lookup of globalState.stateDict{} keys and 
        # friendly names for that metric that will be used in creating the data for any
        # charts requested
        globalState.stateDict["_dataLog"]=databufferClass(self.pluginConfig,{
                                                    "eo_amps_requested_solar":"Solar Current Requested (A)",
                                                    "eo_amps_requested_grid":"Grid Current Requested (A)",
                                                    "eo_amps_requested_site_limit":"Current limited by Site Settings (A)",
                                                    "eo_amps_requested":"Current Requested (A)",
                                                    "eo_amps_requested_moving_average":"Current Requested Avg (A)",
                                                    "eo_amps_delivered":"Current Delivered (A)",
                                                    "eo_power_requested_solar":"Solar Power Requested (kW)",
                                                    "eo_power_requested_grid":"Grid Power Requested (kW)",
                                                    "eo_power_requested_site_limit":"Power limited by Site Settings (kW)",
                                                    "eo_power_requested":"Power Requested (kW)",
                                                    "eo_power_delivered":"Power Delivered (kW)",
                                                    "eo_charger_state_id":"Charger State",
                                                    "eo_current_site":"Site Import Current (A)",
                                                    "eo_current_vehicle":"Vehicle Supply Current (A)",
                                                    "eo_current_solar":"Solar Generation Current (A)",
                                                    "eo_current_raw_site":"Site Import Current (A)",
                                                    "eo_current_raw_vehicle":"Vehicle Supply Current (A)",
                                                    "eo_current_raw_solar":"Solar Generation Current (A)",
                                                    "eo_live_voltage":"Voltage (V)",
                                                    "sys_cpu_temperature":"CPU Temperature (C)",
                                                    "sys_1m_load_average":"System Load Average",
                                                    "sys_free_memory":"Free Memory (MB)",
                                                    "sys_available_memory":"Available Memory (MB)",
                                                    "eo_serial_errors":"Serial Errors",
                                                    "sys_wifi_strength":"WiFi Strength (%)",
                                                    })


#################################################################################
class databufferClass:
    databuffer={}

    def __str__(self):
        return json.dumps(self.databuffer,default=str)
    
    def get_plotly(self,since=None,seriesList=None,subplot_index=None):
        # Returns data in a format compatile with the Plotly Javascript library for
        # rendering a chart. If multiple charts are required, then it can automatically
        # generate subplots, but an implementation limitation is that at least one
        # of the subplots must have a colon separator.. even if there is only one series
        # in the subplot..
        # spec format example
        #  url='/getchartdata?type=plotly&series=eo_charger_state_id,eo_amps_requested_solar:eo_amps_requested_grid:eo_amps_requested_site_limit:eo_amps_requested:eo_amps_delivered,eo_current_vehicle:eo_current_site:eo_current_solar';
        # Subplots are separated by colons, and the series within a subplot by commas.
        
        myData=self.get_data(since,seriesList)

        using_subplots=False

        # Check to see if we are using any subplots anywhere
        if seriesList is not None:
            for index,series in enumerate(seriesList):
                if re.search(":",series):
                    #seriesList[index]=series.split(":")
                    using_subplots=True

        series=[]

        if not using_subplots:

            for key,value in myData.items():
                if key!="time" and (seriesList is None or key in seriesList):
                    if key=="eo_charger_state_id":

                        # Generate annotations for state_id chart
                        text=[]
                        last_datum=None
                        for datum in value:
                            if datum==last_datum:
                                text.append(None)
                            else:
                                text.append(openeoChargerClass.CHARGER_STATES[datum])
                            last_datum=datum

                        series.append({
                            "type": "line",
                            "line": {"shape": 'hv'},
                            "mode": "lines+text",
                            "name": self.seriesDict[key],
                            "key": key,
                            "stackgroup": None,
                            "x": myData["time"],
                            "y": value,
                            "textposition":"top center",
                            "text": text,
                            "legend" : f"legend1" if subplot_index is None else f"legend{subplot_index}",
                            "legendgroup" : "1" if subplot_index is None else f"{subplot_index}",
                            "xaxis" : "x" if subplot_index is None else f"x{subplot_index}",
                            "yaxis" : "y" if subplot_index is None else f"y{subplot_index}" })
                            
                    else:
                        series.append({
                            "type": "line",
                            "mode": "lines",
                            "name": self.seriesDict[key],
                            "key": key,
                            "stackgroup": None,
                            "x": myData["time"],
                            "y": value,
                            "legend" : f"legend1" if subplot_index is None else f"legend{subplot_index}",
                            "legendgroup" : "1" if subplot_index is None else f"{subplot_index}",
                            "xaxis" : "x" if subplot_index is None else f"x{subplot_index}",
                            "yaxis" : "y" if subplot_index is None else f"y{subplot_index}" })
                        
        else:
            for index,subplot in enumerate(seriesList):
                mylist=subplot.split(":")
                series.extend(self.get_plotly(since,mylist,index+1))


        return series


    def get_data(self,since=None,seriesList=None):
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

            # we always want to retrieve the last two, so that we can detect any state changes.
            # this might result in duplicate datapoints, but I don't think this is a big issue
            i=i-1

            # We want to count from the end of the list, so    
            i=len(self.databuffer["time"])-i-1

        newdatabuffer={}

        for key,value in self.databuffer.items():
            if seriesList is None or key in seriesList or key=="time":
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

    def write(self):
        # Writes databuffer to the config database
        globalState.configDB.set("logger","_loggerFingerpint",self.fingerprint,triggerModuleReonfigure=False)
        globalState.configDB.set("logger","_loggerData",json.dumps(self.databuffer,default=str),triggerModuleReonfigure=False)

    def __init__(self,config,seriesDict):
        self.config=config
        self.seriesDict=seriesDict

        # We were previously storing data in these, but moved them to underscore prefix so that they weren't transmitted on 
        # every /getconfig, so best that we delete the old data from the database, if it exists. We'll be able to remove 
        # this in a few versions time.
        
        globalState.configDB.delete("logger","loggerFingerpint")
        globalState.configDB.delete("logger","loggerData")

        # We use the fingerprint to determine whether the current set of fields being logged
        # matches those that are stored persistently. If it does, then we can load the persistent
        # record into the dict, if it does not, then we need to start from an empty databuffer.
        separator=":"
        string=separator.join(seriesDict) 

        self.fingerprint=hashlib.md5(string.encode()).hexdigest()
        lastfingerprint=globalState.configDB.get("logger","_loggerFingerpint","")

        # calculate the number of datapoints
        datapoints=round(config["hires_maxage"]/config["hires_interval"]) + \
            round((config["lowres_maxage"]-config["hires_maxage"])/config["lowres_interval"])
        
        if (self.fingerprint==lastfingerprint):
            # Load data from config
            try:
                self.databuffer=json.loads(globalState.configDB.get("logger","_loggerData",""))
                # re-encode time data as time objects, because we serialise them as strings when we save it
                for i,timeValue in enumerate(self.databuffer["time"]):
                    if isinstance(self.databuffer["time"][i],str):
                        self.databuffer["time"][i]=datetime.fromisoformat(timeValue)
            except:
                pass
        
        if len(self.databuffer)==0:
            # Construct the databuffer
            self.databuffer["time"]=[None] * datapoints
            for series in seriesDict:
                self.databuffer[series]=[None] * datapoints
        
        # find ratio of hires/lowres
        self.ratio=self.config["lowres_interval"]/self.config["hires_interval"]
        # find hires/lowres boundary
        self.resolution_boundary=datapoints-int(self.config["hires_maxage"]/self.config["hires_interval"])

        # datapoint count
        self.count=0
