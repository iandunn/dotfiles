#!/bin/bash

source ~/dotfiles/bash/functions.sh

section "Installing WPCLI packages"

wp package install git@github.com:schlessera/wp-cli-psysh.git
wp package install iandunn/wp-cli-plugin-active-on-sites
wp package install runcommand/find-unused-themes
wp package install 10up/snapshots

printf "\n\n✅ Done"
