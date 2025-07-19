#!/usr/bin/bash

cd ~/eo

#####################
echo "Wait for network connectivity (checks for default route)"
while ! ip route | grep -q default; do
    echo "Waiting for network..."
    sleep 2
done

echo "Network is up."


#####################

# Main charger program - running in a loop, in case we hit a catastrophic
# bug for some reason Main logging is now done through journalctl, however,
# we still capture stdout/stderr, just in case
#
# We stop running if the file /tmp/openeo-dev-kill is created; this is an 
# override to allow SSH to replace the running application.
#
while [ ! -f /tmp/openeo-dev-kill ] ; do
	sudo ./openeo.py 2>&1 >openeo.log
done

