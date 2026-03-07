#!/usr/bin/env bash

section() {
    printf "\n\033[1;33;40m %s \033[0m\n" "$1"
}

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
	phpunit/phpunit:^9
)

for package in "${packages[@]}"; do
	printf "\n"
    composer global require "$package"
done

printf "\n\n✅ Done"
