#!/bin/bash

echo_red()   { printf "\033[1;31m$*\033[m\n"; }
echo_green() { printf "\033[1;32m$*\033[m\n"; }
echo_blue()  { printf "\033[1;34m$*\033[m\n"; }

usage() {
	echo_red "Usage: compare_img_with_sdcard.sh <img_file> <sdcard-device>"
	exit 1
}

usage_insufficient_args() {
	echo_red "Insufficient arguments"
	usage
}

command_exists() {
	local cmd=$1
	[ -n "$cmd" ] || return 1
	type "$cmd" >/dev/null 2>&1
}

for cmd in sudo fdisk ; do
	command_exists $cmd || {
		echo_red "Script requires '$cmd' installed on system"
		exit 1
	}
done

[ -n "$1" ] || usage_insufficient_args
[ -n "$2" ] || usage_insufficient_args

img_file="$1"
sdcard_dev="$2"

[ -f "$img_file" ] || {
	echo_red "File doesn't exit '$img_file'"
	exit 1
}

[ -e "$sdcard_dev" ] || {
	echo_red "SD-card device doesn't exit '$sdcard_dev'"
	exit 1
}

get_fdisk_output() {
	local dev="$1"
	local flt="$2"

	if [ -n "$flt" ] ; then
		sudo fdisk -l "$dev" | grep "$flt"
	else
		sudo fdisk -l "$dev"
	fi
}

compare_fdisk_output_disk_units() {
	local img_file="$1"
	local sdcard_dev="$2"

	#
	# The stuff below should match img and the actual disk
	#
	# Units: sectors of 1 * 512 = 512 bytes
	# Sector size (logical/physical): 512 bytes / 512 bytes
	# I/O size (minimum/optimal): 512 bytes / 512 bytes
	# Disklabel type: dos
	# Disk identifier: 0x00096174

	for flt in 'Units' 'Sector size' 'I/O size' 'Disklabel type' 'Disk identifier' ; do
		out1=$(get_fdisk_output "$img_file" "$flt")
		out2=$(get_fdisk_output "$sdcard_dev" "$flt")

		[ -n "$out1" ] || {
			echo_red "Output for '$flt' on '$img_file' is empty"
			exit 1
		}

		[ -n "$out2" ] || {
			echo_red "Output for '$flt' on '$sdcard_dev' is empty"
			exit 1
		}

		if [ "$out1" != "$out2" ] ; then
			echo_red "Output differs for '$flt'"
			echo_red "  '$img_file' is '$out1'"
			echo_red "  '$sdcard_dev' is '$out2'"
			exit 1
		fi

		echo_green "Output matches: '$out1'"
	done
}

compare_fdisk_output_parititions() {
	local img_file="$1"
	local sdcard_dev="$2"

	local out1=$(get_fdisk_output "$img_file" "$img_file" | grep -v Disk)
	local out2=$(get_fdisk_output "$sdcard_dev" "$sdcard_dev" | grep -v Disk)

	[ -n "$out1" ] || {
		echo_red "Partitions for '$img_file' not found"
		exit 1
	}

	[ -n "$out2" ] || {
		echo_red "Partitions for '$sdcard_dev' not found"
		exit 1
	}

	# FIXME: find a better way to sanitize paths
	local s1img=$(echo $img_file | sed 's/\//_/g')
	local s1sd=$(echo $sdcard_dev | sed 's/\//_/g')
	local out1a=$(echo $out1 | sed 's/\//_/g' | sed "s/$s1img/common/g")
	local out2a=$(echo $out2 | sed 's/\//_/g' | sed "s/$s1sd/common/g")

	if [ "$out1a" != "$out2a" ] ; then
		echo_red "Fdisk partition info mismatch between partitions"
		echo_red "-----------------$img_file----------------------"
		echo_red "$out1"
		echo_red "-----------------$sdcard_dev--------------------"
		echo_red "$out2"
		echo_red "------------------------------------------------"
		exit 1
	fi

	echo_green "Fdisk partition tables match"
	echo_green "-----------------------------------------------------"
	get_fdisk_output "$img_file" "$img_file" | grep -v Disk
	echo_green "-----------------------------------------------------"
}

get_item_from_list() {
	local idx=$1
	shift
	while [ "$idx" -gt 0 ] ; do
		idx=$((idx - 1))
		shift
	done
	echo $1
}

__partition_check_and_compute() {
	# This relies on the fact that fdisk lists partitions with dev1..N for dev
	local out=$(get_fdisk_output "$if" "${if}${part_idx}")

	[ -n "$out" ] || {
		echo_red "Got empty fdisk output for '${if}${part_idx}'"
		exit 1
	}

	off=$(get_item_from_list 1 $out)
	cnt=$(get_item_from_list 3 $out)

	[ -n "$off" ] || {
		echo_red "Got empty offset for '${if}${part_idx}'"
		exit 1
	}

	[ -n "$cnt" ] || {
		echo_red "Got empty count for '${if}${part_idx}'"
		exit 1
	}
}

dd_partition_to_file() {
	local if="$1"
	local part_idx="$2"
	local of="$3"
	local bs="$4"

	local off
	local cnt

	__partition_check_and_compute

	echo_green "Dumping '${if}${part_idx}' -> '$of': off=$off, cnt=$cnt, bs=$bs"
	echo_green "dd command is: 'sudo dd if="$if" of="$of" skip=$off count=$cnt bs=$bs status=progress'"

	sudo dd if="$if" of="$of" skip=$off count=$cnt bs=$bs status=progress || {
		echo_red "Error when dumping to file '${if}${part_idx}'"
		exit 1
	}
}

mount_partition_to_dir() {
	local if="$1"
	local part_idx="$2"
	local of="$3"
	local bs="$4"

	__partition_check_and_compute

	off=$((off * bs))
	[ -n "$off" ] || {
		echo_red "Got empty offset for '${if}${part_idx}'"
		exit 1
	}

	echo_green "Mounting partition '${if}${part_idx}' with cmd 'sudo mount -o loop,offset=$off $if $of'"

	sudo mount -o loop,offset=$off $if $of || {
		echo_red "Error during mounting '${if}${part_idx}'"
		exit 1
	}
}

compare_partition_checksums() {
	local img_file="$1"
	local sdcard_dev="$2"
	local part_idx
	local part_cnt
	local one_part_is_bad=0

	local tmp1=$(mktemp)
	local tmp2=$(mktemp)

	local bs=$(get_fdisk_output "$img_file" "Units" | grep Units | cut -d= -f2 | cut -db -f1)
	# convert to a more numerical representation
	bs=$((bs))
	local part_cnt=$(get_fdisk_output "$img_file" "$img_file" | grep -v Disk | wc -l)

	# By now; all fdisk data should match; dump partitions to temp files and SHA256 check them
	for part_idx in $(seq 1 $part_cnt) ; do
		dd_partition_to_file "$img_file" "$part_idx" "$tmp1" "$bs"
		dd_partition_to_file "$sdcard_dev" "$part_idx" "$tmp2" "$bs"

		local sha1=$(sha256sum $tmp1 | cut -d' ' -f1)
		local sha2=$(sha256sum $tmp2 | cut -d' ' -f1)

		sudo rm -f $tmp1
		sudo rm -f $tmp2

		[ -n "$sha1" ] || {
			echo_red "Got empty SHA256 value for '$img_file' part '$part_idx'"
			exit 1
		}

		[ -n "$sha2" ] || {
			echo_red "Got empty SHA256 value for '$sdcard_dev' part '$part_idx'"
			echo_red "Partitions for '$sdcard_dev' not found"
			exit 1
		}

		if [ "$sha1" != "$sha2" ] ; then
			echo_red "Partition checksums mismatch:"
			echo_red "  '$img_file' part '$part_idx': '$sha1'"
			echo_red "  '$sdcard_dev' part '$part_idx': '$sha2'"
			one_part_is_bad=1
			echo
		else
			echo_green "Partitions '$part_idx' match"
		fi
	done

	# if at least one partition mismatches, exit here with 1
	[ "$one_part_is_bad" != "1" ] || exit 1
}

mount_and_compare_partition_files() {
	local img_file="$1"
	local sdcard_dev="$2"
	local part_idx
	local part_cnt
	local one_part_is_bad=0

	local tmp1=$(mktemp -d)
	local tmp2=$(mktemp -d)

	local bs=$(get_fdisk_output "$img_file" "Units" | grep Units | cut -d= -f2 | cut -db -f1)
	# convert to a more numerical representation
	bs=$((bs))

	local part_cnt=$(get_fdisk_output "$img_file" "$img_file" | grep -v Disk | wc -l)

	for part_idx in $(seq 1 $part_cnt) ; do
		mount_partition_to_dir "$img_file" "$part_idx" "$tmp1" "$bs"
		mount_partition_to_dir "$sdcard_dev" "$part_idx" "$tmp2" "$bs"

		if sudo diff -rq "$tmp1" "$tmp2" ; then
			echo_green "Partition '$part_idx' contents are identical"
		else
			echo_red "Partition '$part_idx' contents differ"
			one_part_is_bad=1
		fi
		sudo umount "$tmp1"
		sudo umount "$tmp2"
	done

	sudo rmdir -f $tmp1
	sudo rmdir -f $tmp2

	# if at least one partition mismatches, exit here with 1
	[ "$one_part_is_bad" != "1" ] || exit 1
}

echo
compare_fdisk_output_disk_units "$img_file" "$sdcard_dev"
echo
compare_fdisk_output_parititions "$img_file" "$sdcard_dev"
# FIXME: see about keeping/using/tuning `mount_and_compare_partition_files`
#        As it is now, it works only if the files are not system-files
#        or special symlinks/sockets; and doesn't work that well on EXT4
#        partitions
#echo 
#mount_and_compare_partition_files "$img_file" "$sdcard_dev"
echo
compare_partition_checksums "$img_file" "$sdcard_dev"
