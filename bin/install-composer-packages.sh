#!/usr/bin/env bash

source ~/dotfiles/bash/functions.sh

section "Installing Composer Packages"

packages=(
    squizlabs/php_codesniffer:^3
    10up/phpcs-composer:^3
    wp-coding-standards/wpcs:^3
    automattic/vipwpcs:^3
    phpcompatibility/phpcompatibility-wp:^2
    php-stubs/wp-cli-stubs:^2
    php-stubs/wordpress-stubs:^6
	psy/psysh:^0

	# This is the latest version compatible with WP 6.9
	phpunit/phpunit:^9
)

for package in "${packages[@]}"; do
	printf "\n"
    composer global require "$package"
done

printf "\n\n✅ Done"
