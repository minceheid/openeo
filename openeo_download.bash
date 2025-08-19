#!/usr/bin/bash 
# Usage: ./deploy.bash [version]
# If a version is supplied, download the corresponding release from minceheid/openeo
# Otherwise, download the main branch from minceheid/openeo

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

####################
# If this is the first time that this has been run, then the releases directory won't have been created, so
# lets do that.

if [ -d /home/pi/releases ]; then
    mkdir /home/pi/releases
fi
cd /home/pi/releases

if [ -n "$1" ]; then
    RELEASE="$1"
    rm -rf "openeo-${RELEASE}"
    URL="https://github.com/minceheid/openeo/archive/refs/tags/${RELEASE}.tar.gz"
    curl -sSL "$URL" | tar xvzf -
    
    if [ $? -ne 0 ]; then
        echo >&2 "Error - download failed ($URL)"
        exit 2
    fi
else
    RELEASE="main"
    rm -rf "openeo-${RELEASE}"
    URL="https://github.com/minceheid/openeo/archive/refs/heads/${RELEASE}.tar.gz"
    curl -sSL "$URL" | tar xvzf -

    if [ $? -ne 0 ]; then
        echo >&2 "Error - download failed ($URL)"
        exit 2
    fi
fi


DEPLOY="/home/pi/releases/openeo-{$RELEASE}/openeo_deploy.bash"
if [ -x "$DEPLOY" ]; then
    echo "Running openeo_deploy script ($DEPLOY)"
    $DEPLOY
    echo "Deployment complete. A reboot is recommended."
else
    echo >&2 "Error - could not find deploy script. Perhaps download failed?"
    exit 3
fi