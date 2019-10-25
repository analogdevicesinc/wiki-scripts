#!/bin/bash
set -e

# Usage: build_zynq_kernel_image.sh [kernel_dir] [dt_file] [path_cross_toolchain]
#  If no dt_file is specified, the default is `zynq-zc702-adv7511-ad9361-fmcomms2-3.dtb`
#  If no CROSS_COMPILE specified, a GCC toolchain will be downloaded
#  from Linaro's website and used.
#  Default host for Linaro's toolchain is assumed x86_64 but it can be
#  overriden with `HOST=i686 ./build_zynq_kernel_image.sh [opts]`
#
# Notes:
# - it's recommened to run this into a build dir, to make things easier to cleanup
# - this script is not particularly good at tolerating interruptions,
#   so, if you decide to interrupt this mid-way, you may need to cleanup stuff
#

LINUX_DIR="${1:-linux-adi}"
DTFILE="$2"
CROSS_COMPILE="$3"

HOST=${HOST:-x86_64}

DEFCONFIG=zynq_xcomm_adv7511_defconfig
GCC_ARCH=arm-linux-gnueabihf
IMG_NAME="uImage"
ARCH=arm
DTDEFAULT=zynq-zc702-adv7511-ad9361-fmcomms2-3.dtb

KCFLAGS="-Werror -Wno-error=frame-larger-than="
export KCFLAGS

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

