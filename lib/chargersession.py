#################################################################################
"""
OpenEO Module: Charger Session


"""
#################################################################################

from lib.PluginSuperClass import PluginSuperClass
import globalState
import datetime,time
import sqlite3,logging,re
from threading import Lock


# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class chargersessionClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Session"
    CORE_PLUGIN = True  
    pluginParamSpec={ "enabled": {"type": "bool","default": True},
			"tariff": {
                "type": "json",
                "default":'[{"start": "0000", "end": "0029", "cost": 0.27048},{"start": "0030", "end": "0529", "cost": 0.04998},{"start": "0530", "end": "2359", "cost": 0.27048}]'}}
            
    lastloop=datetime.datetime.now()

    SESSION_DB_FILE="/home/pi/etc/session.db"
    # The three SESSION_TABLE references are different versions of the 
    # session table schema. When a new schema version is required, the startup will
    # create the table, migrate the old data, and drop the old table. So far I've been supporting
    # n-1 data migration, meaning that if the v1 schema was in use at the moment, and the
    # software updated to latest, the v3 table would be created, and there would be no data migration
    # so that the session log would be empty. The old v1 schema would not be dropped.
    SESSION_TABLE="session"
    SESSION_TABLE_2="session2"
    SESSION_TABLE_3="session_v3"
    SESSION_TABLE_4="session_v4"
        
    def reset_session(self):
        # Reset all session counters
        globalState.stateDict["eo_session_joules"]=0
        globalState.stateDict["eo_session_kwh"]=0
        globalState.stateDict["eo_session_seconds_charged"]=0
        globalState.stateDict["eo_session_cost"]=0
        globalState.stateDict["eo_session_timestamp"]=int(time.time())

        # store tariff data for the session log, so that we can calculate the cost of the session as it progresses.
        # This is required because the tariff may change during a session, and we need to be able to calculate the
        # cost of the session accurately. We store this in a list of dicts, with each dict containing the start and 
        # end time of the tariff, the cost of the tariff, and the number of joules charged during that tariff period. 
        # This allows us to calculate the cost of the session accurately even if the tariff changes during the session.
        globalState.stateDict["session_tariff"]=[]
        for x in self.pluginConfig.get("tariff",[]):
            globalState.stateDict["session_tariff"].append({"start":x["start"],"end":x["end"],"cost":x["cost"],"joules":0})

    def poll(self):
        # If charger state indicates that the car might be disconnected, then
        # we reset the session kWh count, otherwise we calculate how many additional
        # joules have been added to the count
        
        # Test flag used for development testing. Set to False for production use
        # When set to True, then there will be repeated (fictonal) sessions generated
        # for the purpose of testing the logging mechanism
        
        TEST=False
        #TEST=True
        def testfunc():
            return ((int((datetime.datetime.now()).hour-1)/2)-1) % 2 == 0
        
        thisloop=datetime.datetime.now()
        if (TEST==True and testfunc==True) or \
            (TEST==False and globalState.stateDict["eo_charger_state_id"]<9): 

            self.reset_session()

            if (TEST==True):
                # Debug logging
                print(f"Sessionlog resetting {globalState.stateDict['eo_session_timestamp']}")

        else:
            secondsSinceLastLoop=(thisloop-self.lastloop).total_seconds()
            current_hhmm=self.timestamp_hhmm(int(time.time()))

            ## Production Routine
            # 1J = 1Ws = 1 x V * A * s
            # 1kWh = 3.6 million joules

            if (TEST==True):
                joulesThisLoop = int(globalState.stateDict["eo_live_voltage"] * 32 * secondsSinceLastLoop)
            else: 
                joulesThisLoop = int(globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_current_vehicle"] * secondsSinceLastLoop)

            globalState.stateDict["eo_session_joules"]+= joulesThisLoop
            for x in globalState.stateDict["session_tariff"]:
                if x["start"]<=current_hhmm<=x["end"]:
                    x["joules"]+=joulesThisLoop
                    break

            # If eo_current_vehicle is >=2, then the last cycle is counted against the number of seconds that this session has been actively
            # trying to charge
            if globalState.stateDict["eo_current_vehicle"]>=2 or TEST==True:
                globalState.stateDict["eo_session_seconds_charged"]+=secondsSinceLastLoop

            globalState.stateDict["eo_session_kwh"]= round(globalState.stateDict["eo_session_joules"] / 3600000,2)
            # Calculate cost of the session so far, by multiplying the joules charged during each tariff period by the cost of that tariff, 
            # and summing across all tariff periods.
            cost=0
            for x in globalState.stateDict["session_tariff"]:
                cost+=x["cost"] * (x["joules"] / 3600000)

            globalState.stateDict["eo_session_cost"]=round(cost,2)

            # Debug Logging
            if (TEST==True):
                print(f"Sessionlog accumulating {globalState.stateDict['eo_session_joules']}j {globalState.stateDict['eo_session_seconds_charged']}s £{globalState.stateDict['eo_session_cost']}")

            # Once a minute, we should write the current session information to the persistent log
            if (thisloop.minute>self.lastloop.minute):
                self.writesessionlog(globalState.stateDict["eo_session_timestamp"],globalState.stateDict["eo_session_joules"],globalState.stateDict["eo_session_seconds_charged"],globalState.stateDict["eo_session_cost"])

        # Reset the time counter for next time.
        self.lastloop=thisloop
        return 0

    # helper function for quickly finding the start of day.
    def timestamp_start_of_today(self):
        return int(datetime.datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    # helper function to convert a timestamp to text
    def timestamp_text(self,ts):
        value = datetime.datetime.fromtimestamp(ts)
        return(f"{value:%Y-%m-%d %H:%M:%S}")

    def timestamp_hhmm(self,ts):
        value = datetime.datetime.fromtimestamp(ts)
        return(f"{value:%H%M}")


    # Write session log to sqlite3 db
    def writesessionlog(self,timestamp,joules,seconds_charged,cost=0.0):
        with self.lock:
            now=int(time.time())
            sql=f'''REPLACE INTO {self.SESSION_TABLE_4} (first_timestamp, last_timestamp, day_timestamp, joules,seconds_charged, cost) \
VALUES ({timestamp}, {now}, {self.timestamp_start_of_today()}, {joules},{seconds_charged},{cost})
-- {self.timestamp_text(timestamp)} {self.timestamp_text(now)} {self.timestamp_text(self.timestamp_start_of_today())}'''
            #print(sql)
            self.cursor.execute(sql)
            self.conn.commit()
        globalState.configDB.logwrite(f"Sessionlog update {sql}")


    # Retrieve a dict of all sessions. This is used by the configserver for making this available via api
    def get_sessions(self):
        six_months_ago=int(time.time()) - 60*60*24*180
        with self.lock:
            # Only retrieve sizeable sessions to remove any noise from short term connections from plug/unplug
            self.cursor.execute(f"SELECT first_timestamp, last_timestamp, day_timestamp, joules, seconds_charged, cost FROM {self.SESSION_TABLE_4} where joules>1500000 and first_timestamp>{six_months_ago}")
            rows = self.cursor.fetchall()

        data=[]
        for x in rows:
            data.append({"first_timestamp":x[0],
               "last_timestamp":x[1],
               "day_timestamp":x[2],
               "joules":x[3],
               "seconds_charged":x[4],
               "cost":x[5]}
               )
        
        return data

    def __init__(self,configParam):
        super().__init__(configParam)

        # Reset session counters on startup, to ensure that we start with a clean session. This is important because 
        # if the software is restarted during a charging session, we don't want to carry over the old session data 
        # into the new session.
        self.reset_session()

        # Create mutex lock for protecting transactions - noting that the get_sessions() method will be called from
        # another thread in configserver.
        self.lock=Lock()

        # Initialize SQLite DB and table
        self.conn = sqlite3.connect(self.SESSION_DB_FILE, check_same_thread=False)
        self.conn.execute('pragma journal_mode=wal')

        self.cursor = self.conn.cursor()
        
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.SESSION_TABLE_4} (
                first_timestamp INTEGER NOT NULL,
                day_timestamp INTEGER NOT NULL,
                last_timestamp INTEGER,
                joules INTEGER NOT NULL,
                seconds_charged INTEGER NOT NULL,
                cost REAL NOT NULL,
                PRIMARY KEY (first_timestamp, day_timestamp)
            )
        ''')

        # v5.8 session log db format no longer supported for migration - installation will just create an empty log
        # v5.9 had a different format session table, so if it exists, then
        #      we migrate the data across to the new table and drop the old table
        with self.lock:
            try:
                sql=f"SELECT first_timestamp, last_timestamp, day_timestamp, joules, seconds_charged FROM {self.SESSION_TABLE_3}"
                self.cursor.execute(sql)
                rows = self.cursor.fetchall()
                print("Migrating v3 session log data")
                for x in rows:
                    now=datetime.datetime.fromtimestamp(x[0]).astimezone()
                    sql=f"REPLACE INTO {self.SESSION_TABLE_4} (first_timestamp, last_timestamp, day_timestamp, joules,seconds_charged,cost) VALUES ({x[0]}, {x[1]}, {x[2]}, {x[3]}, {x[4]},0.0)"
                    self.cursor.execute(sql)
                    #print(sql)

                self.cursor.execute(f"drop table {self.SESSION_TABLE_3}")
                self.conn.commit()
            except Exception as err:
                if re.search("^no such table:",str(err)):
                    # This is normal - there is no old format session table to migrate
                    pass
                else:
                    print("Error migrating old session data: ",err)

    def get_user_settings(self):
        return [{"type": "tariff", "name": "tariff", "label": "Tariff", "default":self.pluginConfig.get("tariff",""),"note":"Set the tariff for your electricity supply. The full 24 hour period must be specified with no gaps. The cost is measured per kWh. This control may be difficult to use on mobile devices - use from a larger screen if difficulty is experienced."}];
