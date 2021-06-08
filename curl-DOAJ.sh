#!/bin/bash

# Name: curl-DOAJ.sh
#
# Arguments:
#
#   curl-DOAJ.sh $FILESPEC $COLLECTION $ORGANIZATION
#
#  FILESPEC:
#    Relative path to a file OR directory
#    (will iterate through a directory)
#
#  COLLECTION:
#    Collection_Name
#    Default: {}
#
#  ORGANIZATION:
#    Org_Name
#    Default: {}
#
# Blame: Phil Ehrens <phil@archive.org>
#
# NOTE: Set DISABLED to "0" to upload!
#

set -o noglob
LC_ALL=C

# Set DISABLED to something other than 0
# for diagnostic output with no service
# connection.
DISABLED=1

USER=sergeybubka:_greatest_pole_vaulter_ever_

EMPTY='{}'

UPLOADER=https://phil-dev.us.archive.org/vault/deposit/web

COOKIEJAR=${HOME}/.archiveOrg-curl-cookie-jar

RANDOM_FILENAME=Pictures/Mr.Peabody.png

FILE_OR_DIR=${1:-$RANDOM_FILENAME}

COLLECTION=${2:-$EMPTY}

ORGANIZATION=${3:-$EMPTY}

touch $COOKIEJAR
chmod 0600 $COOKIEJAR

fsize() {
    local size=0
    size=$(wc -c "$1")
    echo ${size% *}
}

if [ -d "$FILE_OR_DIR" ]
then
    FILES=$(find ${FILE_OR_DIR})
else
    FILES=$FILE_OR_DIR
fi

for filepath in $FILES
do
    if [[ -f "$filepath" ]] && [[ -s "$filepath" ]]
    then
         size_bytes=$(fsize $filepath)
         SHA_256_SUM=$(sha256sum $filepath)
         if [[ "$SHA_256_SUM" =~ ^[0-9a-fA-F]+ ]]; then
             SHA_256_SUM=${BASH_REMATCH[0]}
         fi

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
         curl_command="curl  --globoff --insecure --silent --show-error
                         --user    $USER
                         --proxy   socks5://localhost:1080
                         --form    client=DOAJ
                         --form    username=${USER%:*}
                         --form    size=$size_bytes
                         --form    directories=$EMPTY
                         --form    organization=$EMPTY
                         --form    collection=$EMPTY
                         --form    file_field=$EMPTY
                         --form    dir_field=@$filepath
                         --form    webkitRelativePath=$filepath
                         --form    sha256sum=$SHA_256_SUM
                         --cookie  $COOKIEJAR --cookie-jar $COOKIEJAR
                         --referer $UPLOADER $UPLOADER"
        
        if [[ "$DISABLED" -eq 0 ]]
        then
            err=$($curl_command)
            if [ $? -gt 0 ]; then
                echo "$filepath : Transfer FAILED!:\n$err"
            else
                echo "$filepath : $size_bytes Bytes sent." 
            fi
        else
            echo "$filepath $size_bytes Bytes. sha256sum: $SHA_256_SUM"
        fi

    else
        echo "*** Invalid file: $filepath"
    fi
done
