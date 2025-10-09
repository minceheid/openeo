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
    SESSION_TABLE="session"
    SESSION_TABLE2="session2"
        
    def poll(self):
        # If charger state indicates that the car might be disconnected, then
        # we reset the session kWh count, otherwise we calculate how many additional
        # joules have been added to the count

        if (((datetime.datetime.now()).hour/2)-1) % 2 == 0: ## TEST
        #if globalState.stateDict["eo_charger_state_id"]<9:
            globalState.stateDict["eo_session_joules"]=0
            globalState.stateDict["eo_session_kwh"]=0
            globalState.stateDict["eo_session_timestamp"]=int(time.time())
        else:
            thisloop=datetime.datetime.now()
            secondsSinceLastLoop=(thisloop-self.lastloop).total_seconds()
            # 1J = 1Ws = 1 x V * A * s
            globalState.stateDict["eo_session_joules"]+= int(globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_current_vehicle"] * secondsSinceLastLoop)
            globalState.stateDict["eo_session_joules"]+= int(globalState.stateDict["eo_live_voltage"] * 32 * secondsSinceLastLoop) ## TEST
            globalState.stateDict["eo_session_kwh"]= round(globalState.stateDict["eo_session_joules"] / 3600000,2)

            # Once a minute, we should write down the current session information to the persistent log
            if (thisloop.minute>self.lastloop.minute):
                self.writesessionlog(globalState.stateDict["eo_session_timestamp"],globalState.stateDict["eo_session_joules"])

            # Reset the time counter for next time.
            self.lastloop=thisloop

        return 0

    def local_day_start_epoch(self):
        now = datetime.datetime.now().astimezone()  # current local time, timezone-aware
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(start_of_day.timestamp())

    def writesessionlog(self,timestamp,joules):
        with self.lock:
            self.cursor.execute(f'''
                REPLACE INTO {self.SESSION_TABLE2} (first_timestamp, last_timestamp, day_timestamp, joules) 
                VALUES (?, ?, ?, ?)
            ''', (int(timestamp), int(time.time()), self.local_day_start_epoch(), joules))
            self.conn.commit()

    def get_sessions(self):
        six_months_ago=int(time.time()) - 60*60*24*180
        with self.lock:
            # Only retrieve entries that are greater than 1kWh to remove any short term connections from plug/unplug
            self.cursor.execute(f"SELECT first_timestamp, last_timestamp, day_timestamp, joules FROM {self.SESSION_TABLE2} where joules>3600000 and first_timestamp>{six_months_ago}")
            rows = self.cursor.fetchall()

        data=[]
        for x in rows:
            data.append({"first_timestamp":x[0],
               "last_timestamp":x[1],
               "day_timestamp":x[2],
               "joules":x[3]}
               )
        
        return data

    def __init__(self,configParam):
        super().__init__(configParam)

        # In case we initialse with the charger already connected, we need to have a session timestamp populated
        # if it's not connected, then it'll be reset on the next poll()
        globalState.stateDict["eo_session_timestamp"]=int(time.time())

        # Create mutex lock for protecting transactions
        self.lock=Lock()

        # Initialize SQLite DB and table
        self.conn = sqlite3.connect(self.SESSION_DB_FILE, check_same_thread=False)
        self.conn.execute('pragma journal_mode=wal')

        self.cursor = self.conn.cursor()
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.SESSION_TABLE2} (
                first_timestamp INTEGER NOT NULL,
                day_timestamp INTEGER NOT NULL,
                last_timestamp INTEGER,
                joules INTEGER NOT NULL,
                PRIMARY KEY (first_timestamp, day_timestamp)
            )
        ''')
