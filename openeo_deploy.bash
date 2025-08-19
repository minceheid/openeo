#!/usr/bin/bash 
# ##################
# Openeo deployment script
# This script is version dependant, and should be run to set and/or update the RPi build to be compatible with openeo
# It should be entirely repeatable - if we're updating a config file, we should ensure that we are not just appending
# to it, but refreshing it completely, leaving it in a working state, even if the deploy script is run multiple times
# it is expected that the deploy script is required to be run at every version update or redeployment of software

MYDIR=$(realpath $(dirname $0))
MYACCOUNT=$(whoami)

if [ "$(whoami)" != "pi" ]; then
    echo >&2 "Error: this deploy script must be run by the pi user"
    exit 1
fi

if [ "$(sudo whoami)" != "root" ]; then
    echo >&2 "Error: the pi user does not appear to have full sudo rights - please check user configuration"
    exit 1
fi
##############################################
# All actions from here must be repeatable. If we're updating a config file,
# ensure that we're not just appending it, but refreshing it completely leaving it
# in a workable state


# Create a config directory, if it isn't already there
# We want to separate config from code, so having a single location outside of the releases area
# is where we want to keep our config
if [ ! -d /home/pi/etc ]; then
    mkdir /home/pi/etc
fi

# Install prereq packages
sudo apt-get update
sudo apt-get install -y python3-serial python3-websockets python3-jsonschema python3-jinja2 python3-psutil dnsmasq nginx fcgiwrap spawn-fcgi iptables at

if [ $? -ne 0 ] ; then
	echo >&2 "ERROR: Package Install failed - Deploy Aborted"
	exit 1
fi

# Update the SPI config
sudo cp /boot/firmware/config.txt /tmp/config.txt
sudo sh -c 'sed "s/#dtparam=spi=on/dtparam=spi=on/" </tmp/config.txt >/boot/firmware/config.txt'

# www-data needs to be able to see the pi directory
chmod 755 /home/pi

# link the openeo symlink to this release
# using -r as a precaution because previous releases used this path as a directory
# and making sure that we clear up properly. Also using sudo as some *very* old releases
# ran as root, which may have left some root owned files
rm -rf /home/pi/openeo
ln -s $MYDIR /home/pi/openeo

#####################
# Give Python the capability of binding to port 80. This will give our
# script the ability to run without full root privs, which is a Good Thing.
sudo setcap CAP_NET_BIND_SERVICE=+eip $(realpath $(which python3))
# Ensure that we are in the right groups
# spi & gpio for communications with the EO control board
# video gives access to pi temperature
sudo usermod -a -G spi,gpio,video $(whoami)
sudo chmod 666 /dev/vcio

sudo cp $MYDIR/etc/openeo.service /etc/systemd/system/
######
# Remove old crontab, if it exists (we previously used crontab in earlier releases)
crontab -r

#############
# Setup Portal
echo ">> Deploying Portal Config"
sudo cp -r $MYDIR/portal/config/* /
sudo rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/openeo_portal.conf
sudo ln -s /etc/nginx/sites-available/openeo_portal.conf  /etc/nginx/sites-enabled/openeo_portal.conf

echo ">> Enabling services..."
sudo systemctl daemon-reload
sudo systemctl disable nginx
sudo systemctl disable dnsmasq
sudo systemctl enable openeo
sudo systemctl restart openeo
##########
## Portal disabled for now - we have some sort of race condition error
sudo systemctl disable openeo_portal