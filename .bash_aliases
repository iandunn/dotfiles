## Core utilities
# ls --group-directories-first requires `coreutils` from Homebrew on OS X b/c native `ls` doesn't support sorting folders first
alias ls='ls --all --group-directories-first --color'
alias ll='ls -lh'
alias nano='nano -wc'
alias less='less -SN'
alias df='df -h'
alias du='du -h'
alias grep='grep -i'
alias rm='rm -i'
alias diff='diff -u'
alias which='which -a'
alias tar='tar --exclude-vcs'
	# todo --exclude-vcs doesn't work on osx
alias locate='locate -i'
# todo works but throws usage notice - alias tail='tail -n40'
alias watch='watch -d'
alias ..="cd .."
alias ...="cd .. && cd .."
alias ....="cd .. && cd .. && cd .."
alias .....="cd .. && cd .. && cd .. && cd .."

alias devdown="sudo nginx -s quit && brew services stop php@7.2 && brew services stop mailhog && brew services stop mysql && brew services list"
alias devup="sudo nginx && brew services start php@7.2 && brew services start mailhog && brew services start mysql && brew services list"
#todo move ^ to appropriate section below

## Miscellaneous
alias patch='patch --no-backup-if-mismatch'
alias trim-whitespace="sed -i '' -e's/[[:space:]]*$//'"
alias phpcbf='phpcbf -v'
alias phpcs='phpcs -a'
alias phpcs-changed-git='phpcs -a $(git diff master --name-only) $(git diff --cached --name-only)'
alias phpcs-changed-svn='phpcs -a $(svn stat | grep "\(M \|A \)" | grep -v "external item" | cut -c8-)'
# todo can combine ^^^ into just `phpcs-changed` ?
alias phpcs-changed-lines='DIFF_BASE=master DEV_LIB_ONLY=phpsyntax,phpcs /Users/iandunn/vhosts/tools/xwp-wp-dev-lib/pre-commit'

alias curl-time='curl -w "
DNS Lookup:    %{time_namelookup}
TCP connect:   %{time_connect}
TLS handshake: %{time_appconnect}
Pre-transfer:  %{time_pretransfer}
Redirection:   %{time_redirect}
First byte:    %{time_starttransfer}
Total:         %{time_total}
"'

alias dcomp='docker-compose'

#
# Version Control
#

# Git is a bit more forgiving than SVN, so running SVN first leads to fewer conflicts.
alias pullup='svn up && git pull'
	# todo if w.org sandbox, `svnup`

# todo works manually but not as alias
# todo also grep for begining of sentance, to avoid false matches
# alias svn-add-untracked="svn add $(svn status | grep [^?] | awk '{print $2}')"
# also do something like alias rm-svn-untracked="rm -f $(svn status | grep [^?] | awk '{print $2}')"

# todo works manually but not as alias
#alias svn-revert-clean="svn revert -R . && rm -rf $(svn status | grep ? | awk '{print $2}')"


# remove noise from externals
alias prune-svn-stat="grep -v 'X   ' |grep -v 'Performing status on ex' |grep -v -e '^$'"
# todo convert this to a single regex -- '^[^?X]' ?
alias svn-stat-pruned="svn stat |prune-svn-stat"
# todo: "alias svn-stat-deep" which will include externals in subdirectiories. probably needs to be a function rather than an alias

# todo setup https://stackoverflow.com/a/3885594/450127 so `svn ci` also prints the diff like git does

alias syncsvn='php /Users/iandunn/vhosts/localhost/wordcamp.test/public_html/bin/php/multiple-use/miscellaneous/sync-svn-with-git.php'

## Host-specific aliases
case $(hostname) in
	"willow" | "willow.local" | "flanders" | "flanders.local" )
		alias ls='gls --all --group-directories-first --color'
		alias vhosts='cd /Users/iandunn/vhosts/'
		alias wpver='find /Users/iandunn/vhosts -name version.php -print0 |xargs -0 grep "wp_version =" -s'
		alias vvv='cd /Users/iandunn/vhosts/virtual-machines/vvv-personal/www/'
		alias vvv-up='vvv && vagrant up && vagrant ssh'
		alias wcorg='vhosts && cd localhost/wordcamp.test/public_html/wp-content'
		alias pv='cd /Users/iandunn/vhosts/virtual-machines/primary-vagrant/user-data/sites'
		alias pv-up='pv && vagrant up && vagrant ssh'
		alias wme='cd /Users/iandunn/vhosts/virtual-machines/vvv-wme/www/wordpress-meta-environment'
		alias wme-up='wme && vagrant up && vagrant ssh'
		alias calypso='cd /Users/iandunn/vhosts/localhost/calypso.localhost'
		alias updatedb='sudo /usr/libexec/locate.updatedb'
		alias behat='/Users/iandunn/vhosts/tools/wp-cli/vendor/behat/behat/bin/behat'
		alias web-ext-run='web-ext run --firefox=/Applications/FirefoxDeveloperEdition.app/Contents/MacOS/firefox-bin --firefox-profile=dev-edition-default'

		# When unplug external webcam (like when traveling), then plug back in, it's not recognized until restart service
		alias fix-camera='sudo killall VDCAssistant'

		alias push-deploy='git push && deploy'
		alias pushdeploy='push-deploy'
	;;

	"vvv" )
		alias vvv='cd /srv/www/'
		alias codeception='php /srv/tools/codecept.phar --config=.'
		alias makepot='php /srv/www/wp-develop.dev/tools/i18n/makepot.php'
	;;

	"norah" )
		alias reset-resolution='xrandr  --output LVDS1  --mode 1366x768'
		alias suspend='dbus-send --system --print-reply --dest="org.freedesktop.login1" /org/freedesktop/login1 org.freedesktop.login1.Manager.Suspend boolean:true'
		alias pbcopy='xsel --clipboard --input'
		alias pbpaste='xsel --clipboard --output'
	;;

	"iandunn.dev.wordpress.org" | "iandunn.dev.ord.wordpress.org" )
		alias svnupall='svnup-all.sh'
		alias svnup-all='svnup-all.sh'
	;;
esac
