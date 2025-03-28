SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DOTFILES_DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DOTFILES_DIR/$SOURCE"
done
DOTFILES_DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

# Environmental variables
export EDITOR="micro"
export SVN_EDITOR="micro"
export BASH_SILENCE_DEPRECATION_WARNING=1

# Need to hardcode /usr/local/bin for `brew` on Intel, and `/opt/homebrew/bin` for Silicone
export PATH="$PATH:$HOME/bin:$DOTFILES_DIR/bin:\
/usr/local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:"

export HOMEBREW_PREFIX=$(brew --prefix) # Different on laptop and desktop because intel vs silicon
eval "$($HOMEBREW_PREFIX/bin/brew shellenv)"

# Fix git-svn, see https://github.com/Homebrew/homebrew-core/issues/52490#issuecomment-792604853
# will need to update when perl version changes
export PERL5LIB=$HOMEBREW_PREFIX/lib/perl5/site_perl/5.30.3/darwin-thread-multi-2level/

export HOMEBREW_NO_AUTO_UPDATE=1

#export WP_TESTS_DIR="$HOME/vhosts/localhost/wp-develop.test/public_html/tests/phpunit"
# export MH_OUTGOING_SMTP="/usr/local/etc/mailhog/outgoing-smtp.json"   this isn't working, not sure why

export NVM_DIR="$HOME/.nvm"
\. "$HOMEBREW_PREFIX/opt/nvm/nvm.sh"
\. "$HOMEBREW_PREFIX/opt/nvm/etc/bash_completion.d/nvm"


export GPG_TTY=$(tty)
export GITLEAKS_CONFIG=~/.config/gitleaks/gitleaks.toml

# For Two Factor plugin
export WORDPRESS_DB_NAME=wordpress_develop_tests
export WORDPRESS_DB_USER=wp_tests
export WORDPRESS_DB_PASSWORD=wp_tests


# Host-specific overrides
case $(hostname) in
	"durin" )
		# Need to periodically update this to match php-fpm's version
		export PATH=/usr/local/php70/bin:$PATH
	;;
esac

# Only tab-complete local branches.
# You can include remote branches by using `git checkout --guess`. That has to be the full command, it won't work in an alias.
export GIT_COMPLETION_CHECKOUT_NO_GUESS=1

source /Library/Developer/CommandLineTools/usr/share/git-core/git-completion.bash
source $HOMEBREW_PREFIX/etc/bash_completion.d/gh
source $HOMEBREW_PREFIX/etc/bash_completion.d/wp
complete -F _complete_ssh_hosts ssh

# make wp-cli completions work for the wpdev alias too
#complete -o nospace -F _wp_complete wpdev

source ~/.bash_aliases

if [[ 'iTerm.app' = $TERM_PROGRAM ]]; then
	source ~/.iterm2_shell_integration.bash
fi
source ~/.bash_prompt

source $HOMEBREW_PREFIX/etc/profile.d/autojump.sh


####
#### FUNCTIONS
####


# props https://github.com/tomjn/bashosx/blob/483f272af00be0cfee7a73f25210a0bbdfda7e1a/init.sh#L5
_complete_ssh_hosts ()
{
        COMPREPLY=()
        cur="${COMP_WORDS[COMP_CWORD]}"
        comp_ssh_hosts=`cat ~/.ssh/known_hosts | \
                        cut -f 1 -d ' ' | \
                        sed -e s/,.*//g | \
                        grep -v ^# | \
                        uniq | \
                        grep -v "\[" ;
                cat ~/.ssh/config | \
                        grep "^Host " | \
                        awk '{print $2}'
                `
        COMPREPLY=( $(compgen -W "${comp_ssh_hosts}" -- $cur))
        return 0
}

# find all files in the current folder and below, then grep each of them for the given string
# this could _almost_ be an alias, but then $QUERY would have to be at the end of the command, so you couldn't remove the binary files
function findgrep {
	local QUERY=$1
	local MATCHES=$(find . -type f ! -name "*.svn*" ! -name "*.git*" -follow |xargs grep --ignore-case --line-number --no-messages $QUERY)
	# ! -path '*/.svn/*' ! -path '*/.git/*' might be better ?
	local OUTPUT=$(printf '%s\n' "${MATCHES[@]}" | grep -v "Binary file")
	# also add build, vendor, etc folders to exclude?

	printf '%s\n' "${OUTPUT[@]}"
}

# especiallly helpful when git and svn checked out side by side, like w/ gutenberg plugin
function svn-rm-untracked {
	local FILES=$(svn status | egrep '^\?' | awk '{print $2}')

	 rm -rf ${FILES[@]}
}

# todo describe
function wordcamp-diff() {
	exit
	# not done yet

	local args=($@)
	local rest=(${args[@]:1:${#args[@]}})
	local WP_CONTENT="/Users/ian/vhosts/virtual-machines/vvv-personal/www/wordcamp.dev/public_html/wp-content"

	local GIT_DIRS=(
		"mu-plugins"
		"mu-plugins-private/wporg-mu-plugins"
		"plugins-meta"
		"themes-meta"
		"wp-super-cache-plugins"
	)

	local SVN_DIRS=(
		"plugins-external"
		"themes-external"
	)

	for i in "${GIT_DIRS[@]}"
	do :
		git -C $WP_CONTENT/$i stat
	done

	for i in "${SVN_DIRS[@]}"
	do :
		svn stat "$WP_CONTENT/$i" |prune-svn-stat
	done
}

# Bump svn:externals in the current directory
#
# $1 - The plugin/theme slug
# $2 - The version to bump to
# $3 - "local" if you want to only make the change locally, short-circuiting the diff/commit/deploy process.
#      This is useful when you want to update several externals in a row, then commit them all at once.
#
# Examples:
# svn-bump-ext akismet 3.2
# svn-bump-ext twentyfifteen 1.6 local
#
function svn-bump-ext {
	svn-bump-ext-update-property $1 $2

	if [[ 'local' == $3 ]]; then
		return
	fi

	printf "Fetching latest externals...\n\n"
	svn up
	printf "\nDone fetching, you can test the new externals now."

	svn-bump-ext-commit $1 $2
}

# svn-bump-ext helper for updating svn:externals
#
# $1 - The plugin/theme slug
# $2 - The version to bump to
function svn-bump-ext-update-property {
	# Use printf to avoid adding a trailing newline
	printf %s "$(svn propget svn:externals)" > externals.tmp

	local search="$1/(tags/)?(.*)/"
	local replace="$1/\1$2/"

	# The space is a valid delimiter, just like / or @, but improves readability
	eval "sed -i '' -E 's $search $replace ' externals.tmp"

	svn propset svn:externals -F externals.tmp .
	rm -f externals.tmp
}

# svn-bump-ext helper for diff / commit / deploy
#
# $1 - The plugin/theme slug
# $2 - The version to bump to
function svn-bump-ext-commit {
	printf "\nExternal differences:\n\n"
	svn diff --depth empty

	printf "\nCommit and deploy the changes? [y/n]: "
	read commit

	if [[ 'y' != $commit ]]; then
		printf "\nAborting, did not commit.\n"
		return
	fi

	message="Externals: Bump \`$1\` to \`$2\`"
	printf "\nCommit message: [$message]: "
	read new_message

	# Enter and "y" both mean that the user wants to accept the default message
	if [[ "" != $new_message && "y" != $new_message ]]; then
		message=$new_message
	fi

	eval "svn ci --depth empty -m '$message'"

	printf "\nDeploying...\n"
	eval "deploy"
}


# Alias to convert a stereo recording to mono
#
# See https://iandunn.name/2017/06/04/dropping-quicktime-recording-from-stereo-to-mono/
#
# $1 - The input filename
function qtmono {
	basename=$(basename "$1")
	filename="${basename%.*}"
	extension="${basename##*.}"

	ffmpeg -i $1 -codec:v copy -af pan="mono: c0=FL" $filename-mono.$extension
}

# todo git checkout HEAD @ date
# git checkout `git rev-list -n 1 --before="2017-01-16 17:00" master`
# probably better to make this a git alias instead of a bash alias

# Sync canonical Git repos with legacy/deploy SVN repos
function sync {
	current_folder=$(pwd)
	printf "\n"

	case "$current_folder" in
		*wordcamp.test* )
			php /Users/iandunn/vhosts/localhost/wordcamp.test/public_html/bin/php/multiple-use/miscellaneous/sync-svn-with-git.php
		;;

		*themes/wporg-news* )
			ssh wordpress.org '$SYNCPATH/news.sh'
		;;

		*wporg-mu-plugins* )
			echo "Sync script broken until https://github.com/WordPress/wporg-mu-plugins/pull/175 merged"
			#ssh wordpress.org '$SYNCPATH/wporg-mu-plugins.sh'
		;;

		*wporg-5ftf* )
			ssh wordpress.org '$SYNCPATH/5ftf.sh'
		;;

		* )
			printf "Couldn't detect repo to sync.\n"
		;;
	esac
}

# Deploy the site that corresponds to the current directory
# $1 For w.org, the role to deploy. Otherwise unused.
function deploy {
	current_folder=$(pwd)
	printf "\n"

	# w.org sandbox
	if [[ 'iandunn.dev.ord.wordpress.org' = $(hostname) ]]; then
		case "$current_folder" in
			*wordcamp* )
				echo "Updating everything"
				svnup $WORDCAMP_PATH

				if ! $WORDCAMP_PATH/bin/php/multiple-use/miscellaneous/wpcut; then
					printf "\n\nERROR: Aborting deploy. Make 'wpcut' pass and then retry.\n\n"
					return
				else
					echo "Command succeeded, continue"
				fi

				deploy-wordcamp.sh
			;;

			*wporg* )
				echo "Updating everything"
				svnup $WPORGPATH

				printf "\n"
				deploy-dotorg.sh $1
			;;

			*api* | *buddypress* | *planet* )
				deploy-dotorg.sh $1
			;;

			* )
				echo "Couldn't detect site to deploy."
			;;
		esac;

		return
	fi

	# local sandbox
	case "$current_folder" in
		*wordcamp.test* )
			ssh wordcamp.org 'deploy-wordcamp.sh'
		;;

		*themes/wporg-news* )
			ssh wordpress.org 'deploy-dotorg.sh'
		;;

		*wporg-mu-plugins* )
			ssh wordpress.org 'deploy-dotorg.sh'
		;;

		*i18n-tools* )
			ssh wordpress.org 'deploy-dotorg.sh'
		;;

		*wp15.wordpress.test* )
			ssh -t wp15.wordpress.net 'svn up ~/wp15.wordpress.net'
		;;

		*wordpressfoundation.test* )
			ssh -t wordpressfoundation.org 'svn up ~/public_html/'
		;;

		*iandunn.localhost* )
			bash /Users/iandunn/vhosts/localhost/iandunn.localhost/bin/deploy.sh
		;;

		*regolith.iandunn.localhost* )
			bash /Users/iandunn/vhosts/localhost/regolith.iandunn.localhost/bin/deploy.sh
		;;

		* )
			printf "Couldn't detect site to deploy.\n"
		;;
	esac
}

# Wrapper for phpmd to avoid having to specify report type and config file.
#
# $1 - The file/folder to analyize
function phpmd {
	env phpmd $1 text ~/vhosts/localhost/wordcamp.test/phpmd.xml.dist
}

# Run composer commands from subfolder without prompt
#
# When running `composer update`, etc, it obnoxiously complains that you're not in the root folder, and makes you
# confirm that you want to execute the commands based on the `composer.json` in the root. That only exists for
# back-compat due to a (IMO) poor design decision. See https://github.com/composer/composer/issues/6426.
#
# This function works around that inconvenience so that you're not prompted if you're in a known project.
function composer {
	current_folder=$(pwd)

	case "$current_folder" in
		*wordcamp.test* )
			env composer "$@" -d /Users/iandunn/vhosts/localhost/wordcamp.test/
		;;

		* )
			env composer "$@"
		;;
	esac
}

# run a request against all w.org web heads
# must be ran on sandbox, must use http
function check_all_wporg_web_heads {
	local query_string = $1

	for i in $(seq 1 5); do
		curl "http://web$i.ord.wordpress.org$query_string" -I -H 'Host: wordpress.org';
	 done
}
