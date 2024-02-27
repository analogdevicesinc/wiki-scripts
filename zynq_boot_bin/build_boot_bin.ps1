$XSA_FILE=$args[0]
$UBOOT_FILE=$args[1]
$OUT_FILE=$args[2]
$BUILD_DIR='build_boot_bin'
$OUTPUT_DIR='output_boot_bin'

function usage () {
	echo "usage:powershell.exe .\build_boot_bin.ps1 system_top.xsa u-boot.elf [output-archive]"
	exit 1
}

function depends () {
Param (
[string]$cmd
)
	echo "Xilinx $cmd must be installed and in your PATH"
	echo "try: C:\Xilinx\Vitis\202x.x\settings64.bat"
	echo "this will work from Command Prompt"
	exit 1
}

### Check command line parameters
if ($null -eq (echo "$XSA_FILE" | Select-String -Pattern .xsa)) {usage}
if ($null -eq (echo "$UBOOT_FILE" | Select-String -Pattern .elf | Select-String -Pattern u-boot)) {usage}

if (!(Test-Path $XSA_FILE)) {
    echo "$XSA_FILE not found"
    usage
}

if (!(Test-Path $UBOOT_FILE)) {
    echo "$UBOOT_FILE not found"
    usage
}

if (!(Get-Command xsct)) {
    depends "xsct"
}

if (!(Get-Command bootgen)) {
    depends "bootgen"
}

Remove-Item -Recurse -Force -ErrorAction:SilentlyContinue $BUILD_DIR
Remove-Item -Recurse -Force -ErrorAction:SilentlyContinue $OUTPUT_DIR
mkdir -p $OUTPUT_DIR
mkdir -p $BUILD_DIR

cp $XSA_FILE $BUILD_DIR/
cp $UBOOT_FILE $OUTPUT_DIR/u-boot.elf
cp $XSA_FILE $OUTPUT_DIR/

$BASE_XSA=(Get-Item $XSA_FILE).name

echo "hsi open_hw_design $BASE_XSA" | out-file -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'set cpu_name [lindex [hsi get_cells -filter {IP_TYPE==PROCESSOR}] 0]' | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'platform create -name hw0 -hw system_top.xsa -os standalone -out ./build/sdk -proc $cpu_name'  | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl
echo 'platform generate'  | out-file  -Append -encoding ASCII $BUILD_DIR/create_fsbl_project.tcl

### Create zynq.bif file used by bootgen
echo 'the_ROM_image:' | out-file -encoding ASCII $OUTPUT_DIR/zynq.bif
echo '{' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo '[bootloader] fsbl.elf' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo 'system_top.bit' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo 'u-boot.elf' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif
echo '}' | out-file  -Append -encoding ASCII  $OUTPUT_DIR/zynq.bif

### Build fsbl.elf

cd $BUILD_DIR
xsct create_fsbl_project.tcl
cd ..


### Copy fsbl and system_top.bit into the output folder
cp $BUILD_DIR\build\sdk\hw0\export\hw0\sw\hw0\boot\fsbl.elf $OUTPUT_DIR\fsbl.elf
cp $BUILD_DIR\build\sdk\hw0\hw\system_top.bit $OUTPUT_DIR\system_top.bit

cd $OUTPUT_DIR
bootgen -arch zynq -image zynq.bif -o BOOT.BIN -w
cd ..

if ($OUT_FILE) {
    tar czvf "$OUT_FILE.tar.gz" "$OUTPUT_DIR"
}