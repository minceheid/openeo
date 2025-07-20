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
else
    BRANCH=main
    wget https://github.com/minceheid/openeo/archive/refs/heads/$BRANCH.zip -O main.zip
    unzip main.zip
    mv openeo-$BRANCH openeo
    # The crontab will allow openeo to start automatically at boot
    echo "@reboot openeo/boot.bash" >/tmp/crontab 
fi

crontab /tmp/crontab

# Install prereq packages
sudo apt-get install -y python3-serial python3-websockets python3-jsonschema python3-jinja2

# Update the SPI config
sudo cp /boot/firmware/config.txt /tmp/config.txt
sudo sh -c 'sed "s/#dtparam=spi=on/dtparam=spi=on/" </tmp/config.txt >/boot/firmware/config.txt'

echo If you hava previous config.json, please copy it to the new openeo directory.