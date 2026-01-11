#!/usr/bin/env python3

import http.server
import socketserver
import urllib.parse
import os
import threading
import time
import argparse
import signal
import sys
import json
import subprocess
import socket
import fcntl,struct,re
from urllib.parse import parse_qs


PORT = 81
DEFAULT_TIMEOUT = 4*60
CONNECTION_NAME = "custom-wifi"
WIFI_INTERFACE = "wlan0"
DRYRUN=True
SSH_DIR="/home/pi/.ssh"
auth_keys_file = os.path.join(SSH_DIR, "authorized_keys")


shutdown_event = threading.Event()
start_time = time.time()

# =========================
# Startup / Shutdown hooks
# =========================

def on_startup():
    print("[STARTUP] Network startup")
    subprocess.run(['sudo','/home/pi/openeo/portal/tools/openeo_portal.bash', 'start'],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[STARTUP] Webserver starting")


def on_shutdown():
    print("[SHUTDOWN] Network stopping")
    subprocess.run(['sudo','/home/pi/openeo/portal/tools/openeo_portal.bash', 'stop'],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[SHUTDOWN] Webserver stopping")



# =========================
# API function definitions
# =========================

def api_get_wifi(params):
    data=get_wifi_data()
    data["INTERNET"]=can_access_internet()
    data["SSH"]=get_ssh_public_key()
    data["IP"]=get_ip_address(WIFI_INTERFACE)
    return data



def api_set_wifi(params):
    ssid = params.get("ssid", [None])
    password = params.get("password", [None])

    # Input validation
    if not is_valid_ssid(ssid):
        return({"error": "Invalid SSID"})
    if not is_valid_password(password):
        return({"error": "Invalid Password"})

    connected, message = setup_wifi_connection(ssid, password)

    return({
        "connected_to_wifi": connected,
        "nmcli_message": message,
        "internet_access": can_access_internet()
    })


def api_set_ssh(params,post_data):
    key = post_data.get("key", [None])

    if is_valid_key(key):
        if not os.path.isdir(SSH_DIR):
            os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
        os.chmod(SSH_DIR, 0o700)
        with open(auth_keys_file, "w", encoding="utf-8") as f:
            f.write(key.rstrip() + "\n")

        return(get_ssh_public_key())
    else:
        return({"error": "Invalid Key"})




# =========================
# API supporting functions
# =========================

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
            ['sudo','nmcli', '--get-values=SSID,IN-USE', 'dev', 'wifi', 'list', 'ifname', WIFI_INTERFACE],
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
        with open(auth_keys_file, "r", encoding="utf-8") as f:
            content = f.readline()
            return content
    except Exception as e:
            return f"Error reading file: {e}"


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
        if DRYRUN:
            print(f"setup_wifi_connection {ssid} {password} - dryrun - not executed\n")
            return 0
        
        # Delete any existing connection with this name
        subprocess.run(['sudo','nmcli', 'connection', 'delete', CONNECTION_NAME],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Add new connection profile
        subprocess.run([
            'sudo','nmcli', 'connection', 'add',
            'type', 'wifi',
            'ifname', WIFI_INTERFACE,
            'con-name', CONNECTION_NAME,
            'ssid', ssid
        ], check=True)

        # Set security and password
        subprocess.run([
            'sudo','nmcli', 'connection', 'modify', CONNECTION_NAME,
            'wifi-sec.key-mgmt', 'wpa-psk',
            'wifi-sec.psk', password
        ], check=True)

        # Bring up the connection
        result = subprocess.run([
            'sudo','nmcli', 'connection', 'up', CONNECTION_NAME
        ], capture_output=True, text=True)

        success = result.returncode == 0
        return success, result.stdout.strip() if success else result.stderr.strip()

    except subprocess.CalledProcessError as e:
        return False, f"nmcli error: {e.stderr.strip() if e.stderr else str(e)}"
    except Exception as e:
        return False, f"Exception: {str(e)}"
    
def is_valid_key(key):
    return (
        isinstance(key, str) and
        re.match(r"^(ssh-dss AAAAB3NzaC1kc3|ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNT|sk-ecdsa-sha2-nistp256@openssh.com AAAAInNrLWVjZHNhLXNoYTItbmlzdHAyNTZAb3BlbnNzaC5jb2|ssh-ed25519 AAAAC3NzaC1lZDI1NTE5|sk-ssh-ed25519@openssh.com AAAAGnNrLXNzaC1lZDI1NTE5QG9wZW5zc2guY29t|ssh-rsa AAAAB3NzaC1yc2)[0-9A-Za-z+/]+[=]{0,3}(\s.*)?$", key)
    )


# =========================
# API whitelist
# =========================

API_HANDLERS_GET = {
    "get_wifi": api_get_wifi,
    "set_wifi": api_set_wifi,

}
API_HANDLERS_POST = {
    "set_ssh": api_set_ssh,
}

# =========================
# HTTP Handler
# =========================

class APIServerHandler(http.server.SimpleHTTPRequestHandler):
    api_prefix = "/api/"

    def do_GET(self):
        if self.path.startswith(self.api_prefix):
            self.handle_api(API_HANDLERS_GET)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith(self.api_prefix):
            self.handle_api(API_HANDLERS_POST)
        else:
            super().do_POST()

    def handle_api(self,API_HANDLERS):
        parsed = urllib.parse.urlparse(self.path)
        api_name = parsed.path[len(self.api_prefix):].strip("/")
        params = urllib.parse.parse_qs(parsed.query)
        # Flatten params: key -> single value or list
        params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}



        if api_name not in API_HANDLERS:
            self.send_error(404, "Unknown API endpoint")
            return

        try:

            if self.command=="POST":
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length).decode('utf-8')
                post_data = urllib.parse.parse_qs(post_data)
                post_data = {k: v[0] if len(v) == 1 else v for k, v in post_data.items()}
                result = API_HANDLERS[api_name](params,post_data)
            else:   
                result = API_HANDLERS[api_name](params)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())

        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - %s\n" %
                         (self.client_address[0], fmt % args))


# =========================
# Main
# =========================


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """This child class allows us to set the REUSEADDR and REUSEPORT options on the socket
    which means the Python task can be started and stopped without breaking the config server
    due to the previous socket being in TIME_WAIT.
    
    """
    def server_bind(self):
        # Set socket options before binding
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()

def webserver():
    socketserver.TCPServer.allow_reuse_address = True
    with ThreadedServer(("", PORT), APIServerHandler) as httpd:
        print(f"[INFO] Serving {os.getcwd()} on port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.shutdown()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="html", help="Directory to serve")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    os.chdir(args.dir)
    on_startup()

    serverthread = threading.Thread(target=webserver, name='serverthread', daemon=True)
    serverthread.start()

    time.sleep(args.timeout)
    on_shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()
