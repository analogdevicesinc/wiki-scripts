#!/bin/sh
set -e

RED='\033[0;31m'
GREEN="\033[0;32m"        # Green
YELLOW="\033[0;33m"       # Yellow
BLUE="\033[0;34m"         # Blue
PURPLE="\033[0;35m"       # Purple
NC='\033[0m' # No Color

filetype="Kconfig"
#filetype="*.c"
parts=".all_parts.$(echo ${filetype} | sed 's/\*//g').tmp"
adi=".adi.tmp"
kernel=".kernel"_$(echo ${filetype} | sed 's/\*//g')
missing=".missing"_$(echo ${filetype} | sed 's/\*//g')
rm -rf ${missing}
touch ${missing}

touch ${parts}
touch ${adi}
touch ${kernel}

indent=""

# will return prefix[0-9]* as well as ad193x, ad1848/cs4248, adau17x1, ad2s1200
seek_all() {
prefix=$1
#'s:[() _\."=,]:\n:g'
for file in $(find ./ -name ${filetype}) ; do
	for part in $(grep -i ${prefix}[0-9][a-z0-9] ${file} | \
			tr '[:upper:]' '[:lower:]' | \
			sed -e "s:-${prefix}: ${prefix}:g" \
			    -e 's:[]{}\*~\[&()\t _\."=,>:;?]:\n:g' \
			    -e "s:/${prefix}:\n${prefix}:g" \
		       	    -e 's:-spi::g' -e 's:-i2c::g' -e 's:-keys::g' -e 's:-hw::g' -e 's:-[[:space:]]*$::' | \
			grep -i ^${prefix}[0-9][a-z0-9] | sort -u)
	do
		# untangle things like: ad9833/4/7/8 ad5933/4 ad5360/61/62/63/70/71/73
		# these are harder :  ad5624/44/64r ad1848/cs4248
		echo $part |\
			awk -F/ '{
					print $1; \
				  	if (NF >= 2 ) { \
						len="99"; \
						for (i = 2; i <= NF; i++) {if (length($i) <= len) len=length($i)} ; \
						for (i = 2; i <= NF; i++) {print substr($1, 1, length($1) - len)$i} \
					} \
				  }' | \
			 grep -i ^${prefix}

		for p in $(echo $part |\
			awk -F/ '{
					print $1; \
					if (NF >= 2 ) { \
						len="99"; \
						for (i = 2; i <= NF; i++) {if (length($i) <= len) len=length($i)} ; \
						for (i = 2; i <= NF; i++) {print substr($1, 1, length($1) - len)$i} \
					} \
				}' | \
			grep -i ^${prefix})
		do
			in=$(grep -P "^${p}\t" ${kernel} | awk -F'\t' '{print $2}')
			if [ "$(echo ${in} | wc -c)" -lt "2" ] ; then
				echo "$p\t$file" >> ${kernel}
			fi
		done
	done
done
}

sold2on=".sold_to_on_semi"
wget -o /dev/null -O ${sold2on} https://www.analog.com/en/products/landing-pages/001/parts-list-sold-to-on-semiconductor.html

on_adi()
{
	part=${1}
	if [ "$(grep -P "^${part}\t"  ${adi} | wc -l)" -gt "0" ] ; then
		err=$(grep -P "^${part}\t" ${adi} | awk -F'\t' '{print $2}')
		echo ${err}
		return
	fi
	if [ "$(grep -i -P "${part}" ${sold2on} | wc -l)" -gt "0" ] ; then
		echo 999
		echo "${part}\t999" >> ${adi}
		return
	fi
	for agent in "\"\"" "\"Safari\"" "\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36\""
	do
		er=0
		while [ ${er} -lt "5" ]
		do
			sleep 1
			# do not quit on error
			# T(imeout) = 15 seconds
			# (re)t(ry) = 4 times
			# try maximintegrated.com/ & www.analog.com/
			for site in www.analog.com www.maximintegrated.com
			do
				set +e
				#set -x
				eval "wget -T 15 -t 2 --no-check-certificate --user-agent=${agent} -o ${tmpfl}._code -O ${tmpfl}._html https://${site}/${part}"
				#set -x; echo code1 ; cat ${tmpfl}"._code"
				set -e
				if [ "$(grep "Unable to establish SSL connection" "._code" | wc -l)" -gt "0" ] ; then
					# SSL error, trying again
					er==$((er+1))
					continue
				fi
				if [ "$(grep "HTTP request sent.*\.\.\.[[:space:]]200" ${tmpfl}"._code" | wc -l)" -gt "0" ] ; then
					break
				fi
				if [ "$(grep "HTTP request sent,.*200 OK$" ${tmpfl}"._code" | wc -l)" -gt "0" ] ; then
					break
				fi
				sleep 1
				set +e
				#set -x
				eval "wget -T 15 -t 2 --no-check-certificate --user-agent=${agent} -o ${tmpfl}._code -O ${tmpfl}._html ${site}/${part}"
				#set +x; echo code2:; cat ${tmpfl}"._code"
				set -e
				if [ "$(grep "Unable to establish SSL connection" "${tmpfl}._code" | wc -l)" -gt "0" ] ; then
					# SSL error, trying again
					er==$((er+1))
					continue
				fi
			done
			break
		done
		if [ "$(grep "HTTP request sent.*\.\.\.[[:space:]]200" ${tmpfl}"._code" | wc -l)" -gt "0" ] ; then
			break
		fi
		if [ "$(grep "HTTP request sent,.*200 OK$" ${tmpfl}"._code" | wc -l)" -gt "0" ] ; then
			break
		fi
	done
	if [ "$(grep "search.html" ._code | wc -c)" -gt "5" ] ; then
		return=404
	elif [ "$(grep "www.maximintegrated.com/en/search/parts.mvp" ._code | wc -c)" -gt "5" ] ; then
		return=998
	elif [ "$(grep "www.maximintegrated.com/en/404.html" ._code | wc -c)" -gt "5" ] ; then
		return=404
	elif [ "$(grep "parts-list-sold-to" ._code | wc -c)" -gt "5" ] ; then
		return=999
	else
		return=$(grep "HTTP request sent" ._code | tail -n 1 | sed 's/ /\n/g' | grep [0-9][0-9][0-9])
	fi

	echo $return
	if [ "${return}" -eq "200" ] ; then
		lifecycle=$(grep product-life-cycle-information ._html | \
				head -n 1  | \
				sed -e 's:href="[a-zA-Z:/\.-]*"::' -e 's/<span><a >//g' -e 's|</a></span>||g' -e 's/^[[:space:]]*//' -e 's/<a[[:space:]]*class="//' -e 's/[[:space:]]*$//g' -e 's/">$//g')
		if [ -z "${lifecycle}" ] ; then
			lifecycle=$(grep activeProd_section ._html | head -n 1 | sed 's/<div/\n<div/g' | grep -A 1 activeProd_section | tail -n 1 | sed 's/>/>\n/g' | head -n 1 | sed -e 's/^<div class="//' -e 's/">//')
		fi
		echo "${part}\t${return}\t${lifecycle}" >> ${adi}
	else
		echo "${part}\t${return}" >> ${adi}
	fi
}

which_file() {
	tmp=0
	in=$(grep -P "^${1}\t" ${kernel} | awk -F'\t' '{print $2}')
	if [ "$(echo ${in} | wc -c)" -gt "2" ] ; then
		for i in ${in}
		do
			if [ "${tmp}" -ne "0" ] ; then
				echo "\t${indent}${i}"
			else
				tmp=1
				echo "${i}"
			fi
		done
		return
	fi

	tmp=0
	for i in $(find ./ -name ${filetype}) ; do
		if [ "$(grep -i ${1} $i -l | wc -c)" -gt "2" ] ; then
			if [ "${tmp}" -ne "0" ] ; then
				echo "\t${indent}${i}"
			else
				tmp=1
				echo "${i}"
			fi
			echo "${1}\t${i}" >> ${kernel}
		fi
	done
	if [ "${tmp}" -eq "0" ] ; then
		echo "${1}\tnowhere" >> ${kernel}
	fi
}

wiki_check() {
	web_status=$(grep -P "^$1\t" ${adi} | awk -F'\t' '{print $3}')
	where=$(which_file $1 | sed 's/ /\n\t/g')
	if [ $(grep -i -c "$1[$: ]" ${index}) -eq 0 ] ; then
		if [ "${where}" = "nowhere" ] ; then
			echo "${indent}$1 ${RED}missing from wiki${NC} (${web_status}), ${YELLOW}but not found${NC}"
		else
			echo -n "${indent}$1 ${RED}missing from wiki${NC} (${web_status}), mentioned in:"
			echo ${where}
			if [ $(grep -i -c "^$1 " ${missing}) -eq 0 ] ; then
				echo -n "$1 missing from wiki (${web_status}), mentioned in:" >> ${missing}
				echo ${where} >> ${missing}
			fi
		fi

		wiki=$(grep -i ${1} ${index} | sed -e 's:[() _\."=,]:\n:g' | tr '[:upper:]' '[:lower:]' | grep -i ${1} | sort -u)
		if [ $(echo $wiki | wc -c) -gt 1 ] ; then
			echo "${indent}\ton wiki : $wiki"
		fi
	else
		if [ "${web_status}" = "obsolete" ] ; then
			set +e
			wiki_status=$(grep -i ${1} ${index} | sed -e 's:[() _\."=,]:\n:g' | tr '[:upper:]' '[:lower:]' | grep -i ${1} | grep -i obsolete)
			set -e
			if [ "$(echo ${wiki_status} | wc -c)" -gt "2" ] ; then
				echo "${indent}$1 on ADI web site (${web_status}), and on wiki ${wiki_status}"
			else
				echo -n "${indent}$1 on ADI web site (${web_status}), ${RED}missing obsolete on wiki${NC} mentioned in:"
				echo ${where}
				if [ $(grep -i -c "^$1 " ${missing}) -eq 0 ] ; then
					echo -n "$1 missing from wiki (${web_status}), mentioned in:" >> ${missing}
					echo ${where} >> ${missing}
				fi
			fi
		else
			echo "${indent}$1 on ADI web site (${web_status}), and on wiki "
		fi
		good=$(expr ${good} + 1)
	fi
}

# grab all the part prefixes from the wiki, [a-z][a-z][0-9] and [0-9][0-9][0-9]
part_prefixes() {
	wiki_parts | sed -e 's:[0-9].*$::' | \
	       	sort -u
}

all_parts() {
	echo $(for pref in $(part_prefixes) ; do
		seek_all ${pref}
	done) |  sed -e 's: :\n:g' | sort -u | grep -v "'"
}

wiki_parts() {
	echo $(grep "\[\[adi" ${index} | \
			sed -e 's:\[\[adi:\n\[\[adi:g' | \
			set -e 's:\[\[maxim:\n\[\[maxim:g' | \
			grep "\[\[adi\|\[\[maxim" | \
			tr '[:upper:]' '[:lower:]' | \
			sed -e 's:|[[:space:]]*obsolete::' -e 's:^\[\[adi>::' -e 's:\]\][[:space:]]*$::' \
			; \
		sed -e 's:\]\]:\n:g' ${index} | \
			grep "\[\[" | \
			grep -v "\[\[adi" | \
			grep -v "\[\[maxim" | \
			sed -e 's:^.*|::' -e 's:[() _\."=,\:]:\n:g' | \
			tr '[:upper:]' '[:lower:]' | \
			grep [a-z][a-z][0-9][0-9a-z] \
		) | sed -e 's: :\n:g' | grep -v jesd | grep -v sc70 | sort -u
}

index=linux_drivers_raw.txt
set +e
rm ${index}
set -e
if [ ! -f ${index} ] ; then
	wget -O ${index} -o /dev/null https://wiki.analog.com/resources/tools-software/linux-drivers-all?do=export_raw
fi

#wiki_parts
#part_prefixes
#seek_all ad | sort -u

if [ ! -f "${parts}" ] ; then
	echo capuring al parts from kernel
	git rev-parse HEAD > ${parts}
	all_parts >> ${parts}
	echo done
	echo ${parts}
else
	if [ "$(git rev-parse HEAD)" != "$(head -n 1 ${parts})" ] ; then
		echo old kernel capturing parts from kernel
		git rev-parse HEAD > ${parts}
		all_parts >> ${parts}
		echo done
	else
		echo using old list ${parts}
	fi
fi

good=0;

for part in $(sed '1d' ${parts}) ; do
	code=$(on_adi $part)
	case $code in
		200)
			wiki_check $part
			;;
		500)
			echo "\t$part most likely OK"
			wiki_check $part
			;;
		503)
			# Service Unavailable
			echo $part wrong part number
			;;
		404)
			echo -n $part missing from ADI web site, referenced from:
			which_file $part
			# handle part numbers like : adt746x adf4360-x
			if [ "$(echo -n $part | tail -c 1)" = "x" ] ; then
				indent="\t"
				echo "${indent}unwind1 $part"
				for i in $(seq 0 9) ; do
					code=$(on_adi $(echo "${part%?}"$i))
					if [ $code -eq 200 ] ; then
						wiki_check $(echo "${part%?}"$i)
					elif [ $code -eq 500 ] ; then
						wiki_check $(echo "${part%?}"$i)
					else
						echo "${indent}${part%?}"$i  " " $code
					fi
				done
				indent=""
			# handle part numbers like : adt7x10
			elif [ "$(echo -n $part | grep -c -e [0-9]x[0-9])" -eq "1" ] ; then
				indent="\t"
				echo "${indent}unwind2 $part"
				for part2 in $(echo $part | awk -Fx '{for (i = 0; i <= 9; i++) {print $1 i $2}}') ; do
					code=$(on_adi ${part2})
					if [ $code -eq 200 ] ; then
						wiki_check ${part2}
					elif [ $code -eq 500 ] ; then
						wiki_check ${part2}
					else
						echo "${indent}${part2} ${code}"
					fi
				done
				indent=""
			# drop suffixes off parts like "-1", or "r"
			else
				part2=$(echo $part | sed -e 's:[a-zA-Z]*$::' -e 's:-[0-9]*$::')
				if [ "$part" != "$part2" ] ; then
					echo "\tchecking derivative $part2"
					indent="\t\t"
					code=$(on_adi $part2)
					if [ $code -eq 200 ] ; then
						wiki_check $part2
					elif [ $code -eq 500 ] ; then
						wiki_check $part2
					else
						echo "\t\t$part2 also not on adi web site $code"
					fi
					indent=""
				fi
			fi
			;;
		998)	echo $part in kernel, ${GREEN}but likely needs suffix${NC}
			if [ $(grep -i -c "^${part} " ${missing}) -eq 0 ] ; then
				echo -n $part in kernel, but likely needs a suffix, mentioned in >> ${missing}
				where=$(which_file $part | sed 's/ /\n\t/g')
				if [ "${where}" != "nowhere" ] ; then
					echo ${where} >> ${missing}
				else
					echo >> ${missing}
				fi
			fi
			indent="\t"
			wiki_check $part
			indent=""
			;;
		999)
			echo $part in kernel, but sold
			;;
		*)
			echo do not know $part returned code was :\"${code}\"
			exit
			;;
	esac
done

echo checked and validated $good part
