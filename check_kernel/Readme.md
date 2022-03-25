## check kernel

This is a small script which will go through a checked out mainline kernel, and the ADI wiki, and let you know which parts are missing from the wiki.

example:

```
rgetz@brain:~/github/linux-mainline$ ../wiki-scripts/check_kernel/check_parts.sh ./
rm: cannot remove 'linux_drivers_raw.txt': No such file or directory
old kernel capturing parts from kernel
...
ssm2602 on ADI web site (Not Recommended for New Designs), and on wiki 
ssm4567 on ADI web site (Production), and on wiki 
checked and validated 863 part
```

the output of the script is looked at, and manually reviewed.

Controls:
```
filetype="Kconfig"
#filetype="*.c"
```

looks at either only Kconfig, or all c files.

TODO:
when the ADI/Maxim sites are merged - the scripe will need to be tweaked.

