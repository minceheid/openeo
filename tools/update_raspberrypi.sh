#!/usr/bin/bash

date
export DEBIAN_FRONTEND=noninteractive
sudo apt -y update
yes | sudo apt -y full-upgrade
/home/pi/openeo/openeo_deploy.bash
