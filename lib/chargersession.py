#################################################################################
"""
OpenEO Module: Charger Session


"""
#################################################################################

from lib.PluginSuperClass import PluginSuperClass
import globalState
import datetime,time
import sqlite3,logging
from threading import Lock


# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class chargersessionClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Session"
    CORE_PLUGIN = True  
    pluginParamSpec={}
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
        
    def poll(self):
        # If charger state indicates that the car might be disconnected, then
        # we reset the session kWh count, otherwise we calculate how many additional
        # joules have been added to the count
        
        # Test flag used for development testing. Set to False for production use
        # When set to True, then there will be repeated (fictonal) sessions generated
        # for the purpose of testing the logging mechanism
        TEST=False
        def testfunc():
            return ((int((datetime.datetime.now()).hour-1)/2)-1) % 2 == 0
        
        thisloop=datetime.datetime.now()
        if (TEST==True and testfunc==True) or \
            (TEST==False and globalState.stateDict["eo_charger_state_id"]<9): 

            # Reset all session counters
            globalState.stateDict["eo_session_joules"]=0
            globalState.stateDict["eo_session_kwh"]=0
            globalState.stateDict["eo_session_seconds_charged"]=0
            globalState.stateDict["eo_session_timestamp"]=int(time.time())

            if (TEST==True):
                # Debug logging
                globalState.configDB.logwrite(f"Sessionlog resetting {globalState.stateDict['eo_session_timestamp']}")

        else:
            secondsSinceLastLoop=(thisloop-self.lastloop).total_seconds()

            if (TEST==True):
                ## Test Routine
                globalState.stateDict["eo_session_joules"]+= int(globalState.stateDict["eo_live_voltage"] * 32 * secondsSinceLastLoop) ## TEST
                globalState.stateDict["eo_session_seconds_charged"]+=secondsSinceLastLoop
                # Debug Logging
                globalState.configDB.logwrite(f"Sessionlog accumulating {globalState.stateDict['eo_session_joules']}j {globalState.stateDict['eo_session_seconds_charged']}s")

            else:
                ## Production Routine
                # 1J = 1Ws = 1 x V * A * s
                globalState.stateDict["eo_session_joules"]+= int(globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_current_vehicle"] * secondsSinceLastLoop) ## LIVE
                # If eo_amps_requested is >=2, then the last cycle is counted against the number of seconds that this session has been actively trying to charge
                if globalState.stateDict["eo_amps_requested"]>=2:
                    globalState.stateDict["eo_session_seconds_charged"]+=secondsSinceLastLoop
            
            globalState.stateDict["eo_session_kwh"]= round(globalState.stateDict["eo_session_joules"] / 3600000,2)

            # Once a minute, we should write the current session information to the persistent log
            if (thisloop.minute>self.lastloop.minute):
                self.writesessionlog(globalState.stateDict["eo_session_timestamp"],globalState.stateDict["eo_session_joules"],globalState.stateDict["eo_session_seconds_charged"])

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


    # Write session log to sqlite3 db
    def writesessionlog(self,timestamp,joules,seconds_charged):
        with self.lock:
            now=int(time.time())
            sql=f'''REPLACE INTO {self.SESSION_TABLE_3} (first_timestamp, last_timestamp, day_timestamp, joules,seconds_charged) \
VALUES ({timestamp}, {now}, {self.timestamp_start_of_today()}, {joules},{seconds_charged})
-- {self.timestamp_text(timestamp)} {self.timestamp_text(now)} {self.timestamp_text(self.timestamp_start_of_today())}'''
            print(sql)
            self.cursor.execute(sql)
            self.conn.commit()
        globalState.configDB.logwrite(f"Sessionlog update {sql}")


    # Retrieve a dict of all sessions. This is used by the configserver for making this available via api
    def get_sessions(self):
        six_months_ago=int(time.time()) - 60*60*24*180
        with self.lock:
            # Only retrieve sizeable sessions to remove any noise from short term connections from plug/unplug
            self.cursor.execute(f"SELECT first_timestamp, last_timestamp, day_timestamp, joules, seconds_charged FROM {self.SESSION_TABLE_3} where joules>1500000 and first_timestamp>{six_months_ago}")
            rows = self.cursor.fetchall()

        data=[]
        for x in rows:
            data.append({"first_timestamp":x[0],
               "last_timestamp":x[1],
               "day_timestamp":x[2],
               "joules":x[3],
               "seconds_charged":x[4]}
               )
        
        return data

    def __init__(self,configParam):
        super().__init__(configParam)

        # In case we initialse with the charger already connected, we need to have a session timestamp and
        # other session counters populated. If it's not connected, then no biggie - it'll be reset on the next poll()
        globalState.stateDict["eo_session_joules"]=0
        globalState.stateDict["eo_session_kwh"]=0
        globalState.stateDict["eo_session_seconds_charged"]=0
        globalState.stateDict["eo_session_timestamp"]=int(time.time())

        # Create mutex lock for protecting transactions - noting that the get_sessions() method will be called from
        # another thread in configserver.
        self.lock=Lock()

        # Initialize SQLite DB and table
        self.conn = sqlite3.connect(self.SESSION_DB_FILE, check_same_thread=False)
        self.conn.execute('pragma journal_mode=wal')

        self.cursor = self.conn.cursor()
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.SESSION_TABLE_3} (
                first_timestamp INTEGER NOT NULL,
                day_timestamp INTEGER NOT NULL,
                last_timestamp INTEGER,
                joules INTEGER NOT NULL,
                seconds_charged INTEGER NOT NULL,
                PRIMARY KEY (first_timestamp, day_timestamp)
            )
        ''')

        # v5.8 session log db format no longer supported for migration - installation will just create an empty log
        # v5.9 had a different format session table, so if it exists, then
        #      we migrate the data across to the new table and drop the old table
        with self.lock:
            try:
                sql=f"SELECT first_timestamp, last_timestamp, day_timestamp, joules FROM {self.SESSION_TABLE_2}"
                self.cursor.execute(sql)
                rows = self.cursor.fetchall()
                print("Migrating v2 session log data")
                for x in rows:
                    now=datetime.datetime.fromtimestamp(x[0]).astimezone()
                    sql=f"REPLACE INTO {self.SESSION_TABLE_3} (first_timestamp, last_timestamp, day_timestamp, joules,seconds_charged) VALUES ({x[0]}, {x[1]}, {x[2]}, {x[3]},0)"
                    self.cursor.execute(sql)
                    print(sql)

                self.cursor.execute(f"drop table {self.SESSION_TABLE_2}")
                self.conn.commit()
            except Exception as err:
                if str(err)=="no such table: session":
                    # This is normal - there is no old format session table to migrate
                    pass
                else:
                    print("Error migrating old session data: ",err)