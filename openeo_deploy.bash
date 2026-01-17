#!/usr/bin/bash 
# ##################
# Openeo deployment script
# This script is version dependant, and should be run to set and/or update the RPi build to be compatible with openeo
# It should be entirely repeatable - if we're updating a config file, we should ensure that we are not just appending
# to it, but refreshing it completely, leaving it in a working state, even if the deploy script is run multiple times
# it is expected that the deploy script is required to be run at every version update or redeployment of software
# v0.7 update - this script now need to be runnable by either the pi user or root, if root, then we cannot use sudo.
# this is to support chroot build of images

MYDIR=$(realpath $(dirname $0))
MYACCOUNT=$(whoami)
HOME=/home/pi

if [ "$(whoami)" = "pi" ]; then
    if [ "$(sudo whoami)" != "root" ]; then
        echo >&2 "Error: the pi user does not appear to have full sudo rights - please check user configuration"
        exit 1
    fi
    SUDO="sudo"
else if [ "$(whoami)" = "root"]; then
    echo ">> Running as root for image deploy"
    SUDO=""
else
    echo >&2 "Error: this deploy script must be run by the pi user"
    exit 1
fi

# Create a config directory, if it isn't already there
# We want to separate config from code, so having a single location outside of the releases area
# is where we want to keep our config
if [ ! -d $PIHOME/etc ]; then
    mkdir -p $PIHOME/etc
    chown pi:pi $PIHOME/etc
fi

# Install prereq packages
$SUDO apt-get update
$SUDO apt-get install -y python3-serial python3-websockets python3-jsonschema python3-jinja2 python3-psutil python3-paho-mqtt dnsmasq iptables


if [ $? -ne 0 ] ; then
	echo >&2 "ERROR: Package Install failed - Deploy Aborted"
	exit 1
fi

# Update the SPI config
$SUDO cp /boot/firmware/config.txt /tmp/config.txt
$SUDO sh -c 'sed "s/#dtparam=spi=on/dtparam=spi=on/" </tmp/config.txt >/boot/firmware/config.txt'

# link the openeo symlink to this release
# using -r as a precaution because previous releases used this path as a directory
# and making sure that we clear up properly. Also using $SUDO as some *very* old releases
# ran as root, which may have left some root owned files
rm -rf $PIHOME/openeo
ln -s $MYDIR $PIHOME/openeo
chown -h pi:pi $PIHOME/openeo

#####################
# Give Python the capability of binding to port 80. This will give our
# script the ability to run without full root privs, which is a Good Thing.
$SUDO setcap CAP_NET_BIND_SERVICE=+eip $(realpath $(which python3))
# Ensure that we are in the right groups
# spi & gpio for communications with the EO control board
# video gives access to pi temperature
$SUDO usermod -a -G spi,gpio,video $(whoami)
$SUDO chmod 666 /dev/vcio

$SUDO cp $MYDIR/etc/openeo.service /etc/systemd/system/
$SUDO cp $MYDIR/etc/rc.local /etc/rc.local

#############
# Setup Portal
echo ">> Deploying Portal Config"
$SUDO cp -r $MYDIR/portal/config/* /


# Enable peristent journals
$SUDO mkdir -p /etc/systemd/journald.conf.d
$SUDO cp $MYDIR/etc/99-permanent-journal.conf /etc/systemd/journald.conf.d

echo ">> Enabling services..."
$SUDO systemctl daemon-reload
$SUDO systemctl enable openeo
$SUDO systemctl force-reload systemd-journald
$SUDO systemctl enable dnsmasq
$SUDO systemctl enable openeo_portal

if [ ! -z "$SUDO" ]; then
    # Don't run these if run by root
    $SUDO systemctl start rc-local.service
    $SUDO systemctl restart openeo
fi
