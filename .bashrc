# Aliases for core utils
alias ls='ls -a -G'
alias ll='ls -lh'
alias nano='nano -w'
alias df='df -h'
alias du='du -h'
alias grep='grep -i'
alias rm='rm -i'
alias tar='tar --exclude .git --exclude .svn'
alias locate='locate -i'


# Other aliases
alias wp='wp --path=wordpress'
alias patch='patch --no-backup-if-mismatch'

case $(hostname) in
	"macenzie.local" )
		alias vhosts='cd /Users/ian/vhosts/'
	    alias wpver='find /Users/ian/vhosts -name version.php -print0 |xargs -0 grep "wp_version =" -s'
		alias vvv='cd /Users/ian/vhosts/varying-vagrant-vagrants/www/'
	;;

	"veronica" )
		alias vvv='cd /srv/www/'
	;;
esac


# Environmental variables
export EDITOR="nano"
export SVN_EDITOR="nano"
