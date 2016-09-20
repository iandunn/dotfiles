## Core utilities
alias ls='ls -a --color'
alias ll='ls -lh'
alias nano='nano -wc'
alias less='less -SN'
alias df='df -h'
alias du='du -h'
alias grep='grep -i'
alias rm='rm -i'
alias tar='tar --exclude-vcs'
	# todo --exclude-vcs doesn't work on osx
alias locate='locate -i'
# todo works but throws usage notice - alias tail='tail -n40'
alias ..="cd .."
alias ...="cd .. && cd .."
alias ....="cd .. && cd .. && cd .."


## Miscellaneous
alias patch='patch --no-backup-if-mismatch'
alias trim-whitespace="sed -i '' -e's/[[:space:]]*$//'"

alias curl-time='curl -w "
DNS Lookup:    %{time_namelookup}
TCP connect:   %{time_connect}
TLS handshake: %{time_appconnect}
Pre-transfer:  %{time_pretransfer}
Redirection:   %{time_redirect}
First byte:    %{time_starttransfer}
Total:         %{time_total}
"'

# todo works manually but not as alias
# todo also grep for begining of sentance, to avoid false matches
# alias svn-add-untracked="svn add $(svn status | grep ? | awk '{print $2}')"

# todo works manually but not as alias
#alias svn-revert-clean="svn revert -R . && rm -rf $(svn status | grep ? | awk '{print $2}')"


# remove noise from externals
alias prune-svn-stat="grep -v 'X   ' |grep -v 'Performing status on ex' |grep -v -e '^$'"
# todo convert this to a single regex
alias svn-stat-pruned="svn stat |prune-svn-stat"


## Host-specific aliases
case $(hostname) in
	"macenzie" | "macenzie.local" )
		alias ls='ls -a -G'
		alias vhosts='cd /Users/ian/vhosts/'
		alias wpver='find /Users/ian/vhosts -name version.php -print0 |xargs -0 grep "wp_version =" -s'
		alias vvv='cd /Users/ian/vhosts/vvv-personal/www/'
		alias wme='cd /Users/ian/vhosts/vvv-wme/www/wordpress-meta-environment'

		# On its own, this will ask for a password for private repositories, and the password characters will be
		# shown on the screen instead of being masked. To avoid that, setup something like this wrapper on the
		# server:
		#
		# https://gist.github.com/iandunn/0d33e0abc769dd3a8c4814a80a686dd9#
		alias deploy="ssh wordcamp.org 'deploy '"

		alias git-svn-rebase='git stash && git svn rebase && git stash pop'
		alias git-svn-push='git stash && git svn dcommit --interactive && git stash pop'
	;;

	"vvv" )
		alias vvv='cd /srv/www/'
		alias codeception='php /srv/tools/codecept.phar --config=.'
		alias makepot='php /srv/www/wp-develop.dev/tools/i18n/makepot.php'
		alias phpcs='phpcs -a'
	;;

	# iandunn.name cluster
	"iandunn.name" | "n2"* )
		alias wp='~/bin/wp'
	;;

	"iandunn.dev.wordpress.org" )
		alias deploy='deploy-dotorg.sh'
	;;
esac
