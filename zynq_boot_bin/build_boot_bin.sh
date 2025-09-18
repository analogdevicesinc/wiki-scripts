#!/bin/bash
set -ex

XSA_FILE=$1

BUILD_DIR=build_boot_bin
OUTPUT_DIR=output_boot_bin

usage () {
	echo "usage: $0 system_top.xsa [output-archive]"
	exit 1
}

depends () {
	echo Xilinx $1 must be installed and in your PATH
	echo try: source /opt/Xilinx/Vivado/202x.x/settings64.sh
	exit 1
}

### Check command line parameters
echo $XSA_FILE | grep -q ".xsa" || usage

if [ ! -f $XSA_FILE ]; then
	echo $XSA_FILE: File not found!
	usage
fi

### Check for required Xilinx tools (xcst is equivalent with 'xsdk -batch')
command -v xsct >/dev/null 2>&1 || depends xsct
command -v bootgen >/dev/null 2>&1 || depends bootgen

patterns=("zed" "ccfmc_*" "ccbob_*" "usrpe31x" "zc702" "zc706" "coraz7s")

carrier=$(unzip -p $XSA_FILE | grep -a "PATH_TO_FILE" | grep -oE "$(IFS='|'; echo "${patterns[*]}")")
case  $carrier  in
	zed)			UBOOT_FILE="u-boot_zynq_zed.elf" ;;
	ccfmc_*)		UBOOT_FILE="u-boot_zynq_adrv9361.elf" ;;
	ccbob_*)		UBOOT_FILE="u-boot_zynq_adrv9361.elf" ;;
	usrpe31x)		UBOOT_FILE="u-boot-usrp-e310.elf" ;;
	zc702)			UBOOT_FILE="u-boot_zynq_zc702.elf" ;;
	zc706)			UBOOT_FILE="u-boot_zynq_zc706.elf" ;;
	coraz7s)		UBOOT_FILE="u-boot_zynq_coraz7.elf" ;;
	*)
		echo "\n\n!!!!! Undefined carrier name for uboot selection !!!!!\n\n"
		exit 126
esac

tool_version=$(vitis -v | grep -o "Vitis v20[1-9][0-9]\.[0-9] (64-bit)" | grep -o "20[1-9][0-9]\.[0-9]")
if [[ "$tool_version" != "20"[1-9][0-9]"."[0-9] ]] ; then
	echo "Could not determine Vitis version"
	exit 1
fi

boot_partition_location=${tool_version//./_r}

echo "Downloading $UBOOT_FILE ..."
wget https://swdownloads.analog.com/cse/boot_partition_files/$boot_partition_location/$UBOOT_FILE

rm -Rf $BUILD_DIR $OUTPUT_DIR
mkdir -p $OUTPUT_DIR
mkdir -p $BUILD_DIR

cp $XSA_FILE $BUILD_DIR/
cp $UBOOT_FILE $OUTPUT_DIR/u-boot.elf
cp $XSA_FILE $OUTPUT_DIR/

### Create create_fsbl_project.tcl file used by xsct to create the fsbl.
echo "hsi open_hw_design `basename $XSA_FILE`" > $BUILD_DIR/create_fsbl_project.tcl
echo 'set cpu_name [lindex [hsi get_cells -filter {IP_TYPE==PROCESSOR}] 0]' >> $BUILD_DIR/create_fsbl_project.tcl
echo 'platform create -name hw0 -hw system_top.xsa -os standalone -out ./build/sdk -proc $cpu_name' >> $BUILD_DIR/create_fsbl_project.tcl
echo 'platform generate' >> $BUILD_DIR/create_fsbl_project.tcl

FSBL_PATH="$BUILD_DIR/build/sdk/hw0/export/hw0/sw/hw0/boot/fsbl.elf"
SYSTEM_TOP_BIT_PATH="$BUILD_DIR/build/sdk/hw0/hw/system_top.bit"

### Create zynq.bif file used by bootgen
echo 'the_ROM_image:' > $OUTPUT_DIR/zynq.bif
echo '{' >> $OUTPUT_DIR/zynq.bif
echo '[bootloader] fsbl.elf' >> $OUTPUT_DIR/zynq.bif
echo 'system_top.bit' >> $OUTPUT_DIR/zynq.bif
echo 'u-boot.elf' >> $OUTPUT_DIR/zynq.bif
echo '}' >> $OUTPUT_DIR/zynq.bif

### Build fsbl.elf
(
	cd $BUILD_DIR
	xsct create_fsbl_project.tcl
)

### Copy fsbl and system_top.bit into the output folder
cp $FSBL_PATH $OUTPUT_DIR/fsbl.elf
cp $SYSTEM_TOP_BIT_PATH $OUTPUT_DIR/system_top.bit

### Build BOOT.BIN
(
	cd $OUTPUT_DIR
	bootgen -arch zynq -image zynq.bif -o BOOT.BIN -w
)

### Optionally tar.gz the entire output folder with the name given in argument 3
if [ ${#3} -ne 0 ]; then
	tar czvf $3.tar.gz $OUTPUT_DIR
fi
