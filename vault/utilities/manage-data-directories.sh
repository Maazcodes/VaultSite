#!/bin/bash
#
# Name: manage-data-directories.sh
#
# Description:
#
# Create directory structures for Data Preservation Service
# data staging. Staged data further disposition TBD.
#
# Blame: Phil Ehrens <phil@archive.org>
#

LC_ALL=C

ROOTDIR=/opt/DPS/BACKING_STORE

HEX_DIGITS=(0 1 2 3 4 5 6 7 8 9 A B C D E F)

_log_() {
    local logfile="$ROOTDIR/${0}.log"
    local ts=$(date +%F-%T)
   echo "$ts ($0) - $*" >>$logfile
}

dirsizekb () {
    # Returns 4.0K for anything 0-4Kb
    echo $(du -sh "$1" |grep -oP -m 1 '^[0-9\.]+[A-Z]')
}

fcount () {
    local count=$(ls -1 "$1" |wc -l)
    echo "$count"
}

_mkdir_ () {
    local dir="$1"
    if [ ! -d $dir ]
    then
        _log_ "Creating: $dir"
        mkdir --mode=700 -p $dir
    fi
}

subdivide () {
    local dir=
    local fulldir="$1"
    local newdir=
    _log_ "Subdividing: $fulldir"
    # ~16^4x10^3 (67,000,000) files after one generation.
    for dir in $(ls -d ${ROOTDIR}/[0-9A-F][0-9A-F])
    do
        # The pattern strips everything up to and including the final '/'
        newdir=$fulldir/${fulldir##*/}${dir##*/}
        _mkdir_ $newdir
        mv -u $fulldir/${fulldir##*/}${dir##*/}[0-9A-F]* $newdir 2>&1 >/dev/null
    done
}

_mkdir_ $ROOTDIR

_log_ ":FIXME: - This script only handles one generation of subdirectories"
for i in ${HEX_DIGITS[@]}
do
	for j in ${HEX_DIGITS[@]}
	do
        _mkdir_ $ROOTDIR/$i$j
        count=$(fcount $ROOTDIR/$i$j)
        if [ "$count" -ge 1024 ]
        then
            subdivide $ROOTDIR/$i$j
        fi
	done
done

