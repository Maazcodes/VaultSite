#!/bin/bash

helpme() {
    msg='
# Name: curl-DOAJ.sh
#
# Arguments:
#
#   curl-DOAJ.sh $ORGANIZTION_ID $COLLECTION_ID $PATHSPEC
#
#
#  ORGANIZATION_ID:
#    INTEGER
#    Default: {}
#
#  COLLECTION_ID:
#    INTEGER
#    Default: {}
#
#  PATHSPEC:
#    Relative path to a file OR directory
#    (will iterate through a directory)
#
#
# Blame: Phil Ehrens <phil@archive.org>
#
# NOTE: Set DISABLED to "0" to upload!
#
#'
echo "$msg"
exit
}

set -o noglob
LC_ALL=C

# Set DISABLED to something other than 0
# for diagnostic output with no service
# connection.
DISABLED=0

USER='doaj_uploader:Jasper2021!!'

EMPTY='{}'

#UPLOADER=https://phil-dev.us.archive.org/vault/deposit/web
UPLOADER=https://wbgrp-svc600.us.archive.org/vault/deposit/web

COOKIEJAR=${HOME}/.archiveOrg-curl-cookie-jar

ORGANIZATION_ID=${1:-$EMPTY}
COLLECTION_ID=${2:-$EMPTY}
PATHSPEC=${3:-$EMPTY}

[[ ${FILE_OR_DIR} == '{}' ]] && helpme
[[ ! ${ORGANIZATION_ID} =~ ^[0-9]+$ ]] && helpme
[[ ! ${COLLECTION_ID} =~ ^[0-9]+$ ]] && helpme

touch $COOKIEJAR
chmod 0600 $COOKIEJAR

#
# --proxy   socks5://localhost:1080
#

curl_command='curl  --globoff --insecure --silent --show-error
                --user    $USER
                --proxy   socks5://localhost:1080
                --form    client=DOAJ_CLI
                --form    username=${USER%:*}
                --form    size=$size_bytes
                --form    directories=$filepath
                --form    organization=$ORGANIZATION_ID
                --form    orgname=$EMPTY
                --form    collection=$COLLECTION_ID
                --form    collname=$COLLECTION
                --form    file_field=$EMPTY
                --form    dir_field=@$filepath
                --form    webkitRelativePath=$filepath
                --form    name=$filepath
                --form    sha256sum=$SHA_256_SUM
                --cookie  $COOKIEJAR --cookie-jar $COOKIEJAR
                --referer $UPLOADER $UPLOADER'


fsize() {
    local size=0
    size=$(wc -c "$1")
    echo ${size% *}
}

shasum() {
    local filepath="$1"
    local hash=
    hash=$(sha256sum $filepath)
    if [[ "$hash" =~ ^[0-9a-fA-F]+ ]]; then
       hash=${BASH_REMATCH[0]}
    fi
    echo -n "$hash"
}

IFS=$'\n'

if [ -d "$PATHSPEC" ]
then
    FILES=$(find ${PATHSPEC})
else
    FILES=$PATHSPEC
fi

for filepath in $FILES
do
    if [[ -f "$filepath" ]] && [[ -r "$filepath" ]]
    then
         size_bytes=$(fsize "$filepath")
         SHA_256_SUM=$(shasum "$filepath")

         #
         # In the Django views.py, the --form options are accessible as:
         #
         #    request.POST.get("sha256sum", "")
         #
         # The dir_field is actually a list that can be iterated:
         #
         #    files = request.FILES.getlist(dir_field)
         #        for f in files:
         #            ...
         #
         #    With attributes: f.name f.size
         #

        if [[ "$DISABLED" -eq 0 ]]
            then
                json=$(eval $curl_command)

                if [ $? -gt 0 ]; then
                    echo "$filepath : Transfer FAILED!:\n$err"
                else
                    #echo "$filepath : $size_bytes Bytes sent."
                    echo "$json"
                fi
        else
            echo "$filepath $size_bytes Bytes. sha256sum: $SHA_256_SUM"
        fi

    else
        echo "*** Invalid file: $(file $filepath)"
    fi
done
