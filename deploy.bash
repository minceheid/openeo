#!/usr/bin/bash

echo "@reboot openeo/boot.bash" >/tmp/crontab 
crontab /tmp/crontab
sudo apt-get install -y python3-serial python3-websockets python3-jsonschema python3-jinja2
sudo cp /boot/firmware/config.txt /tmp/config.txt
sudo sh -c 'sed "s/#dtparam=spi=on/dtparam=spi=on/" </tmp/config.txt >/boot/firmware/config.txt'
