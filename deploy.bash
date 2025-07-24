#!/usr/bin/bash 
# Usage: ./deploy.bash [version]
# If a version is supplied, download the corresponding release from minceheid/openeo
# Otherwise, download the main branch from minceheid/openeo

if [ -n "$1" ]; then
    VERSION="$1"
    ZIP_URL="https://github.com/minceheid/openeo/releases/download/${VERSION}/openeo-${VERSION}.zip"
    ZIP_FILE="openeo-${VERSION}.zip"
    wget "$ZIP_URL" -O "$ZIP_FILE"
    unzip "$ZIP_FILE" -d "openeo-${VERSION}"
    # The crontab will allow openeo to start automatically at boot
    echo "@reboot openeo-${VERSION}/boot.bash" >/tmp/crontab 

elif [ ! -n "$NODOWNLOAD" ]; then
    # Let us set BRANCH from environment variable. This can help us test
    if [ ! -n "$BRANCH" ]; then
        BRANCH=main
    fi
    rm -rf openeo-${BRANCH}
    curl -L https://github.com/minceheid/openeo/archive/refs/heads/${BRANCH}.tar.gz | tar xvzf -

    if [ -d openeo ]; then
        # Not the first deployment, so we need to preserve the config.json
        if [ -f openeo/config.json ]; then
            echo "Preserving config.json"
            cp openeo/config.json openeo-${BRANCH}/
        fi
        # Delete old archive area
        rm -rf openeo.old
        mv openeo openeo.old
        mv openeo-${BRANCH} openeo

        # we have also updated the deployment, so this deploy script itself might have changed,
        # so we need to call the new one, but tell it that we don't want to download
        # the software yet again
        echo "Relaunching to complete"
        BRANCH=$BRANCH NODOWNLOAD=1 ~/openeo/deploy.bash
        exit $?
    else
        mv openeo-${BRANCH} openeo
    fi
fi

##############################################
# All actions from here must be repeatable. If we're updating a config file,
# ensure that we're not just appending it, but refreshing it completely leaving it
# in a workable state

##############################################
# The crontab will allow openeo to start automatically at boot
# Also add crontab entry to redeploy

TMP_CRONTAB=/tmp/crontab.$$

if [ ! -n "$1" ]; then
    DAY=$(( $RANDOM % 7 ))
    HOUR=$(( $RANDOM % 5 + 9 ))
    MINUTE=$(( $RANDOM % 60 ))
    echo "$MINUTE $HOUR * * $DAY BRANCH=$BRANCH openeo/deploy.bash" >$TMP_CRONTAB
fi

echo "@reboot openeo/boot.bash" >>$TMP_CRONTAB
crontab $TMP_CRONTAB

# Install prereq packages
sudo apt-get install -y python3-serial python3-websockets python3-jsonschema python3-jinja2

# Update the SPI config
sudo cp /boot/firmware/config.txt /tmp/config.txt
sudo sh -c 'sed "s/#dtparam=spi=on/dtparam=spi=on/" </tmp/config.txt >/boot/firmware/config.txt'