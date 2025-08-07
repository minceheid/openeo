#!/usr/bin/env python3

import subprocess
import json
import sys
import socket

import fcntl
import struct

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ip_addr = fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )
        return socket.inet_ntoa(ip_addr[20:24])
    except IOError:
        return None
    
def can_access_internet(host="8.8.8.8", port=53, timeout=3):
    """
    Attempts to open a socket to a known public DNS server (Google's 8.8.8.8).
    Returns True if successful, False otherwise.
    """
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host, port))
        return True
    except Exception:
        return False


def get_wifi_data():
    active_network=""
    try:
        result = subprocess.run(
            ['nmcli', '--get-values=SSID,IN-USE', 'dev', 'wifi', 'list', 'ifname', 'wlan0'],
            capture_output=True, text=True, check=True
        )
        ssids = []
        banned_ssids = ["openeo",""]
        for line in result.stdout.splitlines():
                row=line.split(':')
                if row[0] not in ssids and row[0] not in banned_ssids:
                    ssids.append(row[0])
                if (row[1]=="*"):
                    active_network=row[0]

		
	
        return {"SSID": sorted(ssids), "CONNECTED":active_network}

    except subprocess.CalledProcessError as e:
        return {"error": f"Command failed: {e}"}
    except Exception as e:
        return {"error": str(e)}

def get_ssh_public_key():
	try:
		result = subprocess.run( ['/var/www/html/cgi-bin/getset_keys'], capture_output=True, text=True, check=True )
		return result.stdout
	except Exception as e:
		return f"Error reading file: {e}"

def main():

    data=get_wifi_data()
    data["INTERNET"]=can_access_internet()
    data["SSH"]=get_ssh_public_key()
    data["IP"]=get_ip_address('wlan0')

    # Output CGI headers
    print("Content-Type: application/json")
    print()

    # Output JSON response
    print(json.dumps(data))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Failsafe error output
        print("Status: 500 Internal Server Error")
        print("Content-Type: application/json")
        print()
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

