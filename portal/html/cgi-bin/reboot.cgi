#!/usr/bin/python3

import subprocess


def main():
    try:
        result=subprocess.run(['sudo','-u','root','/usr/sbin/reboot'],capture_output=True, text=True, check=True)


if __name__ == "__main__":
    main()
