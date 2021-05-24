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
  echo "Error: Directory intelFPGA_pro/19.3 not added to PATH."
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

cd hdl/projects/$PROJECT/$CARRIER_BOARD
make
quartus_cpf -c --hps -o bitstream_compression=on ./"$PROJECT""_""$CARRIER_BOARD.sof" soc_system.rbf

echo "Build U-Boot..."
mkdir -p software/bootloader && cd software/bootloader
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
./arch/arm/mach-socfpga/qts-filter-a10.sh ../../../hps_isw_handoff/hps.xml arch/arm/dts/socfpga_arria10_socdk_sdmmc_handoff.h

echo "Make extlinux.conf linux configuration file..."
mkdir -p extlinux
echo "LABEL Linux Arria 10 Default" > extlinux/extlinux.conf
echo "    KERNEL ../zImage" >> extlinux/extlinux.conf
echo "    FDT ../socfpga.dtb" >> extlinux/extlinux.conf
echo "    APPEND root=/dev/mmcblk0p2 rw rootwait earlyprintk console=ttyS0,115200n8" >> extlinux/extlinux.conf

echo "Configure and build U-Boot..."
make socfpga_arria10_defconfig
make -j 4

echo "Create the FIT image..."
echo "/dts-v1/;" > board/altera/arria10-socdk/fit_spl_fpga.its
echo "" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "/ {" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "        description = \"FIT image with FPGA bistream\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "        \#address-cells = <1>;" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "        images {" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                fpga-periph-1 {" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        description = \"FPGA peripheral bitstream\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        data = /incbin/(\"../../../soc_system.periph.rbf\");" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        type = \"fpga\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        arch = \"arm\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        compression = \"none\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                };" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                fpga-core-1 {" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        description = \"FPGA core bitstream\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        data = /incbin/(\"../../../soc_system.core.rbf\");" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        type = \"fpga\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        arch = \"arm\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        compression = \"none\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                };" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "        };" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "        configurations {"  >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                default = \"config-1\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                config-1 {" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        description = \"Boot with FPGA early IO release config\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                        fpga = \"fpga-periph-1\", \"fpga-core-1\";" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "                };" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "        };" >> board/altera/arria10-socdk/fit_spl_fpga.its
echo "};" >> board/altera/arria10-socdk/fit_spl_fpga.its

ln -s ../../../soc_system.core.rbf .
ln -s ../../../soc_system.periph.rbf .
tools/mkimage -E -f board/altera/arria10-socdk/fit_spl_fpga.its fit_spl_fpga.itb

echo "Done!"
exit 0
