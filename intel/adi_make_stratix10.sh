#!/bin/bash

PROJECT="$1"
CARRIER="$2"

export CROSS_COMPILE=aarch64-none-linux-gnu-

if [ -d "arm-trusted-firmware" ]
then
	cd ./arm-trusted-firmware
	git fetch
	git checkout -f rel_socfpga_v2.6.0_22.03.02_pr
else
	git clone https://github.com/altera-opensource/arm-trusted-firmware
	cd ./arm-trusted-firmware
	git checkout rel_socfpga_v2.6.0_22.03.02_pr
fi

make bl31 PLAT=stratix10 DEPRECATED=1

cd ..

if [ -d "u-boot-socfpga" ]
then
	cd ./u-boot-socfpga
	git fetch
	git checkout -f rel_socfpga_v2022.01_22.11.02_pr
else
	git clone https://github.com/altera-opensource/u-boot-socfpga
	cd ./u-boot-socfpga
	git checkout rel_socfpga_v2022.01_22.11.02_pr
fi

ln -sf ../arm-trusted-firmware/build/stratix10/release/bl31.bin .
sed -i 's/earlycon panic=-1/earlycon panic=-1 console=ttyS0,115200 root=\/dev\/mmcblk0p2 rw rootwait/g' configs/socfpga_stratix10_defconfig
echo 'CONFIG_BOOTCOMMAND="bridge enable 0xf; setenv ethaddr 00:15:17:ab:cd:ef; load mmc 0:1 ${kernel_addr_r} Image; load mmc 0:1 ${fdt_addr_r} socfpga_stratix10_socdk.dtb; booti ${kernel_addr_r} - ${fdt_addr_r}"' >> configs/socfpga_stratix10_defconfig
make socfpga_stratix10_defconfig
sed -i '/4GB/,/0x80000000>;/creg = <0 0x00000000 0 0x80000000>;' arch/arm/dts/socfpga_stratix10_socdk.dts
make -j 16

cd ..

if [ -d "hdl" ]
then
	cd ./hdl
	git fetch
	git checkout -f origin/master
else
	git clone https://github.com/analogdevicesinc/hdl.git
	cd ./hdl
	git checkout origin/master
fi

cd "projects/$PROJECT/$CARRIER"

make

quartus_pfg -c "$PROJECT""_""$CARRIER.sof" -o hps_path=../../../../u-boot-socfpga/spl/u-boot-spl-dtb.hex "$PROJECT""_""$CARRIER""_hps.sof"
