#!/bin/bash

#
# Homebrew
#

# install/update homebrew itself

# brew update casks or whatever, so that doesn't do that as part of first brew install command. want output to be cleaner so can easily see errors etc

brew install hub

# is there a command that'll update if already installed?

# probably - general: node, ruby
# probably - valetish approach: nginx, dnsmasq, mysql || mariadb, php70
# maybe: dos2unix
# maybe - still needed? (remove dupes from above) dnsmasq		gettext		jpeg		libyaml		nginx		openssl@1.1	pkg-config	unixodbc dos2unix	hub		libpng		makedepend	node		pcre		readline	xz freetype	icu4c		libxml2		mariadb		openssl		php70		ruby		yarn


#
# What else can install/update from script?
#