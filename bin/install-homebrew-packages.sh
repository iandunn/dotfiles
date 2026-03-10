#!/bin/bash

source ~/dotfiles/bash/functions.sh

section "Installing Homebrew packages"

packages=(
  bat
  bash # oh-my-posh requires bash 4+
  composer
  colordiff
  coreutils
  fd
  font-caskaydia-cove-nerd-font # for iTerm and VS Code terminal (with oh-my-posh)
  font-fira-code-nerd-font # VS Code editor (not currently working, so remove this if don't end up using it)
  fswatch
  fzf # needed for zoxide
  ImageOptim
  jandedobbeleer/oh-my-posh/oh-my-posh
  git-delta
  git-svn
  gh
  glab
  jq
  lnav
  micro

  # Avast will flag, see https://github.com/ngrok/homebrew-ngrok/issues/21.
  # To install it:
  # 	* Oopen Avast and go to Core Shields and turn off File Shield
  #		* Run the install
  # 	* Turn File Shield back on.
  # Then open ngrok. Avast will block it, but allow you to add it to the exceptions.
  # To use it, run `ngrok http --host-header=foo.test 80`
  ngrok

  # can also use this as an alternative to ngrok that might not be flagged by avast
  # works like this:
  # cloudflared tunnel --url https://www.williams.test --http-host-header www.williams.test
  cloudflared

  nvm
  qmk/qmk/qmk
  ripgrep
  svn
  telnet
  wget
  wp-cli-completion
  zoxide
)

for package in "${packages[@]}"; do
  brew install "$package"
done

printf "\nYou will need to run 'install-wpcli-packages.sh' inside a WP installation (and maybe a LocalWP shell) in order to get 'wp shell' to use psysh.\n"

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

printf "\n\n✅ Done"
