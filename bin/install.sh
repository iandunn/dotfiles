#!/bin/bash

#
# Install dotfiles after they've been cloned.
#
# Some things, like SSH, phpcs, and phpmd aren't installed, because they're only used on a few machines.
#

printf "\nDirectory where dotfiles have been cloned: "
read DOTFILES_DIR

# Replace `~` with $HOME, because symlinks need abolute paths
DOTFILES_DIR=${DOTFILES_DIR//\~/$HOME}

if [ ! -d $DOTFILES_DIR ]; then
	printf "\nError: \`$DOTFILES_DIR\` does not exist. Aborting.\n\n"
	exit
fi

# Overwrite existing files, because the defaults are unlikely to be useful or important
ln -sf $DOTFILES_DIR/.bash_aliases	$HOME/.bash_aliases
ln -sf $DOTFILES_DIR/.bash_prompt	$HOME/.bash_prompt
ln -sf $DOTFILES_DIR/.gitconfig		$HOME/.gitconfig
ln -sf $DOTFILES_DIR/.gitignore_global	$HOME/.gitignore_global
ln -sf $DOTFILES_DIR/.inputrc		$HOME/.inputrc
ln -sf $DOTFILES_DIR/.nanorc		$HOME/.nanorc

# Subversion and SSH configs can't be symlinked :(
cp $DOTFILES_DIR/.subversion/config	$HOME/.subversion/config



# Append to existing files, to avoid overwriting possibly useful/important system defaults
if [ -f $HOME/.bashrc ]; then
	if [ ! -L $HOME/.bashrc ]; then
		if [ ! -L $HOME/.bashrc && ! grep "$DOTFILES_DIR/.bash_profile" $HOME/.bashrc ]; then
			printf "\nsource $DOTFILES_DIR/.bashrc\n" >> $HOME/.bashrc
		fi
	fi
else
	ln -s $DOTFILES_DIR/.bashrc $HOME/.bashrc
fi

# todo make this DRY w/ block above
if [ -f $HOME/.bash_profile ]; then
	if [ ! -L $HOME/.bash_profile && ! grep "$DOTFILES_DIR/.bash_profile" $HOME/.bash_profile ]; then
        	printf "\nsource $DOTFILES_DIR/.bash_profile\n" >> $HOME/.bash_profile
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
