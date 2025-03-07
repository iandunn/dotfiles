packages=(
  micro
  z  # Need to manually apply https://github.com/rupa/z/pull/323 or find a maintained version
  gh
  composer
  coreutils
  lnav
  wget
  nvm
  jq
  glab	# Remove if haven't been using
  psysh
)

for package in "${packages[@]}"; do
  brew install "$package"
done

printf "\nYou will need to run 'wp package install git@github.com:schlessera/wp-cli-psysh.git' inside a WP installation (and maybe a LocalWP shell) in order to get 'wp shell' to use psysh.\n"

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
