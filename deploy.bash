#!/usr/bin/bash 
# Usage: ./deploy.bash [version]
# If a version is supplied, download the corresponding release from minceheid/openeo
# Otherwise, download the main branch from minceheid/openeo

MYDIR=$(dirname $0)

if [ -n "$1" ]; then
    VERSION="$1"
    ZIP_URL="https://github.com/minceheid/openeo/releases/download/${VERSION}/openeo-${VERSION}.zip"
    ZIP_FILE="openeo-${VERSION}.zip"
    wget -q "$ZIP_URL" -O "$ZIP_FILE"
    unzip -of "$ZIP_FILE" -d "openeo-${VERSION}"

elif [ ! -n "$NODOWNLOAD" ]; then
    # Let us set BRANCH from environment variable. This can help us test
    if [ ! -n "$BRANCH" ]; then
        BRANCH=main
    fi
    rm -rf openeo-${BRANCH}
    curl -sSL https://github.com/minceheid/openeo/archive/refs/heads/${BRANCH}.tar.gz | tar xvzf -

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

#####################
# Give Python the capability of binding to port 80. This will give our
# script the ability to run without full root privs, which is a Good Thing.
sudo setcap CAP_NET_BIND_SERVICE=+eip $(realpath $(which python3))
# Ensure that we are in the right groups
# spi & gpio for communications with the EO control board
# video gives access to pi temperature
sudo usermod -a -G spi,gpio,video $(whoami)
sudo chmod 666 /dev/vcio

cp $MYDIR/etc/openeo.service /etc/systemd/service

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
