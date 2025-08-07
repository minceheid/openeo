#!/usr/bin/env python3

import os
import subprocess
import json
import sys
import re
from urllib.parse import parse_qs


def parse_input():
    method = os.environ.get("REQUEST_METHOD", "GET")
    if method == "POST":
        length = int(os.environ.get("CONTENT_LENGTH", 0))
        input_data = sys.stdin.read(length)
    else:
        input_data = os.environ.get("QUERY_STRING", "")
    return parse_qs(input_data)

def set_ssh_public_key(key=""):
        try:
                result = subprocess.run( ['/home/pi/openeo/portal/html/cgi-bin/getset_keys',key], capture_output=True, text=True, check=True )
                return result.stdout
        except Exception as e:
                return f"Error reading file: {e}"

def get_ssh_public_key():
        try:
                result = subprocess.run( ['/home/pi/openeo/portal/html/cgi-bin/getset_keys'], capture_output=True, text=True, check=True )
                return result.stdout
        except Exception as e:
                return f"Error reading file: {e}"


def is_valid_key(key):
    return (
        isinstance(key, str) and
        re.match(r"^(ssh-dss AAAAB3NzaC1kc3|ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNT|sk-ecdsa-sha2-nistp256@openssh.com AAAAInNrLWVjZHNhLXNoYTItbmlzdHAyNTZAb3BlbnNzaC5jb2|ssh-ed25519 AAAAC3NzaC1lZDI1NTE5|sk-ssh-ed25519@openssh.com AAAAGnNrLXNzaC1lZDI1NTE5QG9wZW5zc2guY29t|ssh-rsa AAAAB3NzaC1yc2)[0-9A-Za-z+/]+[=]{0,3}(\s.*)?$", key)
    )

def main():
    params = parse_input()
    key = params.get("key", [None])[0]
    # Only interested in the first line
    key=key.partition('\n')[0]

    if is_valid_key(key):
        set_ssh_public_key(key)
        print("Content-Type: application/json\n")
        print(get_ssh_public_key())
    else:
        print("Status: 500 Internal Server Error")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Status: 500 Internal Server Error")
        print("Content-Type: application/json\n")
        print(json.dumps({"error": str(e)}))

