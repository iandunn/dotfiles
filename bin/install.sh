#!/bin/bash

#
# Install dotfiles after they've been cloned.
#
# Some things, like SSH, phpcs, and phpmd aren't installed, because they're only used on a few machines.
#


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
ln -sf $DOTFILES_DIR/.bash_aliases	$HOME/.bash_aliases
ln -sf $DOTFILES_DIR/.bash_prompt	$HOME/.bash_prompt
ln -sf $DOTFILES_DIR/.gitconfig		$HOME/.gitconfig
ln -sf $DOTFILES_DIR/.gitignore_global	$HOME/.gitignore_global
ln -sf $DOTFILES_DIR/.inputrc		$HOME/.inputrc
ln -sf $DOTFILES_DIR/.nanorc		$HOME/.nanorc

# These have to be hard links, because Subversion and SSH configs don't support symlinks.
ln -f $DOTFILES_DIR/.ssh/config		$HOME/.ssh/config
ln -f $DOTFILES_DIR/.subversion/config	$HOME/.subversion/config
ln -f $DOTFILES_DIR/.subversion/servers	$HOME/.subversion/servers



# Append to existing files, to avoid overwriting possibly useful/important system defaults.
if [ -f $HOME/.bashrc ]; then
	COMMAND="source $DOTFILES_DIR/.bashrc"

	if [ ! -L $HOME/.bashrc ] && ! grep -q "$COMMAND" "$HOME/.bashrc"; then
		printf "\nsource $DOTFILES_DIR/.bashrc\n" >> $HOME/.bashrc
	fi
else
	ln -s $DOTFILES_DIR/.bashrc $HOME/.bashrc
fi

# todo make this DRY w/ block above
if [ -f $HOME/.bash_profile ]; then
	COMMAND="source $DOTFILES_DIR/.bash_profile"

	if [ ! -L $HOME/.bash_profile ] && ! grep -q "$COMMAND" "$HOME/.bash_profile"; then
		printf "\n$COMMAND\n" >> $HOME/.bash_profile
	fi
else
        ln -s $DOTFILES_DIR/.bash_profile $HOME/.bash_profile
fi

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
