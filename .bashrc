SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DOTFILES_DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DOTFILES_DIR/$SOURCE"
done
DOTFILES_DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

# Environmental variables
export EDITOR="nano"
export SVN_EDITOR="nano -w"

# todo maybe use \nano or /usr/bin/nano to avoid the -w and force line wrapping during git/svn commits

# Host-specific environmental variables
case $(hostname) in
	"macenzie" | "macenzie.local" | "flanders" | "flanders.local" )
		export PATH="$HOME/bin:$PATH"
		export WP_TESTS_DIR="$HOME/vhosts/localhost/wp-develop.dev/public_html/tests/phpunit"
		# export MH_OUTGOING_SMTP="/usr/local/etc/mailhog/outgoing-smtp.json"   this isn't working, not sure why
		export NVM_DIR="$HOME/.nvm"
		source "/usr/local/opt/nvm/nvm.sh"
	;;

	"iandunn.name" | "n2"* )
		export PATH="$HOME/bin:$HOME/opt/bin:$PATH:/usr/local/sbin:/usr/sbin:/sbin"
	;;
esac

source $DOTFILES_DIR/bin/git-completion.bash
source $DOTFILES_DIR/bin/hub-completion.bash
source $DOTFILES_DIR/bin/wp-cli-completion.bash

#todo source bash-completion, but need to setup path per environment. dont leak root paths
	# maybe more proper to go in .bash_profile that .bashrc

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

# Deploy the site that corresponds to the current directory
function deploy {
	current_folder=$(pwd)
	printf "\n"

	case "$current_folder" in
		*wordcamp.test* )
			ssh wordcamp.org 'deploy-wordcamp.sh'
		;;

		*wp15.wordpress.test* )
			ssh -t wp15.wordpress.net 'svn up ~/wp15.wordpress.net'
		;;

		*iandunn.localhost* | *silencedmajority.test* )
			deployer deploy
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
	/usr/local/bin/phpmd $1 text ~/vhosts/localhost/wordcamp.test/phpmd.xml.dist
}
