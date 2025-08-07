#!/bin/bash
MYDIR=$(dirname $0)

################################
# SD Card image builder script.
# You can (probably) run this on the RPi Zero, but I wouldn't recommend it.
# Instead it can be run on any standard x86 linux host.

exec > >(tee file.log)

# === CONFIGURATION ===
BASE_IMAGE_URL="https://downloads.raspberrypi.org/raspios_lite_armhf_latest"
IMAGE_NAME="openeo.img"
MOUNT_DIR="/tmp/rpi.$$"
WORK_DIR="."

if [ ! -d $MOUNT_DIR ] ; then
	mkdir $MOUNT_DIR
fi

# === PREPARE ===

if [ ! -d $WORK_DIR ] ; then
	mkdir -p $WORK_DIR
fi

cd "$WORK_DIR"

BASE_IMAGE=latest.img
if [ ! -f $BASE_IMAGE ] ; then
	echo ">> Downloading base image..."
	curl -L $BASE_IMAGE_URL | unxz >$BASE_IMAGE
else
	echo ">> Skipping base image download..."
fi

echo ">> Making a copy of $BASE_IMAGE..."
cp "$BASE_IMAGE" "$IMAGE_NAME"

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

echo ">> Running chroot setup..."
sudo chroot "$MOUNT_DIR" /bin/bash <<'EOF_chroot'

raspi-config nonint do_hostname openeo
raspi-config nonint do_wifi_country GB
raspi-config nonint do_change_timezone Europe/London

echo ">> Installing packages..."

#############
## Deploy openeo
# Weirdly, at this point in the build, config has not yet been put into /boot/firmware/
mkdir /boot/firmware
cp /boot/config.txt /boot/firmware/config.txt
su - pi -c "wget https://raw.githubusercontent.com/minceheid/openeo/refs/heads/main/deploy.bash -O /tmp/deploy.bash"
su - pi -c "bash /tmp/deploy.bash"
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
xz -f -9e $IMAGE_NAME

echo "✅ Done! Image saved as $WORK_DIR/$IMAGE_NAME"

