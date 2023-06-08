# todo write script to re-install these on new systems

# hub
# z
	# need to manually apply https://github.com/rupa/z/pull/323
	# or maybe switch to one that's maintained
# mailhog
# mkcert nss
# composer
# mysql
# telnet
# nginx
# php
# coreutils
# lnav
# wget nvm
# gunpg openssl
# svn
# colordiff
# micro
# fswatch
# jq
# git-svn
# gpatch 	# https://github.com/cweagans/composer-patches/issues/423#issuecomment-1301026697

#pecl install xdebug

brew services start mailhog
brew services start mysql
brew services start php
mkcert -install

# also want https://github.com/bobthecow/psysh/wiki/Installation, which doesn't have an brew package

# don't need anymore?
# httpd and/or httpd24
# php-code-sniffer phpmd phpunit sass - installed via composer into local packages, not used globally?
#
