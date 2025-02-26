# todo clean up this, maybe split into separate files and source them all here.
# eg aliases/core-utils.sh, aliases/version-control.sh, etc

## Core utilities
# ls --group-directories-first requires `coreutils` from Homebrew on OS X b/c native `ls` doesn't support sorting folders first
alias ls='ls --all --group-directories-first --color'
alias ll='ls -lh --time-style="+%b %e %Y %l:%M:%S %P"'	# always show the year, and use 12-hour time
alias less='less -SR'
alias lessn='less -N'
alias df='df -h'
alias du='du -h'
alias grep='grep -i'
alias rm='rm -i'
alias diff='diff -u'
alias diffsplit='/usr/bin/diff -y -W 250' # full path b/c -y conflicts w/ -u alias
alias stat='stat -x'
alias which='which -a'
alias locate='locate -i'
alias zip='zip -r'

# todo works but throws usage notice - alias tail='tail -n40'
alias watch='watch -d'
alias ..="cd .."
alias ...="cd .. && cd .."
alias ....="cd .. && cd .. && cd .."
alias .....="cd .. && cd .. && cd .. && cd .."

# Usage: watch curl -iks https://misc.wordcamp.test/2016/tmp/ |grep WordCampBlocks
# Note this will watch the current working directory.
alias watch='fswatch -o $(pwd) |xargs -n1 -I{} $1'

alias date='gdate'

# This assumes you're in the directory you want to search
alias findgrep='find . -type f ! -path '*/.svn/*' ! -path '*/.git/*' -follow |xargs grep --ignore-case --line-number --no-messages'
# also add build, vendor, etc folders to exclude?
# maybe need something like b/c exclude above doesn't work
# function grep() {
#	/bin/grep --exclude-dir=.svn "$@"
#}
#also exclude binary files


# z doesn't always add folders for some reason, but this lets you manually do it easily when you encounter one that should exist and doesn't
alias zadd='z --add $(pwd)'

alias devdown="brew services stop  nginx && brew services stop  php@8.0 && brew services stop  mailhog && brew services stop  mysql && brew services list"
alias devup="  brew services start nginx && brew services start php@8.0 && brew services start mailhog && brew services start mysql && brew services list"
alias brew-intel="/usr/local/bin/brew"
#todo move ^ to appropriate section below

alias nr='npm run'
alias startminstack="npm start -- --color | grep --color=always -v '^    at .*/node_modules/'" # npm start w/ minimal stack trace, https://stackoverflow.com/a/35505086/450127
alias cr='composer run'
alias ce='composer exec'
alias yr='yarn run'
alias ywr='yarn workspaces run'

alias mic='micro'
alias nano='echo "remember to use micro instead"'
alias mical='micro ~/.bash_aliases'
alias soal='source ~/.bash_aliases'

## Miscellaneous
alias patch='patch --no-backup-if-mismatch'
alias trim-whitespace="sed -i '' -e's/[[:space:]]*$//'"
alias phpcbf='phpcbf -v'
alias phpcs='phpcs -a'
alias phpcs-git-files='phpcs -a $(git diff production --name-only) $(git diff --cached --name-only)'
	# todo ^ should use default branch, not hardcode "master". doesn't work w/ "production" , "develop" etc
	# `git remote show origin | grep 'HEAD branch' | cut -d' ' -f5` works. have to hardcode "origin" but works in most cases.
	# none from https://stackoverflow.com/questions/28666357/git-how-to-get-default-branch work in 5ftF repo, maybe have to track remote or something
#alias phpcs-git-lines='DIFF_BASE=production DEV_LIB_ONLY=phpsyntax,phpcs ~/vhosts/tools/xwp-wp-dev-lib/pre-commit'
	# todo ^ also needs to get default branch instead of hardcoding
alias phpcs-svn-files='phpcs -a $(svn stat | grep "\(M \|A \)" | grep -v "external item" | cut -c8-)'
# todo can combine ^^^ into just `phpcs-changed` ?
alias phpcs-changed-lines='DIFF_BASE=production DEV_LIB_ONLY=phpsyntax,phpcs /Users/iandunn/vhosts/tools/xwp-wp-dev-lib/pre-commit'
	# todo also shouldn't hardcode branch ^
alias wpef='wp eval-file'
alias wppat='wp --url=https://wordpress.org/patterns'
alias wpupall='wp core update && wp plugin update --all && wp theme update --all && wp core language update'
alias devnote='cp ~/dotfiles/docs/development-process-and-tips.md '
alias wpdev='/Users/iandunn/vhosts/tools/wp-cli/bin/wp'

# tweak the -n option, but this is really more here just to remind yourself that `nice` is available to throttle commands that hog a lot of resources
alias slurp='nice -n 19 ~/vhosts/tools/wordpress-plugin-directory-slurper/update'

# todo move these below w/ version control. clean up this file in general
# cleans up externals within the pwd too
# can just do `svn cleanup --include-externals` instead?
alias svn-cleanup-deep="find . -name '.svn' | sed 's/.svn//' | xargs -I% svn cleanup %"
# todo move ^ into vcs section below
#same for others above it

alias cleanbuild='npm ci && npm run build'
alias nr='npm run'
alias cr='composer run'

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

# have to specify which firefox, see https://github.com/mozilla/web-ext/issues/628
# Don't add `--keep-profile-changes` because that causes security problems
# Might need to add --watch-file manually in some cases, see https://github.com/mozilla/web-ext/issues/1626
alias webxr='web-ext run --firefox=firefoxdeveloperedition --firefox-profile="Ian Dunn"'

# To allow `svn up` without certificate errors
# nginx has to be off
# can't leave this running after svn up, though, b/c messes up .test cert verification in browser
alias proxy-svn-on='sudo nginx -s stop     && sudo ssh -fN iandunn@proxy.automattic.com -L 443:dotorg.svn.wordpress.org:443'
alias proxy-svn-off='sudo pkill -f "ssh -fN iandunn@proxy.automattic.com -L 443:dotorg.svn.wordpress.org:443"       && sudo nginx'
# todo add & so see output
# todo might need to specify ident file if add more


alias skipinstall='WP_TESTS_SKIP_INSTALL=1'

#
# Version Control
#

# Git is a bit more forgiving than SVN, so running SVN first leads to fewer conflicts.
alias pullup='svn up && git pull'
	# todo if w.org sandbox, `svnup`
	# add a `git checkout .` before git pull? that would avoid `cant pull with rebase, you have unstaged changes` errors. but might also discard uncommitted changes that i want to keep
	# could maybe do git pull --autostash instead

# todo works manually but not as alias
# probably need to escape $2 to be \$2 and other stuff
# but probably easier to make it a function like svn-rm-untracked is
	# maybe something like this, but need to remove the `rm` stuff: svn st $DIR |awk '/^!/ { print "svn rm -q "$2; } /^[?]/ { print "svn add -q "$2; }' | sh
# todo also grep for begining of sentance, to avoid false matches
# alias svn-add-untracked="svn add $(svn status | grep [^?] | awk '{print $2}')"

alias svn-revert-clean="svn-revertr && svn-rm-untracked"

alias qmklf='qmk lint && qmk flash'

# remove noise from externals
# the full wording here is verbose, but remember that bash does tab completion on aliases too
alias svn-stat-pruned='clear && echo -e "" && svn status | grep ^[?!MAD]'
alias svn-stat-pruned-tracked='svn status | grep ^[MAD]'
# todo: "alias svn-stat-deep" which will include externals in subdirectories. probably needs to be a function rather than an alias

alias svn-showhead='svn up --ignore-externals && svn diff -rPREV |less'

# todo setup https://stackoverflow.com/a/3885594/450127 so `svn ci` also prints the diff like git does

alias svn-externals='svn propedit svn:externals .'
alias svn-ignore='svn propedit svn:ignore .'

alias svn-diffw='svn diff -x --ignore-all-space'
# naming not consistent w/ `git diffw` alias?

alias svn-revertr='svn revert -R'
#rename this and others to not have the - in it? breaks typing flow
alias svnrevr='svn revert -R'

#alias rmlock=''
	# parse files out of `git stat` of `git clean --dry-run`, rm if composer-lock or package-lock
		# not git clean b/c that's only untracked files

# works, but why doesn't it autocomplete?
alias ImageOptim='/Applications/ImageOptim.app/Contents/MacOS/ImageOptim'

## Host-specific aliases
case $(hostname) in
	# alias tar='tar --exclude-vcs'
		# todo add ^ to all non-OSX hosts

	"willow" | "willow.local" | "willow.lan" | "MacBook-Pro.lan" | "milo" | "milo.local" )
		alias ls='gls --almost-all --group-directories-first --color'
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

		alias date='gdate "+%b %e %Y %l:%M:%S %P"' # use GNU date instead of BSD date for consistency across machines
		alias timeutc='gdate --utc --date="@$1"'
		alias timelocal='gdate --date='@''

		# use xdebug with wp-cli commands
		# from https://gist.github.com/joshlevinson/93253aec2b41749e10de
		# start listening for connections in phpstorm, set breakpoints, then use this alias to call the wp-cli command
		#
		# if this ever stops working, first try restarting phpstorm and firefox b/c it seems like that that's all that's needed sometimes
		# if that doesn't fix it, then make sure that xdebug.ini settings match. might need to add more of them here explicitly rather than relying on defaults
		# also try putting xdebug_break(); in code, then run and sometimes there's errors in the phpstorm console that you wouldn't otherwise see
		# also check ip address in /opt/homebrew/etc/php/7.2/conf.d/ext-xdebug.ini, make sure matches current ip
		#
		# ugh, it DID stop working, 10 minutes later, even though nothing changed.
		# have to use manual xdebug_breaks everywhere.
		# seems to recognize files in wordcamp/.../mu (core), but not in wordcamp/.../bin
		# it just gets "/3" as the filename instead of teh path to the file
		#   oh, i wonder if this is only with `wp eval-file` commands? `var_dump()` doesn't know the line know in that case either:
		#   phar:///usr/opt/homebrew/wp/vendor/wp-cli/eval-command/src/EvalFile_Command.php(76) : eval()'d code:169: bool(true)
		#   that's still a problem, but less of one, and is maybe a hint at a solution
		#
		# todo phpstorm will open the `wp` binary for some reason, and you'll have to hit the `play/run to...` button to go to the next pointpoint
		#   maybe some way to fix that?
		alias wpdebug='XDEBUG_CONFIG="idekey=iandunn remote_connect_back=1" wp'

		# this has all the same problems as wpdebug
		# plus is breaks the flow, and phpunit doesn't run the tests until after xdebug is finished, or something?
		#
		# a not-so-great workaround is to manually execute the function-under-test with the data for a failing case
		#   wpdebug eval "var_dump( WordCamp\Sunrise\get_post_slug_url_without_duplicate_dates(  true, '/%postname%/', 'vancouver.wordcamp.test', '/2020/', '/2020/2019/save-the-date-for-wordcamp-vancouver-2020/' ) );"
		alias phpunitdebug='XDEBUG_CONFIG="idekey=iandunn remote_connect_back=1" phpunit'

		alias skipinst='WP_TESTS_SKIP_INSTALL=1 phpunit '


		# When unplug external webcam (like when traveling), then plug back in, it's not recognized until restart service
		alias fix-camera='sudo killall VDCAssistant'

		alias push-deploy='git push && deploy'
		alias pushdeploy='push-deploy'

		# cd to Git repo and `pr 510` to checkout the branch for that PR
		alias prc='git fetch && gh pr checkout'
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

		# problem: xdebug idekey is different from what local env uses
		# probably can't change config file, but maybe could setup an alias like `XDEBUG_CONFIG="idekey=iandunn remote_connect_back=1" php` or something, similar to how get it working locally w/ wp-cli and phpunit
	;;
esac
