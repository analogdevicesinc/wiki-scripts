#!/bin/bash

PROJECT="$1"
CARRIER_BOARD="$2"

if [ -z "$1" ]
then
  echo "Error: No Project supplied as input argument!"
  exit 1
fi
if [ -z "$2" ]
then
  echo "Error: No Carrier Board supplied as input argument!"
  exit 1
fi
if [ ! command -v quartus_cpf &> /dev/null ]
then
  echo "Error: Location of quartus_cpf not added to the PATH environment variable!"
  exit 1
fi

echo "Build the FPGA's Raw Binary File..."
if [ -d "hdl" ]
then
  cd ./hdl
  git checkout -f "origin/master"
  git fetch
  git checkout -f "origin/master" 2>/dev/null
  cd ..
else
  git clone https://github.com/analogdevicesinc/hdl.git || continue
fi

cd "hdl/projects/$PROJECT/$CARRIER_BOARD"
make
quartus_cpf -c -o bitstream_compression=on "./$PROJECT""_""$CARRIER_BOARD.sof" soc_system.rbf

echo "Build U-Boot..."
mkdir -p software/bootloader
embedded_command_shell.sh bsp-create-settings --type spl --bsp-dir software/bootloader --preloader-settings-dir hps_isw_handoff/system_bd_sys_hps --settings software/bootloader/settings.bsp
cd software/bootloader
if [ -d "u-boot-socfpga" ]
then
  cd ./u-boot-socfpga
  git checkout -f "socfpga_v2020.10"
  git fetch
  git checkout -f "socfpga_v2020.10" 2>/dev/null
  cd ..
else
  git clone https://github.com/altera-opensource/u-boot-socfpga.git || continue
fi

echo "Run the qts_filter..."
cd u-boot-socfpga
./arch/arm/mach-socfpga/qts-filter.sh cyclone5 ../../../ ../ ./board/altera/cyclone5-socdk/qts/

echo "Configure and build U-Boot..."
make socfpga_cyclone5_defconfig
make -j 4

echo "Make extlinux.conf linux configuration file..."
mkdir -p extlinux
echo "LABEL Linux Cyclone V Default" > extlinux/extlinux.conf
echo "    KERNEL ../zImage" >> extlinux/extlinux.conf
echo "    FDT ../socfpga.dtb" >> extlinux/extlinux.conf
echo "    APPEND root=/dev/mmcblk0p2 rw rootwait earlyprintk console=ttyS0,115200n8" >> extlinux/extlinux.conf

echo "Make u-boot.scr file..."
echo "load mmc 0:1 \${loadaddr} soc_system.rbf;" > u-boot.txt
echo "fpga load 0 \${loadaddr} \$filesize;" >> u-boot.txt
./tools/mkimage -A arm -O linux -T script -C none -a 0 -e 0 -n "Cyclone V script" -d u-boot.txt u-boot.scr

echo "Done!"
exit 0
