#!/bin/bash
set -e

LINUX_DIR="${1:-linux-adi}"
DTFILE="$2"
CROSS_COMPILE="$3"

HOST=${HOST:-x86_64}

DEFCONFIG=adi_bcm2709_defconfig
GCC_ARCH=arm-linux-gnueabi
IMG_NAME="zImage"
ARCH=arm

[ -n "$NUM_JOBS" ] || NUM_JOBS=5

LINARO_GCC_VERSION="5.5.0-2017.10"

get_linaro_link() {
	local ver="$1"
	local gcc_dir="${ver:0:3}-${ver:(-7)}"
	echo "https://releases.linaro.org/components/toolchain/binaries/$gcc_dir/$GCC_ARCH/$GCC_TAR"
}

# if CROSS_COMPILE hasn't been specified, go with Linaro's
[ -n "$CROSS_COMPILE" ] || {
	# set Linaro GCC
	GCC_DIR=gcc-linaro-${LINARO_GCC_VERSION}-${HOST}_${GCC_ARCH}
	GCC_TAR=$GCC_DIR.tar.xz
	if [ ! -d "$GCC_DIR" ] && [ ! -e "$GCC_TAR" ] ; then
		wget "$(get_linaro_link "$LINARO_GCC_VERSION")"
	fi
	if [ ! -d "$GCC_DIR" ] ; then
		tar -xvf $GCC_TAR || {
			echo "'$GCC_TAR' seems invalid ; remove it and re-download it"
			exit 1
		}
	fi
	CROSS_COMPILE=$(pwd)/$GCC_DIR/bin/${GCC_ARCH}-
}

# Get ADI Linux if not downloaded
# We won't do any `git pull` to update the tree, users can choose to do that manually
[ -d "$LINUX_DIR" ] || {
	git clone https://github.com/analogdevicesinc/linux.git "$LINUX_DIR"
	git checkout rpi-4.19.y
}

export ARCH
export CROSS_COMPILE

pushd "$LINUX_DIR"

make $DEFCONFIG

make -j$NUM_JOBS

popd 1> /dev/null

cp -f $LINUX_DIR/arch/$ARCH/boot/$IMG_NAME .

echo "Exported files: $IMG_NAME"

