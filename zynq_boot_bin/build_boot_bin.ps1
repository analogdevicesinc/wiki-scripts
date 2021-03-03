$HDF_FILE=$args[0]
$UBOOT_FILE=$args[1]
$OUT_FILE=$args[2]
$BUILD_DIR='build_boot_bin'
$OUTPUT_DIR='output_boot_bin'

function usage () {
	echo "usage: build_boot_bin.ps1 system_top.hdf u-boot.elf [output-archive]"
	exit 1
}

function depends () {
Param (
[string]$cmd
)
	echo "Xilinx $cmd must be installed and in your PATH"
	echo "try: source /opt/Xilinx/Vivado/201x.x/settings64.sh"
	exit 1
}

### Check command line parameters
if ($null -eq (echo "$HDF_FILE" | Select-String -Pattern .hdf)) {usage}
if ($null -eq (echo "$UBOOT_FILE" | Select-String -Pattern .elf | Select-String -Pattern u-boot)) {usage}

if (!(Test-Path $HDF_FILE)) {
    echo "$HDF_FILE not found"
    usage
}

if (!(Test-Path $UBOOT_FILE)) {
    echo "$UBOOT_FILE not found"
    usage
}

if (!(Get-Command xsdk)) {
    depends "xsdk"
}

if (!(Get-Command bootgen)) {
    depends "bootgen"
}

Remove-Item -Recurse -Force -ErrorAction:SilentlyContinue $BUILD_DIR
Remove-Item -Recurse -Force -ErrorAction:SilentlyContinue $OUTPUT_DIR
mkdir -p $OUTPUT_DIR
mkdir -p $BUILD_DIR

cp $HDF_FILE $BUILD_DIR/
cp $UBOOT_FILE $OUTPUT_DIR/u-boot.elf
cp $HDF_FILE $OUTPUT_DIR/

$BASE_HDF=(Get-Item $HDF_FILE).name

echo "hsi open_hw_design $BASE_HDF" | out-file -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'set cpu_name [lindex [hsi get_cells -filter {IP_TYPE==PROCESSOR}] 0]' | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'sdk setws ./build/sdk'  | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo "sdk createhw -name hw_0 -hwspec $BASE_HDF"  | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'sdk createapp -name fsbl -hwproject hw_0 -proc $cpu_name -os standalone -lang C -app {Zynq FSBL}'  | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'configapp -app fsbl build-config release'  | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'sdk projects -build -type all'  | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl

### Create zynq.bif file used by bootgen
echo 'the_ROM_image:' | out-file -encoding ASCII $OUTPUT_DIR/zynq.bif
echo '{' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo '[bootloader] fsbl.elf' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo 'system_top.bit' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo 'u-boot.elf' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo '}' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif

### Build fsbl.elf

cd $BUILD_DIR
xsdk -batch -source create_fsbl_project.tcl
cd ..


### Copy fsbl and system_top.bit into the output folder
cp $BUILD_DIR\build\sdk\fsbl\Release\fsbl.elf $OUTPUT_DIR\fsbl.elf
cp $BUILD_DIR\build\sdk\hw_0\system_top.bit $OUTPUT_DIR\system_top.bit

cd $OUTPUT_DIR
bootgen -arch zynq -image zynq.bif -o BOOT.BIN -w
cd ..

if ($OUT_FILE) {
    tar czvf "$OUT_FILE.tar.gz" "$OUTPUT_DIR"
}