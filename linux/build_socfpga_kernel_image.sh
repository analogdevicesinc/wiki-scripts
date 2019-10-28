#!/bin/bash
set -e

LINUX_DIR="${1:-linux-adi}"
DTFILE="$2"
CROSS_COMPILE="$3"

HOST=${HOST:-x86_64}

DEFCONFIG=socfpga_adi_defconfig
GCC_ARCH=arm-linux-gnueabihf
IMG_NAME="zImage"
ARCH=arm
DTDEFAULT=socfpga_arria10_socdk_sdmmc.dts

[ -n "$NUM_JOBS" ] || NUM_JOBS=5

GCC_VERSION="8.3-2019.03"

# if CROSS_COMPILE hasn't been specified, go with Linaro's
[ -n "$CROSS_COMPILE" ] || {
	# set Linaro GCC
	GCC_DIR="gcc-arm-${GCC_VERSION}-${HOST}-${GCC_ARCH}"
	GCC_TAR="$GCC_DIR.tar.xz"
	GCC_URL="https://developer.arm.com/-/media/Files/downloads/gnu-a/${GCC_VERSION}/binrel/${GCC_TAR}"
	if [ ! -d "$GCC_DIR" ] && [ ! -e "$GCC_TAR" ] ; then
		wget "$GCC_URL"
	fi
	if [ ! -d "$GCC_DIR" ] ; then
		tar -xvf $GCC_TAR || {
			echo "'$GCC_TAR' seems invalid ; remove it and re-download it"
			exit 1
		}
	fi
	CROSS_COMPILE=$(pwd)/$GCC_DIR/bin/${GCC_ARCH}-
}

# FIXME: remove the line below once Talise & Mykonos APIs
#        dont't use 1024 bytes on stack
KCFLAGS="$KCFLAGS -Wno-error=frame-larger-than="
export KCFLAGS

# FIXME: remove this function once kernel gets upgrade and
#        GCC doesn't report these warnings anymore
GCC="${CROSS_COMPILE}gcc"
if [ "$($GCC -dumpversion | cut -d. -f1)" -ge "8" ]; then
	KCFLAGS="$KCFLAGS -Wno-error=stringop-truncation"
	KCFLAGS="$KCFLAGS -Wno-error=packed-not-aligned"
	KCFLAGS="$KCFLAGS -Wno-error=stringop-overflow= -Wno-error=sizeof-pointer-memaccess"
	KCFLAGS="$KCFLAGS -Wno-error=missing-attributes"
fi

if [ "$($GCC -dumpversion | cut -d. -f1)" -ge "9" ]; then
	KCFLAGS="$KCFLAGS -Wno-error=address-of-packed-member -Wno-error=stringop-truncation"
fi
export KCFLAGS

# Get ADI Linux if not downloaded
# We won't do any `git pull` to update the tree, users can choose to do that manually
[ -d "$LINUX_DIR" ] || \
	git clone https://github.com/analogdevicesinc/linux.git "$LINUX_DIR"

export ARCH
export CROSS_COMPILE

pushd "$LINUX_DIR"

make $DEFCONFIG

make -j$NUM_JOBS $IMG_NAME UIMAGE_LOADADDR=0x8000

if [ -z "$DTFILE" ] ; then
	echo
	echo "No DTFILE file specified"
	echo
else
	make $DTFILE
fi

popd 1> /dev/null

cp -f $LINUX_DIR/arch/$ARCH/boot/$IMG_NAME .
[ -z "$DTFILE" ] || \
	cp -f $LINUX_DIR/arch/$ARCH/boot/dts/$DTFILE .

echo "Exported files: $IMG_NAME, $DTFILE"

