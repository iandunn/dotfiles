# Core utilities
alias ls='ls -a --color'
alias ll='ls -lh'
alias nano='nano -w'
alias less='less -S'
alias df='df -h'
alias du='du -h'
alias grep='grep -i'
alias rm='rm -i'
alias tar='tar --exclude-vcs'
alias locate='locate -i'
# todo works but throws usage notice - alias tail='tail -n40'

# Miscellaneous
alias patch='patch --no-backup-if-mismatch'

# todo works manually but not as alias
# todo also grep for begining of sentance, to avoid false matches
# alias svn-add-untracked="svn add $(svn status | grep ? | awk '{print $2}')"

# todo works manually but not as alias
#alias svn-revert-clean="svn revert -R . && rm -rf $(svn status | grep ? | awk '{print $2}')"


# remove noise from externals
# todo convert this to a single regex
alias svn-stat-pruned="svn stat |grep -v 'X   ' |grep -v 'Performing status on ex' |grep -v -e '^$'"

# Host-specific aliases
case $(hostname) in
	"macenzie" | "macenzie.local" )
		alias ls='ls -a -G'
		alias vhosts='cd /Users/ian/vhosts/'
		alias wpver='find /Users/ian/vhosts -name version.php -print0 |xargs -0 grep "wp_version =" -s'
		alias vvv='cd /Users/ian/vhosts/vvv-personal/www/'
		alias wme='cd /Users/ian/vhosts/vvv-wme/www/wordpress-meta-environment'
		alias deploy-wordcamp="ssh wordcamp.org 'svn up '"
	;;

	"vvv" )
		alias vvv='cd /srv/www/'
		alias codeception='php /srv/tools/codecept.phar --config=.'
		alias makepot='php /srv/www/wp-develop.dev/tools/i18n/makepot.php'
	;;

	# iandunn.name cluster
	"n2"* )
		alias wp='~/bin/wp'
	;;

	"iandunn.dev.wordpress.org" )
		alias deploy='deploy-dotorg.sh'
	;;
esac
