#!/bin/bash

#
# Install dotfiles after they've been cloned.
#
# Some things, like SSH, phpcs, and phpmd aren't installed, because they're only used on a few machines.
#

printf "WARNING: This will overwrite files like ~/.bashrc and ~/.bash_profile. \nHave you diff'd them against the ~/dotfiles version and integrated any changes? (y/N) "
read choice

if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
  echo "Aborting."
  exit 1
fi

if [ -d $HOME/dotfiles ]; then
	printf "\nInstalling from $HOME/dotfiles\n"
	DOTFILES_DIR=$HOME/dotfiles
else
	printf "\nEnter directory where dotfiles have been cloned: "
	read DOTFILES_DIR

	# Replace `~` with $HOME, because symlinks need absolute paths.
	DOTFILES_DIR=${DOTFILES_DIR//\~/$HOME}

	if [ ! -d $DOTFILES_DIR ]; then
		printf "\nError: \`$DOTFILES_DIR\` does not exist. Aborting.\n\n"
		exit
	fi
fi

# Overwrite existing files, because the defaults are unlikely to be useful or important.
ln -sf $DOTFILES_DIR/.bashrc		$HOME/.bashrc
ln -sf $DOTFILES_DIR/.bash_profile	$HOME/.bash_profile
ln -sf $DOTFILES_DIR/.bash_prompt	$HOME/.bash_prompt
ln -sf $DOTFILES_DIR/.bash_aliases	$HOME/.bash_aliases
ln -sf $DOTFILES_DIR/.gitconfig		$HOME/.gitconfig
ln -sf $DOTFILES_DIR/.gitignore_global	$HOME/.gitignore_global
ln -sf $DOTFILES_DIR/.inputrc		$HOME/.inputrc
ln -sf $DOTFILES_DIR/.config/micro	$HOME/.config/micro/

ln -sf ~/dotfiles/iterm2/com.googlecode.iterm2.plist ~/Library/Preferences/com.googlecode.iterm2.plist

# These have to be hard links, because Subversion and SSH configs don't support symlinks.
mkdir $HOME/.ssh
mkdir $HOME/.subversion
ln -f $DOTFILES_DIR/.ssh/config			$HOME/.ssh/config
ln -f $DOTFILES_DIR/.subversion/config	$HOME/.subversion/config
ln -f $DOTFILES_DIR/.subversion/servers	$HOME/.subversion/servers

cat << COW

  ----------------------------------------
/         Installation complete            \\
\\                                          /
  ----------------------------------------
         \\   ^__^ 
          \\  (oo)\_______
             (__)\       )\\/\\
                 ||----w |
                 ||     ||

COW
