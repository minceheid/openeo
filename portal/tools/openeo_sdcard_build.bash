#!/bin/bash
MYDIR=$(dirname $0)

################################
# SD Card image builder script.
# You can (probably) run this on the RPi Zero, but I wouldn't recommend it.
# Instead it can be run on any standard x86 linux host.

exec > >(tee file.log)

# === CONFIGURATION ===
BASE_IMAGE_URL="https://downloads.raspberrypi.org/raspios_lite_armhf_latest"
IMAGE_NAME="/tmp/openeo.img"
MOUNT_DIR="/tmp/rpi.$$"

if [ ! -d $MOUNT_DIR ] ; then
	mkdir $MOUNT_DIR
fi

# === PREPARE ===
echo ">> Downloading base image..."
curl -L $BASE_IMAGE_URL | unxz >$IMAGE_NAME

# === SETUP LOOP DEVICE ===
echo ">> Setting up loop device..."
LOOP_DEV=$(sudo losetup --show -Pf "$IMAGE_NAME")
BOOT_DEV="${LOOP_DEV}p1"
ROOT_DEV="${LOOP_DEV}p2"

mkdir -p "$MOUNT_DIR"
sudo mount "$ROOT_DEV" "$MOUNT_DIR"
sudo mount "$BOOT_DEV" "$MOUNT_DIR/boot"

# === CHROOT SETUP ===
echo ">> Copying resolv.conf..."
sudo cp /etc/resolv.conf "$MOUNT_DIR/etc/resolv.conf"

echo ">> Binding system folders..."
for dir in proc sys dev; do
  sudo mount --bind /$dir "$MOUNT_DIR/$dir"
done

#################
## Copy Files
echo ">> Deploying config..."
sudo cp -r $MYDIR/../config/* $MOUNT_DIR/
sudo cp -p $MYDIR/../../openeo_download.py $MOUNT_DIR/

echo ">> Running chroot setup..."
sudo chroot "$MOUNT_DIR" /bin/bash <<'EOF_chroot'

echo ">> Configuring locale"

raspi-config nonint do_hostname openeo
raspi-config nonint do_wifi_country GB
raspi-config nonint do_change_timezone Europe/London

echo ">> Installing OpenEO..."

# Weirdly, at this point in the build, config has not yet been put into /boot/firmware/
# so we need to manipulate the location for the standard openeo_download/deploy scripts
# to work correctly. I wonder if this may change in future OS releases.
mkdir /boot/firmware
cp /boot/config.txt /boot/firmware/config.txt

# Note that openeo_download.py here is being invoked as root. This is the only case that
# we should be doing that - normally this script should be run as the pi user
/openeo_download.py
rm /openeo_download.py

# put the config.txt back where the first boot process expects it to be
mv /boot/firmware/config.txt /boot/config.txt
rmdir /boot/firmware
EOF_chroot

# === CLEANUP ===
echo ">> Cleaning up..."
for dir in $MOUNT_DIR/proc $MOUNT_DIR/sys $MOUNT_DIR/dev $MOUNT_DIR/boot $MOUNT_DIR; do
  echo "Unmounting $dir"
  sudo umount "$dir"
done
rmdir $dir

sudo losetup -d "$LOOP_DEV"

echo ">> Compressing.."
xz -f -T0 $IMAGE_NAME

echo "✅ Done! Image saved as $IMAGE_NAME"