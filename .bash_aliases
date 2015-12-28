# Core utilities
alias ls='ls -a --color'
alias ll='ls -lh'
alias nano='nano -w'
alias df='df -h'
alias du='du -h'
alias grep='grep -i'
alias rm='rm -i'
alias tar='tar --exclude-vcs'
alias locate='locate -i'

# Miscellaneous
alias wp='wp --path=wordpress'
alias wpd='wp --path=.'
alias patch='patch --no-backup-if-mismatch'

# Host-specific aliases
case $(hostname) in
	"macenzie.local" )
		alias ls='ls -a -G'
		alias vhosts='cd /Users/ian/vhosts/'
		alias wpver='find /Users/ian/vhosts -name version.php -print0 |xargs -0 grep "wp_version =" -s'
		alias vvv='cd /Users/ian/vhosts/vvv-personal/www/'
		alias wme='cd /Users/ian/vhosts/vvv-wme/www/wordpress-meta-environment'
	;;

	"vvv" )
		alias vvv='cd /srv/www/'
		alias codeception='php /srv/tools/codecept.phar --config=.'
		alias makepot='php /srv/www/wp-develop.dev/tools/i18n/makepot.php'
	;;

	"iandunn.dev.wordpress.org" )
		alias deploy='deploy-dotorg.sh'
	;;

	"iandunn.dev.dfw.wordpress.com" )
		unalias wp
		unalias wpd
	;;
esac
