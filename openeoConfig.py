#################################################################################
"""
OpenEO Class for handling configuration get/set
"""
#################################################################################

import sqlite3,logging,json,os,time,re,numbers
from threading import Lock

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

class openeoConfigClass:

    DB_FILE = "/home/pi/etc/config.db"
    JSON_FILE = "/home/pi/etc/config.json"
    CONFIG_TABLE_1 = "configuration"
    CONFIG_TABLE_2 = "configuration_v2"
    CONFIG_TABLE=CONFIG_TABLE_2

    LOG_TABLE = "log"
    LOG_PURGE_TTL = 3600 * 12 # 12 hours

    def logwrite(self,message):
        """
        inserts an entry into a table called "log" in the sqlite database
        """
        with self.lock:
            self.cursor.execute(f'''
                INSERT INTO {self.LOG_TABLE} (timestamp, message) 
                VALUES (?, ?)
            ''', (int(time.time()), message))
            self.conn.commit()

    def logpurge(self):
        """
        Purges log entries older than an hour ago
        """
        with self.lock:
            self.cursor.execute(f'''
                DELETE FROM log where timestamp<? 
            ''', (int(time.time()-self.LOG_PURGE_TTL),))
            self.conn.commit()


    def exists(self, module):
        """
        Check if a module exists in the configuration database.
        Returns True if exists, False otherwise.
        """
        with self.lock:
            self.cursor.execute(f"SELECT 1 FROM {self.CONFIG_TABLE} WHERE module=? LIMIT 1", (module,))
            return self.cursor.fetchone() is not None

    def dict(self):
        """
        Return all configuration as a dict of dicts:
        {module: {key: value, key: value}}
        """
        with self.lock:
            self.cursor.execute(f"SELECT module, key, value FROM {self.CONFIG_TABLE}")
            rows = self.cursor.fetchall()

        config_dict = {}
        for module, key, value in rows:
            if module not in config_dict:
                config_dict[module] = {}
            config_dict[module][key] = value
        return config_dict
    
    def get(self, module, key=None, default=None):
        """
        Given a module name, and optionally a key, retrieve all matching configuration
        if key is not specified, then the resultset will be returned as a Dict
        if key is specified, then only the value will be returned as a string, or 
        default or None if no module/key combination is found
        """
        if key:
            with self.lock:
                self.cursor.execute(f"SELECT value FROM {self.CONFIG_TABLE} WHERE module=? AND key=?", (module, key))
                row = self.cursor.fetchone()
            return row[0] if row else default
        else:
            with self.lock:
                self.cursor.execute(f"SELECT key, value FROM {self.CONFIG_TABLE} WHERE module=?", (module,))
                rows = self.cursor.fetchall()
            return {key: value for key, value in rows} if rows else None


    def delete(self, module, key):
        """
        Given a module name, and a key, delete all matching configuration
        Be careful with this! :-)
        """
        with self.lock:
            self.cursor.execute(f"DELETE FROM {self.CONFIG_TABLE} WHERE module=? AND key=?", (module, key))
        return

        

    def set(self, module, key_or_dict, value=None, triggerModuleReonfigure=True):
        """
        Either:
        1. Set an individual configuration value, given the module and key; or
        2. Bulk set configuration for a module, given a dict containing key/value pairs
        """
        if triggerModuleReonfigure:
            # Flag that something may have changed, which will trigger all plugin modules to reload config
            self.changed=True

        with self.lock:
            if isinstance(key_or_dict, dict):
                # Bulk insert
                for key, val in key_or_dict.items():
                    self.cursor.execute(f'''
                        REPLACE INTO {self.CONFIG_TABLE} (module, key, value, update_ts) 
                        VALUES (?, ?, ?, unixepoch())
                    ''', (module, key, val))

            else:
                # Single insert
                key = key_or_dict
                self.cursor.execute(f'''
                    REPLACE INTO {self.CONFIG_TABLE} (module, key, value, update_ts) 
                    VALUES (?, ?, ?, unixepoch())
                ''', (module, key, value))

            self.conn.commit()

        if isinstance(key_or_dict, dict):
            for key, value in key_or_dict.items():
                self.logwrite(f"Config update {module}:{key}={value}")
        else:
            self.logwrite(f"Config update {module}:{key}={value}")


    def __init__(self,defaultConfig=None):
        """
        Looks for SQLlite database, and if one doesn't exist, create one with the 
        correct schema. If config.json exists, then load the initial configuration from there,
        othewise default configuration will be set by modules as they enable themselves
        """
     
        # Create mutex lock for protecting transactions
        self.lock=Lock()

        # Initialize SQLite DB and table
        self.conn = sqlite3.connect(self.DB_FILE, check_same_thread=False)
        self.conn.execute('pragma journal_mode=wal')

        self.cursor = self.conn.cursor()
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.CONFIG_TABLE_2} (
                module TEXT NOT NULL,
                key TEXT NOT NULL,
                value,
                update_ts INTEGER,
                PRIMARY KEY (module, key)
            )
        ''')

        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.LOG_TABLE} (
                timestamp INTEGER NOT NULL,
                message TEXT NOT NULL
            )
        ''')
        self.conn.commit()

        # schema v2 introduces a requirement for update timestamps to record config changes
        with self.lock:
            try:
                sql=f"SELECT module,key,value FROM {self.CONFIG_TABLE_1}"
                self.cursor.execute(sql)
                rows = self.cursor.fetchall()
                print("Migrating v2 config log data")
                for x in rows:
                    if isinstance(x[2],numbers.Number):
                        sql=f"REPLACE INTO {self.CONFIG_TABLE_2} (module,key,value,update_ts) VALUES ('{x[0]}', '{x[1]}', {x[2]}, unixepoch())"
                    else:
                        sql=f"REPLACE INTO {self.CONFIG_TABLE_2} (module,key,value,update_ts) VALUES ('{x[0]}', '{x[1]}', '{x[2]}', unixepoch())"
                    #print(sql)
                    self.cursor.execute(sql)

                self.cursor.execute(f"drop table {self.CONFIG_TABLE_1}")
                self.conn.commit()
            except Exception as err:
                if re.search("^no such table:",str(err)):
                    # This is normal - there is no old format session table to migrate
                    pass
                else:
                    print("Error migrating old data: ",err)

        #################
        # Set default config, where appropriate
        for module,entriesDict in defaultConfig.items():
            if not self.get(module):
                _LOGGER.info(f"applying configuration defaults for module: {module}")
                for key,value in entriesDict.items():
                    self.set(module,key,value)

        #################
        # Load initial config from JSON file if it exists. Once done,
        # then we can rename the JSON file to prevent reloading it in the future.
        if os.path.exists(self.JSON_FILE):
            try:
                with open(self.JSON_FILE, 'r') as f:
                    initial_config = json.load(f)
                    for module, entries in initial_config.items():
                        for key, value in entries.items():
                            _LOGGER.info(f"applying configuration from {self.JSON_FILE} for {module}: {key} = {value}")
                            self.set(module, key, value)
                # Rename the JSON file to prevent reloading it in the future
                os.rename(self.JSON_FILE, self.JSON_FILE + "_loaded")
            except json.JSONDecodeError as e:
                _LOGGER.error(f"Failed to decode JSON config file '{self.JSON_FILE}': {e}")
            except Exception as e:
                _LOGGER.error(f"Error loading initial config from '{self.JSON_FILE}': {e}")


        # Set changed to True, so that configured modules will load in the main loop
        self.changed=True
        #print(str(self))
        self.LOG_PURGE_TTL=self.get("chargeroptions","log_purge_ttl",3600 * 12)

    
    def __str__(self):
        """
        dumps all configuration as a string for debugging purposes
        """
        # Acquire mutex lock, and run SQL
        with self.lock:
            self.cursor.execute(f"SELECT module, key, value FROM {self.CONFIG_TABLE} ORDER BY module, key")
            rows = self.cursor.fetchall()
        
        output = ""
        for module, key, value in rows:
            output += f"[{module}] {key} = {value}\n"
        return output.strip()

    def __del__(self):
        self.conn.close()
