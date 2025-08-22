#################################################################################
"""
OpenEO Class for handling configuration get/set
"""
#################################################################################

import sqlite3,logging,json
from threading import Lock

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

class openeoConfigClass:

    DB_FILE = "/home/pi/etc/config.db"
    JSON_FILE = "config.json_new"
    CONFIG_TABLE = "configuration"

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
        
    def set(self, module, key_or_dict, value=None):
        """
        Either:
        1. Set an individual configuration value, given the module and key; or
        2. Bulk set configuration for a module, given a dict containing key/value pairs
        """
        # Flag that something may have changed, which will trigger all plugin modules to reload config
        self.changed=True
        
        with self.lock:
            if isinstance(key_or_dict, dict):
                # Bulk insert
                for key, val in key_or_dict.items():
                    self.cursor.execute(f'''
                        INSERT INTO {self.CONFIG_TABLE} (module, key, value) 
                        VALUES (?, ?, ?)
                        ON CONFLICT(module, key) DO UPDATE SET value=excluded.value
                    ''', (module, key, val))
            else:
                # Single insert
                key = key_or_dict
                self.cursor.execute(f'''
                    INSERT INTO {self.CONFIG_TABLE} (module, key, value) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(module, key) DO UPDATE SET value=excluded.value
                ''', (module, key, value))
            self.conn.commit()


    def setDict(self, data, strict=True):
        """
        Insert or replace configuration values from a dict of dicts:
        {module: {key: value, key: value}, ...}

        Ensures all values are coercible to strings.
        If strict=True, raises ValueError if conversion fails.
        If strict=False, silently coerces values with str().
        
        Performs the operation in a single SQL transaction for speed and atomicity.
        Existing values are overwritten; missing modules/keys are inserted.
        """
        if not isinstance(data, dict):
            raise ValueError("setDict() requires a dict of dicts")
        
        # Flag that something may have changed, which will trigger all plugin modules to reload config
        self.changed=True

        # Acquire mutex lock, and load the data
        with self.lock:
            try:
                self.conn.execute("BEGIN")
                insert_sql = f'''
                    INSERT INTO {self.CONFIG_TABLE} (module, key, value)
                    VALUES (?, ?, ?)
                    ON CONFLICT(module, key) DO UPDATE SET value=excluded.value
                '''
                for module, entries in data.items():
                    if not isinstance(entries, dict):
                        raise ValueError(f"Module '{module}' must map to a dict of key/value pairs")
                    for key, value in entries.items():
                        if strict:
                            try:
                                value_str = json.dumps(value) if value is not None else ""
                            except Exception:
                                raise ValueError(f"Value for {module}.{key} cannot be converted to string")
                        else:
                            value_str = json.dumps(value) if value is not None else ""
                        self.cursor.execute(insert_sql, (str(module), str(key), value_str))
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise



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
        
        self.cursor = self.conn.cursor()
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.CONFIG_TABLE} (
                module TEXT NOT NULL,
                key TEXT NOT NULL,
                value,
                PRIMARY KEY (module, key)
            )
        ''')
        self.conn.commit()

        #################
        # Set default config, where appropriate
        for module,entriesDict in defaultConfig.items():
            if not self.get(module):
                _LOGGER.info(f"applying configuration defaults for module: {module}")
                for key,value in entriesDict.items():
                    self.set(module,key,value)

        '''
        # Load initial config from JSON if database is empty
        self.cursor.execute(f"SELECT COUNT(*) FROM {self.CONFIG_TABLE}")
        if self.cursor.fetchone()[0] == 0 and os.path.exists(self.JSON_FILE):
            with open(self.JSON_FILE, 'r') as f:
                initial_config = json.load(f)
                for module, entries in initial_config.items():
                    for key, value in entries.items():
                        self.setConfig(module, key, value)
        '''

        # Set changed to True, so that configured modules will load in the main loop
        self.changed=True
    
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
