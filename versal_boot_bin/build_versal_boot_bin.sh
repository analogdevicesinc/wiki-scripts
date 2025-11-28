#!/bin/bash
set -ex

XSA_FILE=$1
UBOOT_FILE=${2:-download}
ATF_FILE=${3:-download}
BUILD_DIR=build_boot_bin
OUTPUT_DIR=output_boot_bin

usage () {
	echo "usage: $0 system_top.xsa (download | u-boot.elf | <path-to-u-boot-source>) (download | bl31.elf | <path-to-arm-trusted-firmware-source>) [output-archive]"
	exit 1
}

depends () {
	echo "Xilinx $1 must be installed and in your PATH"
	echo "try: source /opt/Xilinx/Vivado/202x.x/settings64.sh"
	exit 1
}

build_u_boot () {
	export DEVICE_TREE="versal-$board-rev1.1"
	make distclean
	make xilinx_versal_virt_defconfig
	make
}

build_bl31 () {
	make distclean
	git checkout $atf_version
	make PLAT=versal RESET_TO_BL31=1
}

### Check command line parameters
echo $XSA_FILE | grep -q ".xsa" || usage

if [ ! -f $XSA_FILE ]; then
	echo $XSA_FILE: File not found!
	usage
fi

### Check for required Xilinx tools (starting with 2019.2 there is no hsi anymore)
command -v bootgen >/dev/null 2>&1 || depends bootgen

tool_version=$(vivado -version | sed -n '1p' | cut -d' ' -f 2)
if [ -z "$tool_version" ] ; then
	echo "Could not determine Vivado version"
	exit 1
fi

versal_download_tools_version=$tool_version
if [[ "$tool_version" == *"2025"* ]]; then
	versal_download_tools_version="v2024.2"
fi

rm -Rf $BUILD_DIR $OUTPUT_DIR
mkdir -p $OUTPUT_DIR
mkdir -p $BUILD_DIR
unzip $XSA_FILE -d $BUILD_DIR
board_id=$(grep -E -o 'BoardId="[[:alnum:]]+' $BUILD_DIR/xsa.xml)
board=${board_id#BoardId=\"}
cp $BUILD_DIR/system_top.pdi $OUTPUT_DIR/system_top.pdi
export CROSS_COMPILE=aarch64-linux-gnu-

### Check if UBOOT_FILE is .elf or path to u-boot repository
if [ "$UBOOT_FILE" != "" ] && [ -d $UBOOT_FILE ]; then
### Build u-boot.elf
(
	cd $UBOOT_FILE
	build_u_boot
)
	cp $UBOOT_FILE/u-boot.elf $OUTPUT_DIR/u-boot.elf
elif [ "$UBOOT_FILE" == "download" ]; then
	wget -O $OUTPUT_DIR/u-boot.elf https://github.com/Xilinx/soc-prebuilt-firmware/raw/refs/tags/xilinx_$versal_download_tools_version/$board-versal/u-boot.elf
else
	echo $UBOOT_FILE | grep -q -e ".elf" || usage
	if [ ! -f $UBOOT_FILE ]; then
		echo $UBOOT_FILE: File not found!
		usage
	fi
	cp $UBOOT_FILE $OUTPUT_DIR/u-boot.elf
fi

atf_version=xilinx-$tool_version
if [[ "$atf_version" == "xilinx-v2021.1" ]];then atf_version="xlnx_rebase_v2.4_2021.1";fi
if [[ "$atf_version" == "xilinx-v2021.1.1" ]];then atf_version="xlnx_rebase_v2.4_2021.1_update1";fi

### Check if ATF_FILE is .elf or path to arm-trusted-firmware
if [ "$ATF_FILE" != "" ] && [ -d $ATF_FILE ]; then
### Build arm-trusted-firmware bl31.elf
(
	cd $ATF_FILE
	build_bl31
)
	cp $ATF_FILE/build/versal/release/bl31/bl31.elf $OUTPUT_DIR/bl31.elf
elif [ "$ATF_FILE" == "download" ]; then
	wget -O $OUTPUT_DIR/bl31.elf https://github.com/Xilinx/soc-prebuilt-firmware/raw/refs/tags/xilinx_$versal_download_tools_version/$board-versal/bl31.elf
else
	echo $ATF_FILE | grep -q -e ".elf" || usage
	if [ ! -f $ATF_FILE ]; then
		echo $ATF_FILE: File not found!
		usage
	fi
	cp $ATF_FILE $OUTPUT_DIR/bl31.elf
fi

### Create versal.bif file used by bootgen
echo "the_ROM_image:"                                                   >  $OUTPUT_DIR/versal.bif
echo "{"                                                                >> $OUTPUT_DIR/versal.bif
echo "  image {"                                                        >> $OUTPUT_DIR/versal.bif
echo "    { type=bootimage, file=system_top.pdi}"			>> $OUTPUT_DIR/versal.bif
echo "  }"                                                              >> $OUTPUT_DIR/versal.bif
echo "  image {"                                                        >> $OUTPUT_DIR/versal.bif
echo "    id = 0x1c000000, name=apu_subsystem"                          >> $OUTPUT_DIR/versal.bif
echo "    { core=a72-0, exception_level=el-3, trustzone, file=bl31.elf}">> $OUTPUT_DIR/versal.bif
echo "    { core=a72-0, exception_level=el-2, file=u-boot.elf}"         >> $OUTPUT_DIR/versal.bif
echo "  }"                                                              >> $OUTPUT_DIR/versal.bif
echo "}"                                                                >> $OUTPUT_DIR/versal.bif

### Create boot.txt files used to create boot.src
echo ' '                                     >  $OUTPUT_DIR/boot.txt
echo 'Load boot image from ${boot_target}...'>> $OUTPUT_DIR/boot.txt
echo 'fatload mmc 0 0x00200000 Image'        >> $OUTPUT_DIR/boot.txt
echo 'fatload mmc 0 0x00001000 system.dtb'   >> $OUTPUT_DIR/boot.txt
echo 'booti 0x00200000 - 0x00001000'         >> $OUTPUT_DIR/boot.txt

### Build BOOT.BIN file and boot.src (replacement for uEnv.txt for versal boards)
(
	cd $OUTPUT_DIR
	bootgen -image versal.bif -arch versal -o BOOT.BIN -w -log trace
	mkimage -A arm -O linux -T script -C none -a 0 -e 0 -n "Boot script for Versal" -d boot.txt boot.scr
)

### Optionally tar.gz the entire output folder with the name given in argument 4/5
if [[ ( $4 == "uart"* && ${#5} -ne 0 ) ]]; then
	tar czvf $5.tar.gz $OUTPUT_DIR
fi

if [[ ( ${#4} -ne 0 && $4 != "uart"* && ${#5} -eq 0 ) ]]; then
        tar czvf $4.tar.gz $OUTPUT_DIR
fi
