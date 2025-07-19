#!/usr/bin/bash

echo "@reboot boot.bash" >/tmp/crontab 
crontab /tmp/crontab
sudo apt-get install -y python3-serial python3-websockets python3-jsonschema
sudo cp /boot/firmware/config.txt /tmp/config.txt
sudo sh -c 'sed "s/#dtparam=spi=on/dtparam=spi=on/" </tmp/config.txt >/boot/firmware/config.txt'
