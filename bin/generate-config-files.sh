#!/bin/bash

# Some dotfiles include sensitive things, but not all apps allow including multiple files in a config.
# This works around that by generating the config file from multiple files. The public files are tracked
# in the repo, and the private files are not.

mkdir -p $HOME/.ssh
touch $HOME/.ssh/config
printf "# Don't edit this, it's generated from dotfiles\n\n" > $HOME/.ssh/config

printf "####\n#### config-private\n####\n\n" >> $HOME/.ssh/config
cat $HOME/dotfiles/.ssh/config-private >> $HOME/.ssh/config

printf "\n\n####\n#### config-public\n####\n\n" >> $HOME/.ssh/config
cat $HOME/dotfiles/.ssh/config-public >> $HOME/.ssh/config
