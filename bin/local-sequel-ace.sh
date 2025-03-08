#!/bin/bash

# Enable Sequel Ace to connect to a LocalWP database
# https://community.localwp.com/t/how-can-i-connect-to-mysql-using-tcp-ip-rather-than-a-socket-on-macos-linux/21220

printf "\nThis must be ran inside a LocalWP shell for the site that you want Sequel Ace to connect to.\n"
printf "Are you in one? (y/N) "

read choice

if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
  printf "\nAborting. Please open the shell first, and then run this again.\n\n"
  exit 1
fi


$(mysql -e "CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY 'root'; GRANT ALL ON *.* TO 'root'@'127.0.0.1';")


# Get the TCP/IP port that MySQL is currently running on.
# You can also just run: jq < ~/Library/Application Support/Local/sites.json
port=$(mysql -e "SHOW VARIABLES WHERE Variable_name = 'port';" | awk '/port/ {print $NF}')


cat << SETTINGS

Now you can setup this connection in Sequel Ace:

Type: TCP/IP
Host: 127.0.0.1
Username: root
Password: root
Database: local
Port: $port

SETTINGS
