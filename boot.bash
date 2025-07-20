#!/usr/bin/bash

cd ~/openeo

#####################
echo "Wait for network connectivity (checks for default route)"
while ! ip route | grep -q default; do
    echo "Waiting for network..."
    sleep 2
done

echo "Network is up."


#####################
# Give Python the capability of binding to port 80. This will give our
# script the ability to run without full root privs, which is a Good Thing.
sudo setcap CAP_NET_BIND_SERVICE=+eip $(realpath $(which python3))
# Ensure that we are in the right groups
# spi & gpio for communications with the EO control board
# video gives access to pi temperature
sudo usermod -a -G spi,gpio,video $(whoami)
sudo chmod 666 /dev/vcio


# Main charger program - running in a loop, in case we hit a catastrophic
# bug for some reason Main logging is now done through journalctl, however,
# we still capture stdout/stderr, just in case
#
# We stop running if the file /tmp/openeo-dev-kill is created; this is an 
# override to allow SSH to replace the running application.
#
while [ ! -f /tmp/openeo-dev-kill ] ; do
	./openeo.py 2>&1 >openeo.log
done

