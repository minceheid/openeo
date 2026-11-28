#################################################################################
"""
OpenEO Module: Charger Session


"""
#################################################################################

from lib.PluginSuperClass import PluginSuperClass
import globalState
import datetime,time
import sqlite3,logging,re,json
from threading import Lock
from lib.tariffrate import select_rate, SessionCostAccumulator, transition_message


# logging for use in this module
_LOGGER = logging.getLogger(__name__)

#################################################################################
class chargersessionClassPlugin(PluginSuperClass):
    PRETTY_NAME = "Session"
    CORE_PLUGIN = True  
    pluginParamSpec={ "enabled": {"type": "bool","default": True},
			"tariff": {
                "type": "json",
                "default":'[{"start": "0000", "end": "0029", "cost": 0.27048},{"start": "0030", "end": "0529", "cost": 0.04998},{"start": "0530", "end": "2359", "cost": 0.27048}]'},
            "ha_rate_enabled": {"type": "bool", "default": False},
            "ha_rate_stale_minutes": {"type": "int", "default": 15}}
            
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
    SESSION_TABLE_5="session_v5"
    SESSION_TABLE_6="session_v6"

    # Live HA tariff rate state. _accumulator is per session; the rest is per process.
    _accumulator=None
    _ha_enabled=False
    _tariff_state=None
    _ever_had_ha=False
        
    def reset_session(self):
        # Reset all session counters
        had_energy=globalState.stateDict.get("eo_session_joules",0)>0
        globalState.stateDict["eo_session_joules"]=0
        globalState.stateDict["eo_session_kwh"]=0
        globalState.stateDict["eo_session_seconds_charged"]=0
        globalState.stateDict["eo_session_cost"]=0
        self.today_timestamp=self.timestamp_start_of_today()

        # store tariff data for the session log, so that we can calculate the cost of the session as it progresses.
        # This is required because the tariff may change during a session, and we need to be able to calculate the
        # cost of the session accurately. We store this in a list of dicts, with each dict containing the start and 
        # end time of the tariff, the cost of the tariff, and the number of joules charged during that tariff period. 
        # This allows us to calculate the cost of the session accurately even if the tariff changes during the session.
        globalState.stateDict["session_tariff"]=[]
        for x in self.pluginConfig.get("tariff",[]):
            globalState.stateDict["session_tariff"].append({"start":x["start"],"end":x["end"],"cost":x["cost"],"joules":0})

        self._reset_ha_rate_accounting(had_energy)

    def _reset_ha_rate_accounting(self, had_energy):
        # Snapshot whether this session is costed from the live HA rate, so a settings change
        # takes effect from the next session (car re-plugged, or midnight). The old accumulator is settled before it is replaced.
        if self._accumulator is not None:
            # Only updates memory: the row already holds the pending energy at the last rate
            # from the last once-a-minute write.
            self._accumulator.settle()
        self._ha_enabled=bool(self.pluginConfig.get("ha_rate_enabled",False))
        self._accumulator=SessionCostAccumulator()
        if not self._ha_enabled:
            # Earlier in this poll the HA rate may have been written; replace it so the rate matches the source.
            globalState.stateDict["eo_session_current_tariff"]=self._schedule_rate(self.timestamp_hhmm(int(time.time())))
            globalState.stateDict["eo_tariff_rate_source"]="schedule"
            globalState.stateDict["eo_tariff_rate_reason"]="disabled"
        # reset_session() runs on every idle poll. HA's last_reset must only move when the
        # session cost actually drops back to 0, so stamp at startup or when energy was cleared.
        if had_energy or globalState.stateDict.get("eo_session_cost_reset") is None:
            globalState.stateDict["eo_session_cost_reset"]=datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    def _tariff_log(self, level, msg):
        _LOGGER.log(level, msg)
        if globalState.configDB is not None:
            globalState.configDB.logwrite(msg)

    def _schedule_rate(self, current_hhmm):
        # Same band lookup as poll(). Energy in a gap in the tariff is not costed on the
        # schedule path either, so a gap costs 0.
        for x in globalState.stateDict["session_tariff"]:
            if x["start"]<=current_hhmm<=x["end"]:
                return x["cost"]
        return 0.0

    def _update_ha_rate(self, current_hhmm):
        # Choose the live HA rate or the schedule rate, and log transitions between them.
        stale_minutes=self.pluginConfig.get("ha_rate_stale_minutes",15)
        rate, source, reason = select_rate(time.time(),
            globalState.stateDict.get("eo_ha_rate"),
            globalState.stateDict.get("eo_ha_online"),
            globalState.stateDict.get("eo_mqtt_connected",False),
            self._ha_enabled, stale_minutes, self._schedule_rate(current_hhmm))

        transition=transition_message(self._tariff_state, (source, reason), rate, self._ever_had_ha, stale_minutes)
        if transition:
            self._tariff_log(*transition)
        self._tariff_state=(source, reason)

        if source=="ha":
            self._ever_had_ha=True
            if not -1<=rate<=5 and rate not in self._warned_rates:
                self._warned_rates.add(rate)
                self._tariff_log(logging.WARNING, f"Tariff: HA rate {rate} is outside the expected range -1..5 per kWh - check the entity unit")

        globalState.stateDict["eo_session_current_tariff"]=rate
        globalState.stateDict["eo_tariff_rate_source"]=source
        globalState.stateDict["eo_tariff_rate_reason"]=reason

    def poll(self):
        # If charger state indicates that the car might be disconnected, then
        # we reset the session kWh count, otherwise we calculate how many additional
        # joules have been added to the count
        
        # Find which tariff period we are in, and record the current tariff cost in the stateDict, so that it can be used by other plugins
        current_hhmm=self.timestamp_hhmm(int(time.time()))
        for x in globalState.stateDict["session_tariff"]:
            if x["start"]<=current_hhmm<=x["end"]:
                globalState.stateDict["eo_session_current_tariff"]=x["cost"]
                break
        if self._ha_enabled:
            self._update_ha_rate(current_hhmm)

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
            globalState.stateDict["eo_session_timestamp"]=int(time.time())


            if (TEST==True):
                # Debug logging
                print(f"Sessionlog resetting to {globalState.stateDict['eo_session_timestamp']}")

        else:
            secondsSinceLastLoop=(thisloop-self.lastloop).total_seconds()

            if self.timestamp_start_of_today() > self.today_timestamp:
                # if the session timestamp is from a previous day, then we reset the session counters, so that we start a new session for the new day.
                # but we don't reset the session timestamp, because we want to keep the timestamp of the first session of the day, so that we can calculate the total cost of the day.
                self.reset_session()
                self.today_timestamp=self.timestamp_start_of_today()

            ## Production Routine
            # 1J = 1Ws = 1 x V * A * s
            # 1kWh = 3.6 million joules

            if (TEST==True):
                joulesThisLoop = int(globalState.stateDict["eo_live_voltage"] * 32 * secondsSinceLastLoop)
            else: 
                joulesThisLoop = int(globalState.stateDict["eo_live_voltage"] * globalState.stateDict["eo_current_vehicle"] * secondsSinceLastLoop)

            globalState.stateDict["eo_session_joules"]+= joulesThisLoop
            if self._ha_enabled:
                self._accumulator.add(thisloop, joulesThisLoop,
                    globalState.stateDict["eo_session_current_tariff"],
                    globalState.stateDict["eo_tariff_rate_source"])
            else:
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
            if self._ha_enabled:
                globalState.stateDict["eo_session_cost"]=round(self._accumulator.cost(),2)
                joules_by_tariff=self._accumulator.cost_by_tariff()
            else:
                cost=0
                joules_by_tariff={}
                for x in globalState.stateDict["session_tariff"]:
                    cost+=x["cost"] * (x["joules"] / 3600000)
                    joules_by_tariff[x["cost"]] = joules_by_tariff.get(x["cost"], 0) + x["joules"]

                globalState.stateDict["eo_session_cost"]=round(cost,2)

            # Debug Logging
            if (TEST==True):
                print(f"Sessionlog {globalState.stateDict['eo_session_timestamp']}/{self.timestamp_start_of_today() } accumulating {globalState.stateDict['eo_session_joules']}j {globalState.stateDict['eo_session_seconds_charged']:.1f}s £{globalState.stateDict['eo_session_cost']} {json.dumps(joules_by_tariff)}")

            # Once a minute, we should write the current session information to the persistent log
            if (thisloop.minute>self.lastloop.minute):
                if (TEST==True):
                    print(f"Sessionlog {globalState.stateDict['eo_session_timestamp']} writing")

                if self._ha_enabled:
                    self.writesessionlog(globalState.stateDict["eo_session_timestamp"],
                        globalState.stateDict["eo_session_joules"],
                        globalState.stateDict["eo_session_seconds_charged"],
                        globalState.stateDict["eo_session_cost"],
                        json.dumps(joules_by_tariff),
                        self._accumulator.fallback_joules)
                else:
                    self.writesessionlog(globalState.stateDict["eo_session_timestamp"],
                        globalState.stateDict["eo_session_joules"],
                        globalState.stateDict["eo_session_seconds_charged"],
                        globalState.stateDict["eo_session_cost"],
                        json.dumps(joules_by_tariff))

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
    def writesessionlog(self,timestamp,joules,seconds_charged,cost=0.0,cost_by_tariff="",fallback_joules=0):
        with self.lock:
            now=int(time.time())
            sql=f'''REPLACE INTO {self.SESSION_TABLE_6} (first_timestamp, last_timestamp, day_timestamp, joules,seconds_charged, cost,cost_by_tariff,fallback_joules) \
VALUES ({timestamp}, {now}, {self.timestamp_start_of_today()}, {joules},{seconds_charged},{cost},\'{cost_by_tariff}\',{int(fallback_joules)})
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
            self.cursor.execute(f"SELECT first_timestamp, last_timestamp, day_timestamp, joules, seconds_charged, cost, cost_by_tariff, fallback_joules \
            FROM {self.SESSION_TABLE_6} \
            where first_timestamp>{six_months_ago}")
            rows = self.cursor.fetchall()

        data=[]
        for x in rows:
            data.append({"first_timestamp":x[0],
               "last_timestamp":x[1],
               "day_timestamp":x[2],
               "joules":x[3],
               "seconds_charged":x[4],
               "cost":x[5],
               "cost_by_tariff":x[6],
               "fallback_joules":x[7]}
               )
        
        # iterate over the data structure and generate a dict of first_timestamp and the sum of joules for that first_timestamp.
        summary={}
        for x in data:
            if x["first_timestamp"] not in summary:
                summary[x["first_timestamp"]]=0
            summary[x["first_timestamp"]]+=x["joules"]

        # generate a list of all first_timestamp values where joules <0.5MJ
        short_sessions=[]
        for k,v in summary.items():
            if v<(3600000/2):  # less than 0.5kWh
                short_sessions.append(k)

        # remove any entries from data where first_timestamp is in short_sessions
        data=[x for x in data if x["first_timestamp"] not in short_sessions]
        
        return data

    def __init__(self,configParam):
        super().__init__(configParam)

        # Out-of-range HA rates already warned about, so each distinct rate is logged once.
        self._warned_rates=set()

        # Reset session counters on startup, to ensure that we start with a clean session. This is important because 
        # if the software is restarted during a charging session, we don't want to carry over the old session data 
        # into the new session.
        self.reset_session()
        globalState.stateDict["eo_session_timestamp"]=int(time.time())
        self._warn_if_ha_plugin_disabled()

        # Create mutex lock for protecting transactions - noting that the get_sessions() method will be called from
        # another thread in configserver.
        self.lock=Lock()

        # Initialize SQLite DB and table
        self.conn = sqlite3.connect(self.SESSION_DB_FILE, check_same_thread=False)
        self.conn.execute('pragma journal_mode=wal')

        self.cursor = self.conn.cursor()
        
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.SESSION_TABLE_6} (
                first_timestamp INTEGER NOT NULL,
                day_timestamp INTEGER NOT NULL,
                last_timestamp INTEGER,
                joules INTEGER NOT NULL,
                seconds_charged INTEGER NOT NULL,
                cost REAL NOT NULL,
                cost_by_tariff text not null,
                fallback_joules INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (first_timestamp, day_timestamp)
            )
        ''')

        # session_v4 session log db format no longer supported for migration - installation will just create an empty log
        # session_v5 had no fallback_joules column, so if it exists, then
        #      we migrate the data across to the new table and drop the old table
        with self.lock:
            try:
                sql=f"SELECT first_timestamp, last_timestamp, day_timestamp, joules, seconds_charged, cost, cost_by_tariff FROM {self.SESSION_TABLE_5}"
                self.cursor.execute(sql)
                rows = self.cursor.fetchall()
                print("Migrating v5 session log data")
                for x in rows:
                    self.cursor.execute(f"REPLACE INTO {self.SESSION_TABLE_6} (first_timestamp, last_timestamp, day_timestamp, joules,seconds_charged,cost,cost_by_tariff,fallback_joules) VALUES (?,?,?,?,?,?,?,0)", x)

                self.cursor.execute(f"drop table {self.SESSION_TABLE_5}")
                self.conn.commit()
            except Exception as err:
                if re.search("^no such table:",str(err)):
                    # This is normal - there is no old format session table to migrate
                    pass
                else:
                    print("Error migrating old session data: ",err)

    def _warn_if_ha_plugin_disabled(self):
        if not self.pluginConfig.get("ha_rate_enabled",False) or globalState.configDB is None:
            return
        ha_enabled=globalState.configDB.get("homeassistant","enabled")
        if ha_enabled not in (True,"True","true","1",1):
            self._tariff_log(logging.WARNING, "Tariff: live HA rate enabled but the Home Assistant plugin is disabled - using schedule rate")

    def get_user_settings(self):
        return [{"type": "tariff", "name": "tariff", "label": "Tariff", "default":self.pluginConfig.get("tariff",""),"note":"Set the tariff for your electricity supply. The full 24 hour period must be specified with no gaps. The cost is measured per kWh. This control may be difficult to use on mobile devices - use from a larger screen if difficulty is experienced."},
            {"type": "boolean", "name": "ha_rate_enabled", "label": "Use live rate from Home Assistant", "default":self.pluginConfig.get("ha_rate_enabled",False), "note":"Costs charging at a rate pushed from Home Assistant by the OpenEO tariff blueprint, settled per half-hour. The tariff above is used whenever the HA rate is stale or unavailable. Takes effect the next time the car is plugged in. If the car is already plugged in, unplug and re-plug it, or the change applies from midnight."},
            {"type": "slider", "name": "ha_rate_stale_minutes", "label": "HA rate stale after", "default":self.pluginConfig.get("ha_rate_stale_minutes",15), "range": [10,60], "step":5, "value_unit":"min", "note":"Fall back to the tariff if no rate has arrived from Home Assistant for this long. Must be longer than the blueprint's 5 minute heartbeat."}];
