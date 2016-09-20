# Environmental variables
export EDITOR="nano"
export SVN_EDITOR="nano -w"

# todo maybe use \nano or /usr/bin/nano to avoid the -w and force line wrapping during git/svn commits

# Host-specific environmental variables
case $(hostname) in
	"iandunn.name" | "n2"* )
		export PATH="$HOME/bin:$PATH"
	;;
esac

if [ -f ~/bin/git-completion.bash ]; then
  source ~/bin/git-completion.bash
fi

#todo source bash-completion, but need to setup path per environment. dont leak root paths
	# maybe more proper to go in .bash_profile that .bashrc

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
	eval "deploy wp-content"
}
