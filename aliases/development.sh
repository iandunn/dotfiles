
# LocalWP shells
alias shdmv='sh  "$HOME/dotfiles/localwp/ssh-entry/O1BOJvLsA.sh"'
alias shfhl='sh  "$HOME/dotfiles/localwp/ssh-entry/HOgy-WCkG.sh"'
alias shcore='sh "$HOME/dotfiles/localwp/ssh-entry/eAU6ubHdw.sh"'

# npm / yarn
alias nr='npm run'
alias startminstack="npm start -- --color | grep --color=always -v '^    at .*/node_modules/'" # npm start w/ minimal stack trace, https://stackoverflow.com/a/35505086/450127
alias cleanbuild='npm ci && npm run build'
alias nr='npm run'
alias yr='yarn run'
alias ywr='yarn workspaces run'

# composer
alias cr='composer run'
alias ce='composer exec'
alias cr='composer run'

# patches
alias patch='patch --no-backup-if-mismatch'
alias trim-whitespace="sed -i '' -e's/[[:space:]]*$//'"

# php linting
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


###
### wp-cli / wordpress
###
alias wpef='wp eval-file'
alias wppat='wp --url=https://wordpress.org/patterns'
alias wpupall='wp core update && wp plugin update --all && wp theme update --all && wp core language update'
alias wpdev='/Users/iandunn/vhosts/tools/wp-cli/bin/wp'
alias skipinstall='WP_TESTS_SKIP_INSTALL=1'
alias wpver='find /Users/iandunn/vhosts -name version.php -print0 |xargs -0 grep "wp_version =" -s'
alias behat='/Users/iandunn/vhosts/tools/wp-cli/vendor/behat/behat/bin/behat'


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


# homebrew
alias devdown="brew services stop  nginx && brew services stop  php@8.0 && brew services stop  mailhog && brew services stop  mysql && brew services list"
alias devup="  brew services start nginx && brew services start php@8.0 && brew services start mailhog && brew services start mysql && brew services list"


###
### misc
###
alias devnote='cp ~/dotfiles/docs/development-process-and-tips.md '

# tweak the -n option, but this is really more here just to remind yourself that `nice` is available to throttle commands that hog a lot of resources
alias slurp='nice -n 19 ~/vhosts/tools/wordpress-plugin-directory-slurper/update'

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

#alias rmlock=''
	# parse files out of `git stat` of `git clean --dry-run`, rm if composer-lock or package-lock
		# not git clean b/c that's only untracked files

# works, but why doesn't it autocomplete?
alias ImageOptim='/Applications/ImageOptim.app/Contents/MacOS/ImageOptim'

alias web-ext-run='web-ext run --firefox=/Applications/FirefoxDeveloperEdition.app/Contents/MacOS/firefox-bin --firefox-profile=dev-edition-default'
