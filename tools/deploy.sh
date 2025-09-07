#!/bin/bash
# A simple script to deploy an application over SSH to the EO charger
# It's insecure, so only use for development purposes
#
# remote_id.txt file should consist of
#   user@<IP/dns name>
#   password
#   base directory
#
# each separated by a new line

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

mapfile -t array < $SCRIPT_DIR/remote_id.txt
REMOTE_NET="${array[0]}"  # N.B. WSL may not route mDNS, so use direct IP if DNS doesn't work
PASS="${array[1]}"
BASE_DIR="${array[2]}"

# This isn't ideal, but the charger rarely runs more than one Python instance.
echo "Stopping existing service."
sshpass -p $PASS ssh $REMOTE_NET "echo $PASS | sudo -S service openeo stop"

echo "Deploying files to ${REMOTE_NET}."
sshpass -p $PASS scp -rp $SCRIPT_DIR/../* $REMOTE_NET:$BASE_DIR/

#echo "Deploying new boot script to ${REMOTE_NET}"
#sshpass -p $PASS scp $SCRIPT_DIR/../boot.bash $REMOTE_NET:$BASE_DIR/

echo "Resuming openeo service."
sshpass -p $PASS ssh $REMOTE_NET "echo $PASS | sudo -S service openeo start"

echo "Complete.  Probably."
