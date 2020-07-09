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
alias locate='locate -i'
# todo works but throws usage notice - alias tail='tail -n40'
alias watch='watch -d'
alias ..="cd .."
alias ...="cd .. && cd .."
alias ....="cd .. && cd .. && cd .."
alias .....="cd .. && cd .. && cd .. && cd .."

# z doesn't always add folders for some reason, but this lets you manually do it easily when you encounter one that should exist and doesn't
alias zadd='z --add $(pwd)'

alias devdown="sudo nginx -s quit && brew services stop php@7.2 && brew services stop mailhog && brew services stop mysql && brew services list"
alias devup="sudo nginx && brew services start php@7.2 && brew services start mailhog && brew services start mysql && brew services list"
#todo move ^ to appropriate section below

## Miscellaneous
alias patch='patch --no-backup-if-mismatch'
alias trim-whitespace="sed -i '' -e's/[[:space:]]*$//'"
alias phpcbf='phpcbf -v'
alias phpcs='phpcs -a'
alias phpcs-git-files='phpcs -a $(git diff production --name-only) $(git diff --cached --name-only)'
	# todo ^ should use default branch, not hardcode "master". doesn't work w/ "production" , "develop" etc
	# none from https://stackoverflow.com/questions/28666357/git-how-to-get-default-branch work in 5ftF repo, maybe have to track remote or something
#alias phpcs-git-lines='DIFF_BASE=production DEV_LIB_ONLY=phpsyntax,phpcs ~/vhosts/tools/xwp-wp-dev-lib/pre-commit'
	# todo ^ also needs to get default branch instead of hardcoding
alias phpcs-svn-files='phpcs -a $(svn stat | grep "\(M \|A \)" | grep -v "external item" | cut -c8-)'
# todo can combine ^^^ into just `phpcs-changed` ?
alias phpcs-changed-lines='DIFF_BASE=production DEV_LIB_ONLY=phpsyntax,phpcs /Users/iandunn/vhosts/tools/xwp-wp-dev-lib/pre-commit'
	# todo also shouldn't hardcode branch ^

# tweak the -n option, but this is really more here just to remind yourself that `nice` is available to throttle commands that hog a lot of resources
alias slurp='nice -n 19 ~/vhosts/tools/wordpress-plugin-directory-slurper/update'

# todo move these below w/ version control. clean up this file in general
# cleans up externals within the pwd too
alias svn-cleanup-deep="find . -name '.svn' | sed 's/.svn//' | xargs -I% svn cleanup %"
# todo move ^ into vcs section below
#same for others above it

alias cleanbuild='npm ci && npm run build'

alias curl='curl --location'

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

# It crashed more than it should, and when it does, it can't be re-opened until this file is deleted.
alias gorramit_firefox='rm -f ~/Library/Application Support/Firefox/Profiles/**/.parentlock'

# To allow `svn up` without certificate errors
# can't leave this running after svn up, though, b/c messes up .test cert verification in browser
# look into that, doesn't make sense.
alias forward-wporg-svn='sudo ssh -ND 8081 -p22 -L 443:dotorg.svn.wordpress.org:443 iandunn@proxy.automattic.com &'
	# sometimes ^ doesn't work, just shows "stopped" right away? is it because of sudo combined with & ?

#
# Version Control
#

# Git is a bit more forgiving than SVN, so running SVN first leads to fewer conflicts.
alias pullup='svn up && git pull'
	# todo if w.org sandbox, `svnup`
	# add a `git checkout .` before git pull? that would avoid `cant pull with rebase, you have unstaged changes` errors. but might also discard uncommitted changes that i want to keep
	# could maybe do git pull --autostash instead

# todo works manually but not as alias
	# maybe something like this, but need to remove the `rm` stuff: svn st $DIR |awk '/^!/ { print "svn rm -q "$2; } /^[?]/ { print "svn add -q "$2; }' | sh
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
	# alias tar='tar --exclude-vcs'
		# todo add ^ to all non-OSX hosts

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
