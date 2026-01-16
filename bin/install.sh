#!/bin/bash

#
# Install dotfiles after they've been cloned.
#
# Some things, like SSH, phpcs, and phpmd aren't installed, because they're only used on a few machines.
#

printf "\nWARNING: Have you run "bin/install-homebrew-packages" yet? If not, do that first so that directories are created. (y/N) "
read homebrew

if [[ "$homebrew" != "y" && "$homebrew" != "Y" ]]; then
  echo "Aborting."
  exit 1
fi

printf "\nWARNING: This will overwrite files like ~/.bashrc and ~/.bash_profile. \nHave you diff'd them against the ~/dotfiles version and integrated any changes? (y/N) "
read diffed

if [[ "$diffed" != "y" && "$diffed" != "Y" ]]; then
  echo "Aborting."
  exit 1
fi


if [ -d $HOME/dotfiles ]; then
	printf "\nInstalling from $HOME/dotfiles\n\n"
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
ln -sf $DOTFILES_DIR/bash/.bashrc		$HOME/.bashrc
ln -sf $DOTFILES_DIR/bash/.bash_profile	$HOME/.bash_profile
ln -sf $DOTFILES_DIR/bash/.bash_aliases	$HOME/.bash_aliases
ln -sf $DOTFILES_DIR/bash/.fdignore		$HOME/.fdignore
ln -sf $DOTFILES_DIR/bash/.fdignore		$HOME/.rgignore

ln -sf $DOTFILES_DIR/git/.gitconfig			$HOME/.gitconfig
ln -sf $DOTFILES_DIR/git/.gitignore_global	$HOME/.gitignore_global
ln -sf $DOTFILES_DIR/.config/gh				$HOME/.config/gh
	# todo ^ is installing to .config/gh/gh and keeps nesting

ln -sf $DOTFILES_DIR/.inputrc		$HOME/.inputrc
ln -sf $DOTFILES_DIR/.curlrc						$HOME/.curlrc
ln -sf $DOTFILES_DIR/.config/micro/bindings.json	$HOME/.config/micro/bindings.json
ln -sf $DOTFILES_DIR/.config/micro/settings.json	$HOME/.config/micro/settings.json

ln -sf $DOTFILES_DIR/localwp/ssh-entry "$HOME/Library/Application Support/Local/ssh-entry"
	# todo ^ is installing to localwp/ssh-entry/ssh-entry and keeps nesting

# iTerm2 has an option to load preferences from a file, but it isn't working.
# If can get it working then won't need this. Using this may cause issues since it's not standard.
#ln -sf ~/dotfiles/iterm2/com.googlecode.iterm2.plist ~/Library/Preferences/com.googlecode.iterm2.plist

# These have to be hard links, because Subversion and SSH configs don't support symlinks.
mkdir -p $HOME/.subversion
ln -f $DOTFILES_DIR/.subversion/config	$HOME/.subversion/config
ln -f $DOTFILES_DIR/.subversion/servers	$HOME/.subversion/servers

bash $DOTFILES_DIR/bin/generate-config-files.sh

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
