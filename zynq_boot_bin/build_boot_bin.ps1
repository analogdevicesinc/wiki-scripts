$XSA_FILE=$args[0]
$UBOOT_FILE=if ($args.Length -ge 2 -and $args[1]) { $args[1] } else { "download" }
$OUT_FILE=$args[2]
$BUILD_DIR='build_boot_bin'
$OUTPUT_DIR='output_boot_bin'

function usage () {
	echo "usage:powershell.exe .\build_boot_bin.ps1 system_top.xsa (u-boot.elf | download) [output-archive]"
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

$tool_version = (& vitis -v | Select-String -Pattern "Vitis v20[1-9][0-9]\.[0-9] \(64-bit\)" | 
                 ForEach-Object { ($_ -match "20[1-9][0-9]\.[0-9]") ; $Matches[0] })


if ($UBOOT_FILE -eq "download") {
	$patterns = @("zed", "ccfmc_.*", "ccbob_.*", "usrpe31x", "zc702", "zc706", "coraz7s")
	$regex = $patterns -join '|'
	$fullPath = (Get-Item $XSA_FILE).FullName
	$dir = Split-Path $fullPath
	$newName = (Get-Item $XSA_FILE).BaseName + ".zip"
	$renamedFilePath = Join-Path $dir $newName
	$extractLocation = Join-Path $dir "extractedXSA"
	Copy-Item $XSA_FILE $renamedFilePath
	Expand-Archive -Path $renamedFilePath -DestinationPath $extractLocation -Force

	# Search inside extracted files
	$line = Get-ChildItem -Path $extractLocation\*.hwh -Recurse -File |
	    Get-Content |
	    Select-String -Pattern "PATH_TO_FILE" |
		Select-Object -First 1 -ExpandProperty Line
	$carrier = [regex]::Match($line, $regex).Value	

	switch -Wildcard ($carrier) {
	    "zed"      { $UBOOT_FILE = "u-boot_zynq_zed.elf" }
	    "ccfmc_*"  { $UBOOT_FILE = "u-boot_zynq_adrv9361.elf" }
	    "ccbob_*"  { $UBOOT_FILE = "u-boot_zynq_adrv9361.elf" }
	    "usrpe31x" { $UBOOT_FILE = "u-boot-usrp-e310.elf" }
	    "zc702"    { $UBOOT_FILE = "u-boot_zynq_zc702.elf" }
	    "zc706"    { $UBOOT_FILE = "u-boot_zynq_zc706.elf" }
	    "coraz7s"  { $UBOOT_FILE = "u-boot_zynq_coraz7.elf" }
	    Default {
	        Write-Host "`n`n!!!!! Undefined carrier name for uboot selection !!!!!`n`n"
	        exit 1
	    }
	}

	$boot_partition_location = $tool_version -replace "\.", "_r"

	Write-Host "Downloading $UBOOT_FILE ..."
	Invoke-WebRequest -Uri "https://swdownloads.analog.com/cse/boot_partition_files/uboot/$boot_partition_location/$UBOOT_FILE" -OutFile $UBOOT_FILE
}
else {
	if ($UBOOT_FILE -notmatch "\.elf" -and $UBOOT_FILE -notmatch "uboot" -and $UBOOT_FILE -notmatch "u-boot") {
        	usage
    	}
	if (-not (Test-Path $UBOOT_FILE)) {
        	Write-Host "$UBOOT_FILE: File not found!"
        	usage
	}
}

if (!(Get-Command xsct)) {
    depends "xsct"
}

if (!(Get-Command bootgen)) {
    depends "bootgen"
}

if (-not ($tool_version -match "^20[1-9][0-9]\.[0-9]$")) {
    Write-Host "Could not determine Vitis version"
    exit 1
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
