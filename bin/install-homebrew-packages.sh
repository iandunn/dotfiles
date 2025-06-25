#!/bin/bash

packages=(
  autojump
  composer
  coreutils
  fswatch
  ImageOptim
  gh
  glab	# Remove if haven't been using
  jq
  lnav
  micro
  nvm
  #php@8.2 # probably remove this b/c localwp installs its own php. when this is linked, it overrides the localwp php and throws errors about extensions not being found etc. have to run `brew unlink php` every time homebrew updates.
  phpunit
  psysh
  qmk/qmk/qmk
  svn
  telnet
  wget
  wp-cli-completion
)

for package in "${packages[@]}"; do
  brew install "$package"
done

printf "\nYou will need to run 'install-wpcli-packages.sh' inside a WP installation (and maybe a LocalWP shell) in order to get 'wp shell' to use psysh.\n"

printf "\nEdit $HOMEBREW_PREFIX/share/autojump/autojump.bash and comment out the line in j() that echos the directory.\n"

# telnet
# gunpg openssl
# svn
# colordiff
# fswatch
# git-svn
# gpatch 	# https://github.com/cweagans/composer-patches/issues/423#issuecomment-1301026697

# Don't need if only using Local
# mailhog
# mkcert nss
# mysql
# nginx
# php


#pecl install xdebug

#brew services start mailhog
#brew services start mysql
#brew services start php
#mkcert -install


# php-code-sniffer phpmd phpunit sass - installed via composer into local packages, not used globally?
#
