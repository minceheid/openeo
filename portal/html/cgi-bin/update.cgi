#!/usr/bin/python3

import os
import json
import subprocess


def main():
    try:
        os.chdir("/home/pi/")
        result=subprocess.run(['sudo','-u','pi','/home/pi/openeo/deploy.bash'],capture_output=True, text=True, check=True)
        print("Content-Type: text/plain\n")
        print(result.stdout)
        print(result.stderr)

    except Exception as e:
        print("Status: 500 Internal Server Error")
        print("Content-Type: application/json\n")
        print(result.stdout)
        print(result.stderr)        


if __name__ == "__main__":
    main()