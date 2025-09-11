export DISABLE_AUTO_TITLE="true"
export SITE_PATH="/Users/iandunn/local-sites/misc/app/public/"
echo -n -e "\033]0;misc Shell\007"

export MYSQL_HOME="/Users/iandunn/Library/Application Support/Local/run/adAGViECs/conf/mysql"
export PHPRC="/Users/iandunn/Library/Application Support/Local/run/adAGViECs/conf/php"
export WP_CLI_CONFIG_PATH="/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/config.yaml"
export WP_CLI_DISABLE_AUTO_CHECK_UPDATE=1

# Add PHP, MySQL, and WP-CLI to $PATH
echo "Setting Local environment variables..."
source "$(dirname "$0")/common.sh"

export PATH="/Users/iandunn/Library/Application Support/Local/lightning-services/mysql-8.0.35+4/bin/darwin$PROCESSOR_DIRECTORY_SUFFIX/bin:$PATH"
export PATH="/Users/iandunn/Library/Application Support/Local/lightning-services/php-8.2.29+0/bin/darwin$PROCESSOR_DIRECTORY_SUFFIX/bin:$PATH"
export PATH="/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/posix:$PATH"
export PATH="/Applications/Local.app/Contents/Resources/extraResources/bin/composer/posix:$PATH"

export MAGICK_CODER_MODULE_PATH="/Users/iandunn/Library/Application Support/Local/lightning-services/php-8.2.29+0/bin/darwin$PROCESSOR_DIRECTORY_SUFFIX/ImageMagick/modules-Q16/coders"

echo "----"
echo "WP-CLI:   $(wp --version)"
echo "Composer: $(composer --version | cut -f3-4 -d" ")"
echo "PHP:      $(php -r "echo PHP_VERSION;")"
echo "MySQL:    $(mysql --version)"
echo "----"

# Ian's customizations
cd $SITE_PATH
export LOCALWP_SHELL="Misc"
export LOCALWP_PHP_PATH="$(dirname "$(which php)")"


# Stops the spawned shell from inheriting NODE_ENV=production from Electron in
# production builds of Local. Users expect NODE_ENV to be unset by default. This
# does not prevent them from overriding NODE_ENV in their own shell config.
unset NODE_ENV

echo "Launching shell: $SHELL ..."
exec $SHELL
