#!/bin/bash
#
# Name: /root/rsync_vault.sh
#
# Requires:
#
#  A passphraseless ssh key on the TARGET(S) that begins thusly:
#
#    command="/usr/bin/rrsync /opt/vault-backups/something" ssh-rsa ...
#
# What the heck?:
#
#  Server backups usually demand preservation of file permissions.
#  It's pretty much a no-go without root, but it needs to be done
#  carefully.
#
#  A passphraseless ssh key with a forced command calling the rsync
#  provided utility rrsync can make it go safely.
#
# How?:
#
#  Run from cron as root. i.e.:
#
#    */5 * * * * /root/rsync_vault.sh 2>&1 >/dev/null &
#
# Blame: phil@archive.org
#

LC_ALL=C
set -o noglob

LOCKFILE="${HOME}/RSYNC_LOGS/rsync_vault.lock"
LOGFILE="${HOME}/RSYNC_LOGS/VAULT_RSYNC.log"

# If Lock File doesn't exist, create it and set trap on exit
 if { set -C; 2>/dev/null >${LOCKFILE}; }; then
         trap "rm -f ${LOCKFILE}" EXIT
 else
         tty -s && echo "Lock file exists… exiting"
         exit
 fi

SOURCE='/opt/DPS'
TARGETS='phil-dev:/phil-dev/'
TARGETS="$TARGETS ia601101:/ia601101_md3/"
RSYNC_OPTS='-avz --delay-updates --one-file-system'

DATE=$(date +%Y-%m-%d)

# make script nice
ionice -c 3 -p $$ 2>&1 >/dev/null
renice +12  -p $$ 2>&1 >/dev/null

for target in $TARGETS
do
    # timetamp in ms
    begin=$(date +%s%3N)
    /usr/bin/rsync $RSYNC_OPTS --log-file=${LOGFILE}.$DATE $SOURCE $target 2>&1 >>${LOGFILE}.$DATE
    end=$(date +%s%3N)

    echo -e "rsync to $target took $(($end - $begin))ms" >>${LOGFILE}.$DATE
done

tty -s && tail ${LOGFILE}.$DATE
