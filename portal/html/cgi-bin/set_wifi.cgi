#!/usr/bin/env python3

import os
import subprocess
import json
import socket
import sys
import re
from urllib.parse import parse_qs

CONNECTION_NAME = "custom-wifi"
WIFI_INTERFACE = "wlan0"

def can_access_internet(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host, port))
        return True
    except Exception:
        return False

def parse_input():
    method = os.environ.get("REQUEST_METHOD", "GET")
    if method == "POST":
        length = int(os.environ.get("CONTENT_LENGTH", 0))
        input_data = sys.stdin.read(length)
    else:
        input_data = os.environ.get("QUERY_STRING", "")
    return parse_qs(input_data)

def is_valid_ssid(ssid):
    return (
        isinstance(ssid, str) and
        1 <= len(ssid) <= 32 and
        re.match(r"^[\w\s\-\.]+$", ssid)
    )

def is_valid_password(password):
    return (
        isinstance(password, str) and
        8 <= len(password) <= 64 and
        re.match(r"^[\x21-\x7E]+$", password)  # Printable ASCII without spaces
    )

def setup_wifi_connection(ssid, password):
    try:
        # Delete any existing connection with this name
        subprocess.run(['nmcli', 'connection', 'delete', CONNECTION_NAME],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Add new connection profile
        subprocess.run([
            'nmcli', 'connection', 'add',
            'type', 'wifi',
            'ifname', WIFI_INTERFACE,
            'con-name', CONNECTION_NAME,
            'ssid', ssid
        ], check=True)

        # Set security and password
        subprocess.run([
            'nmcli', 'connection', 'modify', CONNECTION_NAME,
            'wifi-sec.key-mgmt', 'wpa-psk',
            'wifi-sec.psk', password
        ], check=True)

        # Bring up the connection
        result = subprocess.run([
            'nmcli', 'connection', 'up', CONNECTION_NAME
        ], capture_output=True, text=True)

        success = result.returncode == 0
        return success, result.stdout.strip() if success else result.stderr.strip()

    except subprocess.CalledProcessError as e:
        return False, f"nmcli error: {e.stderr.strip() if e.stderr else str(e)}"
    except Exception as e:
        return False, f"Exception: {str(e)}"

def main():

    params = parse_input()
    ssid = params.get("ssid", [None])[0]
    password = params.get("password", [None])[0]

    # Input validation
    if not is_valid_ssid(ssid):
        print(json.dumps({"error": "Invalid SSID"}))
        return
    if not is_valid_password(password):
        print(json.dumps({"error": "Invalid password"}))
        return

    connected, message = setup_wifi_connection(ssid, password)
    internet_ok = can_access_internet()

    print("Content-Type: application/json\n")
    print(json.dumps({
        "connected_to_wifi": connected,
        "nmcli_message": message,
        "internet_access": internet_ok
    }))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Status: 500 Internal Server Error")
        print("Content-Type: application/json\n")
        print(json.dumps({"error": str(e)}))

