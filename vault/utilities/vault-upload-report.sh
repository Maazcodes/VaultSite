#!/bin/bash

# Name: vault-upload-report.sh
#
# Cal with no arguments for a report on the uploads
# "So far this week".
#
#
# Blame: phil@archive.org
#

set -o noglob

WEEKDAY=$(date +%u)

N_DAYS=${1:-$WEEKDAY}

ORG=''
COLL=''

N_FILES=0

BYTES_TOTAL=0

# A famous function
join_by() {
    local d=${1-} f=${2-}
    if shift 2
    then
        printf %s "$f" "${@/#/$d}";
    fi
}

fsize() {
    local size=0
    size=$(wc -c "$1")
    echo ${size%% *}
}

human() {
    local bytes="$1"
    for M in B KB MB GB TB PB
    do
        [[ $bytes -lt 1024 ]] && break
        bytes=$(($bytes / 1024))
    done
    echo -n "$bytes$M"
}

total=0
nfiles=0
IFS=$'\n'
for upload in $(find /opt/DPS/files -daystart -mtime -$N_DAYS)
do
    [[ ! -f "$upload" ]] && continue
    IFS='/' read -r -a path <<< "$upload"

    org=${path[4]}
    coll=${path[5]}

    if [[ ! "$coll" == "$COLL" ]]
    then
        [[ ${#COLL} ]] && \
            echo "$ORG/$COLL Total last $N_DAYS days: $(human $total) ($total B) in $nfiles files" && echo ''
        total=0
        nfiles=0
        COLL="$coll"
        #echo "    $coll"
    fi

    if [[ ! "$org" == "$ORG" ]]
    then
        ORG="$org"
        total=0
        nfiles=0
        echo "*** $org ***"
    fi

    size=$(fsize "$upload")
    N_FILES=$(($N_FILES + 1))

    total=$(($total + $size))
    nfiles=$(($nfiles + 1))
    BYTES_TOTAL=$(($BYTES_TOTAL + $size))
    relative_path=$(join_by '/' ${path[@]:5})
    #echo "        $relative_path $(human $size)"
done

echo "$ORG/$COLL Total last $N_DAYS days: $(human $total) ($total B) in $nfiles files"
echo ''
echo "Note that the web upload page includes directories in the uploaded file count"
echo ''
echo "Total number of files uploaded in last $N_DAYS days: $N_FILES"
echo ''
echo "Total size of files uploaded in last $N_DAYS days: $(human $BYTES_TOTAL) ($BYTES_TOTAL B)"
