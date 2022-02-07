#!/bin/bash

DEBUG=1

DIR_ROOT='/opt/DPS/files'

while IFS=, read -r org first last email name pass eta; do
	if [[ "$pass" != "Password" ]]; then
		org=${org// /$'_'}
		if [[ ! -d "$DIR_ROOT/$org" ]]; then
			if [[ "$DEBUG" -eq 0 ]]; then
				echo "Creating $DIR_ROOT/$org"
				mkdir -p "$DIR_ROOT/$org"
				chown www-data:www-data "$DIR_ROOT/$org"
				echo "Require group $org" >"$DIR_ROOT/$org/.htaccess"
				echo "${org}: $name" >>/opt/DPS/.htgroups
			else
				echo "Would create $DIR_ROOT/$org"
			fi
			if [[ $(
				grep -q $name /opt/DPS/.htpasswd
				echo $?
			) ]]; then
				if [[ "$DEBUG" -eq 0 ]]; then
					htpasswd -b /opt/DPS/.htpasswd $name $pass
				else
					echo "Would add user to .htpasswd: $name $pass"
				fi
			fi
			echo ''
		fi
	fi
done <Vault-Logins.csv
