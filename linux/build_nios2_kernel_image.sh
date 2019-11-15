#!/bin/bash
set -e

DEFCONFIG=adi_nios2_defconfig
DTDEFAULT=a10gx_adrv9371.dts

CROSS_COMPILE="$1"
LINUX_DIR=${2:-linux-adi}
BRANCH="${3:-altera_4.9}"
DTFILE="$4"

ARCH=nios2

IMG_NAME=zImage

NUM_JOBS=${NUM_JOBS:-4}

KCFLAGS="-Wno-error=frame-larger-than="
export KCFLAGS

# if CROSS_COMPILE hasn't been specified, fail here
# we don't have a good alternative to download at the moment
[ -n "$CROSS_COMPILE" ] || {
	echo "usage: <path-to-nios2-toolchain> [linux-dir] [branch] [DTFILE]"
	echo "Please specify a Nios 2 toolchain prefix."
	exit 1
}

# Get ADI Linux if not downloaded
# We won't do any `git pull` to update the tree, users can choose to do that manually
[ -d "$LINUX_DIR" ] || \
	git clone https://github.com/analogdevicesinc/linux.git "$LINUX_DIR"

if [ -z "$DTFILE" ] ; then
	echo
	echo "No DTFILE file specified ; using default '$DTDEFAULT'"
	DTFILE=$DTDEFAULT
fi

export ARCH
export CROSS_COMPILE

pushd "$LINUX_DIR"

git checkout "$BRANCH"

[ -e arch/nios2/boot/rootfs.cpio.gz ] || \
	wget http://wiki.analog.com/_media/resources/tools-software/linux-drivers/platforms/nios2/rootfs_nios2.cpio.gz \
	-P arch/nios2/boot/rootfs.cpio.gz

make $DEFCONFIG

cp -f arch/$ARCH/boot/dts/$DTFILE arch/$ARCH/boot/devicetree.dts

make -j$NUM_JOBS $IMG_NAME

popd 1> /dev/null

cp -f $LINUX_DIR/arch/$ARCH/boot/$IMG_NAME .

echo
echo "Exported files: $IMG_NAME"
