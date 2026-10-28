#!/usr/bin/env python3
"""Tests for the /getlogs log viewer helpers and openeoConfigClass.logget(limit=)."""

import os, sqlite3, subprocess, sys, unittest
from threading import Lock
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import logviewer
from openeoConfig import openeoConfigClass


class ParseLogQueryTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(logviewer.parse_log_query("/getlogs"), ("app", 500))

    def test_journal_source(self):
        self.assertEqual(logviewer.parse_log_query("/getlogs?source=journal&lines=200"), ("journal", 200))

    def test_unknown_source_falls_back_to_app(self):
        self.assertEqual(logviewer.parse_log_query("/getlogs?source=etc_passwd")[0], "app")

    def test_lines_clamped(self):
        self.assertEqual(logviewer.parse_log_query("/getlogs?lines=0")[1], 50)
        self.assertEqual(logviewer.parse_log_query("/getlogs?lines=-10")[1], 50)
        self.assertEqual(logviewer.parse_log_query("/getlogs?lines=99999")[1], 5000)

    def test_non_numeric_lines_uses_default(self):
        self.assertEqual(logviewer.parse_log_query("/getlogs?lines=abc")[1], 500)


class ReadJournalTests(unittest.TestCase):
    def test_runs_journalctl_without_shell(self):
        completed = subprocess.CompletedProcess([], 0, stdout="line1\nline2\n", stderr="")
        with mock.patch("lib.logviewer.subprocess.run", return_value=completed) as run:
            self.assertEqual(logviewer.read_journal(100), "line1\nline2\n")
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["journalctl", "-u", "openeo", "-n", "100", "--no-pager", "-o", "short-iso"])
        self.assertNotIn("shell", kwargs)

    def test_missing_journalctl(self):
        with mock.patch("lib.logviewer.subprocess.run", side_effect=FileNotFoundError):
            self.assertTrue(logviewer.read_journal(100).startswith("Error:"))

    def test_timeout(self):
        with mock.patch("lib.logviewer.subprocess.run", side_effect=subprocess.TimeoutExpired("journalctl", 10)):
            self.assertIn("did not respond", logviewer.read_journal(100))

    def test_non_zero_exit(self):
        completed = subprocess.CompletedProcess([], 1, stdout="", stderr="No journal files were found.")
        with mock.patch("lib.logviewer.subprocess.run", return_value=completed):
            self.assertEqual(logviewer.read_journal(100), "Error: No journal files were found.")


class LoggetLimitTests(unittest.TestCase):
    def setUp(self):
        # Bypass __init__, which creates the database under /home/pi
        self.cfg = openeoConfigClass.__new__(openeoConfigClass)
        self.cfg.lock = Lock()
        self.cfg.conn = sqlite3.connect(":memory:")
        self.cfg.cursor = self.cfg.conn.cursor()
        self.cfg.cursor.execute("CREATE TABLE log (timestamp INTEGER NOT NULL, message TEXT NOT NULL)")
        # Two entries share a timestamp to check insertion order is kept
        rows = [(1000, "one"), (1001, "two"), (1001, "three"), (1002, "four")]
        self.cfg.cursor.executemany("INSERT INTO log (timestamp, message) VALUES (?, ?)", rows)
        self.cfg.conn.commit()

    def tearDown(self):
        self.cfg.conn.close()

    def messages(self, text):
        return [line.split(" ", 2)[2] for line in text.splitlines()]

    def test_no_limit_returns_everything(self):
        self.assertEqual(self.messages(self.cfg.logget()), ["one", "two", "three", "four"])

    def test_limit_returns_newest_oldest_first(self):
        self.assertEqual(self.messages(self.cfg.logget(limit=3)), ["two", "three", "four"])

    def test_limit_larger_than_table(self):
        self.assertEqual(self.messages(self.cfg.logget(limit=50)), ["one", "two", "three", "four"])

    def test_limit_follows_insertion_order_when_clock_steps_back(self):
        # e.g. NTP correcting the clock after boot: the newest entry has an older timestamp
        self.cfg.cursor.execute("INSERT INTO log (timestamp, message) VALUES (500, 'after clock step')")
        self.cfg.conn.commit()
        self.assertEqual(self.messages(self.cfg.logget(limit=2)), ["four", "after clock step"])


if __name__ == "__main__":
    unittest.main()
