export DISABLE_AUTO_TITLE="true"
export SITE_PATH="/Users/iandunn/local-sites/10up/cdcr/app/public/wp-content"
echo -n -e "\033]0;cdcr Shell\007"

export MYSQL_HOME="/Users/iandunn/Library/Application Support/Local/run/vBmBenAQS/conf/mysql"
export PHPRC="/Users/iandunn/Library/Application Support/Local/run/vBmBenAQS/conf/php"
export WP_CLI_CONFIG_PATH="/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/config.yaml"
export WP_CLI_DISABLE_AUTO_CHECK_UPDATE=1

# Add PHP, MySQL, and WP-CLI to $PATH
echo "Setting Local environment variables..."
source "$(dirname "$0")/common.sh"

export PATH="/Users/iandunn/Library/Application Support/Local/lightning-services/mysql-8.0.35+4/bin/darwin$PROCESSOR_DIRECTORY_SUFFIX/bin:$PATH"
export PATH="/Users/iandunn/Library/Application Support/Local/lightning-services/php-8.3.23+0/bin/darwin$PROCESSOR_DIRECTORY_SUFFIX/bin:$PATH"
export PATH="/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/posix:$PATH"
export PATH="/Applications/Local.app/Contents/Resources/extraResources/bin/composer/posix:$PATH"
export PATH="$SITE_PATH/vendor/bin:$PATH"
## todo update ^ based on composer bath

export MAGICK_CODER_MODULE_PATH="/Users/iandunn/Library/Application Support/Local/lightning-services/php-8.3.23+0/bin/darwin$PROCESSOR_DIRECTORY_SUFFIX/ImageMagick/modules-Q16/coders"


echo "----"
echo "WP-CLI:   $(wp --version)"
echo "Composer: $(composer --version | cut -f3-4 -d" ")"
echo "PHP:      $(php -r "echo PHP_VERSION;")"
echo "MySQL:    $(mysql --version)"
echo "----"

# Ian's customizations
cd $SITE_PATH
export LOCALWP_SHELL="CDCR"
export LOCALWP_PHP_PATH="$(dirname "$(which php)")"

echo "Launching shell: $SHELL ..."
exec $SHELL
