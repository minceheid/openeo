#################################################################################
"""
OpenEO Class for handling configuration get/set
"""
#################################################################################

import sqlite3
import os
import json

class openeoConfigClass:

    DB_FILE = "config.db"
    JSON_FILE = "config.json_new"
    CONFIG_TABLE = "configuration"

    def exists(self, module):
        """
        Check if a module exists in the configuration database.
        Returns True if exists, False otherwise.
        """
        self.cursor.execute(f"SELECT 1 FROM {self.CONFIG_TABLE} WHERE module=? LIMIT 1", (module,))
        return self.cursor.fetchone() is not None

    def get(self, module, key=None):
        """
        Given a module name, and optionally a key, retrieve all matching configuration
        if key is not specified, then the resultset will be returned as a Dict
        if key is specified, then only the value will be returned as a string, or 
        None if no module/key combination is found
        """
        if key:
            self.cursor.execute(f"SELECT value FROM {self.CONFIG_TABLE} WHERE module=? AND key=?", (module, key))
            row = self.cursor.fetchone()
            return row[0] if row else None
        else:
            self.cursor.execute(f"SELECT key, value FROM {self.CONFIG_TABLE} WHERE module=?", (module,))
            rows = self.cursor.fetchall()
            return {key: value for key, value in rows}
        
    def set(self, module, key_or_dict, value=None):
        """
        Either:
        1. Set an individual configuration value, given the module and key; or
        2. Bulk set configuration for a module, given a dict containing key/value pairs
        """
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

    def clear(self, module, key=None):
        """
        Clear an individual configuration key, given the module and key, OR, bulk clear 
        configuration entries for a specific module
        """
        if key:
            self.cursor.execute(f"DELETE FROM {self.CONFIG_TABLE} WHERE module=? AND key=?", (module, key))
        else:
            self.cursor.execute(f"DELETE FROM {self.CONFIG_TABLE} WHERE module=?", (module,))
        self.conn.commit()

    def __init__(self):
        """
        Looks for SQLlite database, and if one doesn't exist, create one with the 
        correct schema. If config.json exists, then load the initial configuration from there,
        othewise default configuration will be set by modules as they enable themselves
        """
        # Initialize SQLite DB and table
        self.conn = sqlite3.connect(self.DB_FILE)
        self.cursor = self.conn.cursor()
        self.cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.CONFIG_TABLE} (
                module TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (module, key)
            )
        ''')
        self.conn.commit()

        # Load initial config from JSON if database is empty
        self.cursor.execute(f"SELECT COUNT(*) FROM {self.CONFIG_TABLE}")
        if self.cursor.fetchone()[0] == 0 and os.path.exists(self.JSON_FILE):
            with open(self.JSON_FILE, 'r') as f:
                initial_config = json.load(f)
                for module, entries in initial_config.items():
                    for key, value in entries.items():
                        self.setConfig(module, key, value)

    
    def __str__(self):
        """
        dumps all configuration as a string for debugging purposes
        """
        self.cursor.execute(f"SELECT module, key, value FROM {self.CONFIG_TABLE} ORDER BY module, key")
        rows = self.cursor.fetchall()
        output = ""
        for module, key, value in rows:
            output += f"[{module}] {key} = {value}\n"
        return output.strip()

    def __del__(self):
        self.conn.close()
