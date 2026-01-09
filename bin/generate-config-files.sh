#!/bin/bash

# Some dotfiles include sensitive things, but not all apps allow including multiple files in a config.
# This works around that by generating the config file from multiple files. The public files are tracked
# in the repo, and the private files are not. Instead, they should be backed securly up using Time Machine etc.

mkdir -p $HOME/.ssh
touch $HOME/.ssh/config
printf "# Don't edit this, it's generated from dotfiles\n\n" > $HOME/.ssh/config

printf "####\n#### config-personal\n####\n\n" >> $HOME/.ssh/config
/bin/cat $HOME/dotfiles/.ssh/config-personal >> $HOME/.ssh/config

printf "####\n#### config-10up\n####\n\n" >> $HOME/.ssh/config
/bin/cat $HOME/dotfiles/.ssh/config-10up >> $HOME/.ssh/config

printf "####\n#### config-cadmv\n####\n\n" >> $HOME/.ssh/config
/bin/cat $HOME/dotfiles/.ssh/config-cadmv >> $HOME/.ssh/config

# This should be last because it contains the `Host *` section
printf "\n\n####\n#### config-public\n####\n\n" >> $HOME/.ssh/config
/bin/cat $HOME/dotfiles/.ssh/config-public >> $HOME/.ssh/config
