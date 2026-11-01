#!/usr/bin/env python3
"""Tests that the Wi-Fi setup portal never writes the Wi-Fi password to its logs."""

import io, os, subprocess, sys, unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "portal"))

import portal

PASSWORD = "s3cret-Pa55word"


class RedactTests(unittest.TestCase):
    def test_masks_password_in_query_string(self):
        line = f'1.2.3.4 - "GET /api/set_wifi?ssid=home&password={PASSWORD} HTTP/1.1" 200 -'
        out = portal.redact(line)
        self.assertNotIn(PASSWORD, out)
        self.assertIn("ssid=home&password=*** HTTP/1.1", out)

    def test_masks_password_followed_by_other_params(self):
        out = portal.redact(f"/api/set_wifi?password={PASSWORD}&ssid=home")
        self.assertEqual(out, "/api/set_wifi?password=***&ssid=home")

    def test_leaves_other_lines_alone(self):
        line = '1.2.3.4 - "GET /api/get_wifi HTTP/1.1" 200 -'
        self.assertEqual(portal.redact(line), line)

    def test_log_message_is_redacted(self):
        handler = SimpleNamespace(client_address=("1.2.3.4", 1234))
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            portal.APIServerHandler.log_message(
                handler, '"%s" %s %s', f"GET /api/set_wifi?ssid=home&password={PASSWORD} HTTP/1.1", "200", "-")
        self.assertNotIn(PASSWORD, buf.getvalue())
        self.assertIn("password=***", buf.getvalue())


class SetupWifiConnectionTests(unittest.TestCase):
    def test_error_message_does_not_contain_password(self):
        def fake_run(cmd):
            if "wifi-sec.psk" in cmd:
                return subprocess.CompletedProcess(cmd, 4, "", "Error: failed to modify connection")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        ok, message, _, _ = portal.setup_wifi_connection("home", PASSWORD, run=fake_run)
        self.assertFalse(ok)
        self.assertNotIn(PASSWORD, message)

    def test_dryrun_does_not_print_password(self):
        buf = io.StringIO()
        with mock.patch.object(portal, "DRYRUN", True), mock.patch.object(sys, "stdout", buf):
            portal.setup_wifi_connection("home", PASSWORD)
        self.assertNotIn(PASSWORD, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
