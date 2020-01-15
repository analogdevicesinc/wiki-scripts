#!/bin/sh -e

usage() {
	echo
	echo "======================================================================="
	echo
	echo "Usage: adintool.sh <command> [args]"
	echo "  setup - setup phytool and ethtool required for demo"
	echo "          WARNING: will override system tools"
	echo "  dump_regs <eth> - show all reg values"
	echo "                    WARNING: some registers will be cleared on read"
	echo "  phy_read_mmd <eth> <reg-addr> - read value from a MMD register"
	echo "  phy_write_mmd <eth> <reg-addr> <val> - write value to MMD register"
	echo "  cable_diagnostics <eth> - run cable diagnostics on cable"
	echo "                            WARNING: puts device into special mode."
	echo "                                     device won't send data during this mode"
	echo "  sop <eth> - Show RX & TX Start-of-Packet settings that are configured"
	echo "              The 'phy_write_mmd' command can be used to configure/change settings"
}

[ -n "$1" ] || {
	usage
	exit 1
}

command_exists() {
	local cmd=$1
	[ -n "$cmd" ] || return 1
	type "$cmd" >/dev/null 2>&1
}

install_package() {
	local package="$1"
	# go through known package managers
	for pacman in apt-get brew yum ; do
		command_exists $pacman || continue
		$pacman install -y $package || {
			# Try an update if install doesn't work the first time
			$pacman -y update && \
				$pacman install -y $package
		}
		return $?
	done
	echo "No known package manager found"
	return 1
}

install_packages() {
	while [ -n "$1" ] ; do
		install_package $1 || {
			echo "Error trying to install package $1"
			exit 1
		}
		shift
	done
}

setup() {
	install_packages make gcc git wget
	local tmpdir=$(mktemp -d)
	local back="$(pwd)"
	cd $tmpdir

	git clone https://github.com/wkz/phytool
	cd phytool
	make
	sudo make install
	cd ..

	wget https://mirrors.edge.kernel.org/pub/software/network/ethtool/ethtool-4.19.tar.xz
	tar -xvf ethtool-4.19.tar.xz
	cd ethtool-4.19
	./configure
	make
	sudo make install
	cd ..

	cd $back
}

get_item_from_list() {
	local idx=$1
	shift
	while [ "$idx" -gt 0 ] ; do
		idx=$((idx - 1))
		shift
		[ -n "$1" ] || return
	done
	echo $1
}

index_in_list() {
	local lst="$1"
	local item="$2"
	local idx=0

	for iter in $(eval echo \$$lst) ; do
		if [ "$iter" = "$item" ] ; then
			echo $idx
			return
		fi
		idx=$((idx + 1))
	done

	echo "-1"
}

check_eth_device_or_exit() {
	[ -n "$1" ] || {
		echo "No ethernet name provided"
		exit 1
	}
	[ -d "/sys/class/net/$1" ] || {
		echo "No ethernet device exists with name '$1'"
		usage
		exit 1
	}
}

check_arg_non_empty() {
	[ -n "$1" ] || {
		echo "Invalid/empty argument provided"
		usage
		exit 1
	}
}

phy_read_mmd() {
	local eth="$1"
	local mmd_reg="$2"
	check_eth_device_or_exit "$eth"
	check_arg_non_empty "$mmd_reg"
	phytool write $eth/0/0x10 $mmd_reg
	phytool read $eth/0/0x11
}

phy_write_mmd() {
	local eth="$1"
	local mmd_reg="$2"
	local new="$3"
	check_eth_device_or_exit "$eth"
	check_arg_non_empty "$mmd_reg"
	check_arg_non_empty "$new"
	phytool write $eth/0/0x10 $mmd_reg
	phytool write $eth/0/0x11 $new
}

dump_regs() {
	local eth="$1"

	check_eth_device_or_exit "$eth"

	local idx=0
	echo "PHY core regs:"
	for reg in $__phy_regs ; do
		local val="$(phytool read $eth/0/$reg)"
		local name="$(get_item_from_list $idx $__phy_regnames)"
		echo "$reg = $val - $name"
		idx=$((idx + 1))
	done

	idx=0
	echo "MMD regs:"
	for reg in $__mmd_regs ; do
		local val="$(phy_read_mmd $eth $reg)"
		local name="$(get_item_from_list $idx $__mmd_regnames)"
		echo "$reg = $val - $name"
		idx=$((idx + 1))
	done
}

cable_diagnostics() {
	local eth="$1"

	check_eth_device_or_exit "$eth"

	# Disable linking in PhyCtrl3
	phytool write $eth/0/0x0017 0x2048

	# Enable ClkDiag
	phytool write $eth/0/0x0012 0x0406

	# Run diagnostics
	phy_write_mmd $eth 0xBA1B 0x0001
	# Wait 2 seconds - normally we should poll, but 2 seconds is more than enough
	sleep 2
	local idx=0
	echo "CableDiag Results:"
	for reg in $__cable_diags_rslt_mmd_regs ; do
		local val="$(phy_read_mmd $eth $reg)"
		local mmd_idx=$(index_in_list __mmd_regs $reg)
		local name="$(get_item_from_list $mmd_idx $__mmd_regnames)"
		echo "$reg = $val - $name"
		idx=$((idx + 1))
	done

	# Disable ClkDiag
	phytool write $eth/0/0x0012 0x0402

	# Re-enable linking in PhyCtrl3
	phytool write $eth/0/0x0017 0x3048
}

sop() {
	local eth="$1"

	check_eth_device_or_exit "$eth"

	idx=0
	echo "SOP 1588 regs:"
	for reg in $__sop_regs ; do
		local val="$(phy_read_mmd $eth $reg)"
		local mmd_idx=$(index_in_list __mmd_regs $reg)
		local name="$(get_item_from_list $mmd_idx $__mmd_regnames)"
		echo "$reg = $val - $name"
		idx=$((idx + 1))
	done
}

__phy_regs="0x0000 0x0001 0x0002 0x0003 0x0004 0x0005 0x0006 0x0007 0x0008
	    0x0009 0x000A 0x000F 0x0010 0x0011 0x0012 0x0013 0x0014 0x0015
	    0x0016 0x0017 0x0018 0x0019 0x001A 0x001B 0x001C 0x001D 0x001F"

__phy_regnames="MII_CONTROL MII_STATUS PHY_ID_1 PHY_ID_2 AUTONEG_ADV LP_ABILITY AUTONEG_EXP
		TX_NEXT_PAGE LP_RX_NEXT_PAGE MSTR_SLV_CONTROL MSTR_SLV_STATUS EXT_STATUS
		EXT_REG_PTR EXT_REGD_ATA PHY_CTRL_1 PHY_CTRL_STATUS_1 RX_ER_RCNT
		PHY_CTRL_STATUS_2 PHY_CTRL_2 PHY_CTRL_3 IRQ_MASK IRQ_STATUS PHY_STATUS_1
		LED_CTRL_1 LED_CTRL_2 LED_CTRL_3 PHY_STATUS_2"

__cable_diags_rslt_mmd_regs="0xBA1D 0xBA1E 0xBA1F 0xBA20 0xBA21 0xBA22 0xBA23
			     0xBA24 0xBA25"

__sop_regs="0x9428 0x9429 0x942A 0xFF3D 0xFF3E 0xFF3F 0xFF41"

__mmd_regs="0x8000 0x8001 0x8002 0x8008 0x8402 0x8403 0x8404 0x8405 0x9400
	    0x9401 0x9403 0x9406 0x9407 0x9408 0x940A 0x940B 0x940C 0x940D
	    0x940E 0x940F 0x9410 0x9411 0x9412 0x9413 0x9414 0x9415 0x9416
	    0x9417 0x9418 0x941A 0x941C 0x941D 0x941E 0xA000 0xB412 0xB413
	    0xBA1B 0xBA1C $__cable_diags_rslt_mmd_regs
	    0xBC00
	    0xFF0C 0xFF0D 0xFF1F 0xFF23 0xFF24 0xFF3C 0xFF3D 0xFF3E 0xFF3F
	    0xFF41
	    0x9428 0x9429 0x942A
	    "

__mmd_regnames="EEE_CAPABILITY EEE_ADV EEE_LP_ABILITY EEE_RSLVD MSE_A MSE_B MSE_C
		MSE_D RX_MII_CLK_STOP_EN PCS_STATUS_1 FC_EN FC_IRQ_EN FC_TX_SEL FC_MAX_FRM_SIZE
		FC_FRM_CNT_H FC_FRM_CNT_L FC_LEN_ERR_CNT FC_ALGN_ERR_CNT FC_SYMB_ERR_CNT FC_OSZ_CNT
		FC_USZ_CNT FC_ODD_CNT FC_ODD_PRE_CNT FC_DRIBBLE_BITS_CNT FC_FALSE_CARRIER_CNT
		FG_EN FG_CNTRL_RSTRT FG_CONT_MODE_EN FG_IRQ_EN FG_FRM_LEN FG_NFRM_H FG_NFRM_L
		FG_DONE LPI_WAKE_ERR_CNT B_10_TX_TST_MODE B_100_TX_TST_MODE CDIAG_RUN CDIAG_XPAIR_DIS
		CDIAG_DTLD_RSLTS_0 CDIAG_DTLD_RSLTS_1 CDIAG_DTLD_RSLTS_2 CDIAG_DTLD_RSLTS_3
		CDIAG_FLT_DIST_0 CDIAG_FLT_DIST_1 CDIAG_FLT_DIST_2 CDIAG_FLT_DIST_3 CDIAG_CBL_LEN_EST
		LED_PUL_STR_DUR
		GE_SFT_RST GE_SFT_RST_CFG_EN GE_CLK_CFG GE_RGMII_CFG GE_RMII_CFG GE_LNK_STAT_INV_EN
		GE_IO_GP_CLK_OR_CNTRL GE_IO_GP_OUT_OR_CNTRL GE_IO_INT_N_OR_CNTRL GE_IO_LED_A_OR_CNTRL
		SOP_CTRL SOP_RX_DELAY SOP_TX_DELAY
		"

cmd="$1"

command_exists "$cmd" || {
	echo "Unknown command: $cmd"
	usage
	exit 1
}

shift
$cmd $@
