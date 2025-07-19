#!/usr/bin/bash

# Get and extract main archive
BRANCH=main

wget https://github.com/minceheid/openeo/archive/refs/heads/$BRANCH.zip
unzip main.zip
# The zip file includes the branch name, so remove that for a consistent pathname
mv openeo-$BRANCH openeo

# The crontab will allow openeo to start automatically at boot
echo "@reboot openeo/boot.bash" >/tmp/crontab 
crontab /tmp/crontab

# Install prereq packages
sudo apt-get install -y python3-serial python3-websockets python3-jsonschema python3-jinja2

# Update the SPI config
sudo cp /boot/firmware/config.txt /tmp/config.txt
sudo sh -c 'sed "s/#dtparam=spi=on/dtparam=spi=on/" </tmp/config.txt >/boot/firmware/config.txt'
