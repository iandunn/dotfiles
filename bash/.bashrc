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
export PATH="$PATH:$HOME/bin:$DOTFILES_DIR/bin"
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:$HOME/.composer/vendor/bin"
export PATH="$PATH:/opt/elasticsearch/bin/:/usr/local/elasticsearch/bin/"

export HOMEBREW_PREFIX=$(brew --prefix) # Different on laptop and desktop because intel vs silicon
eval "$($HOMEBREW_PREFIX/bin/brew shellenv)"

# This makes it so that LocalWP sites will use their version of php instead of the global one
# This has to come after "brew shellenv" above
if [ -n "$LOCALWP_PHP_PATH" ]; then
	export PATH="$LOCALWP_PHP_PATH:$PATH"
fi

# Fix git-svn, see https://github.com/Homebrew/homebrew-core/issues/52490#issuecomment-792604853
# will need to update when perl version changes
export PERL5LIB=$HOMEBREW_PREFIX/lib/perl5/site_perl/5.30.3/darwin-thread-multi-2level/

# Lots of stuff breaks when it's updated, so I want to manually update individual packages when I can supervise it.
export HOMEBREW_NO_AUTO_UPDATE=1

export KUBECONFIG=~/.kube/comicskingdom.yml

#export WP_TESTS_DIR="$HOME/vhosts/localhost/wp-develop.test/public_html/tests/phpunit"
# export MH_OUTGOING_SMTP="/usr/local/etc/mailhog/outgoing-smtp.json"   this isn't working, not sure why
export WP_TESTS_DIR="/Users/iandunn/local-sites/wordpress-tests-lib"
export WP_CORE_DIR="/Users/iandunn/local-sites/wordpress-tests-app"
export WORDPRESS_DB_NAME=wordpress_develop_tests
export WORDPRESS_DB_USER=wp_tests
export WORDPRESS_DB_PASSWORD=wp_tests

export NVM_DIR="$HOME/.nvm"
\. "$HOMEBREW_PREFIX/opt/nvm/nvm.sh"
\. "$HOMEBREW_PREFIX/opt/nvm/etc/bash_completion.d/nvm"


export GPG_TTY=$(tty)
export GITLEAKS_CONFIG=~/.config/gitleaks/gitleaks.toml

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

_wp_complete() {
	local OLD_IFS="$IFS"
	local cur=${COMP_WORDS[COMP_CWORD]}

	IFS=$'\n';  # want to preserve spaces at the end
	local opts="$(wp cli completions --line="$COMP_LINE" --point="$COMP_POINT")"

	if [[ "$opts" =~ \<file\>\s* ]]
	then
		COMPREPLY=( $(compgen -f -- $cur) )
	elif [[ $opts = "" ]]
	then
		COMPREPLY=( $(compgen -f -- $cur) )
	else
		COMPREPLY=( ${opts[*]} )
	fi

	IFS="$OLD_IFS"
	return 0
}
complete -o nospace -F _wp_complete wp
complete -o nospace -F _wp_complete wpdev


if [[ 'iTerm.app' = $TERM_PROGRAM ]]; then
	source ~/.iterm2_shell_integration.bash
fi

# Have to edit install Bash v5, edit `/etc/shells`, then `chsh`` in order for this to work.
# See https://github.com/JanDeDobbeleer/oh-my-posh/discussions/3429#discussioncomment-4910228
# See https://github.com/JanDeDobbeleer/oh-my-posh/issues/3430
eval "$(oh-my-posh init bash --config "$HOME/dotfiles/bash/iandunn.omp.yml")"

eval "$(zoxide init bash)"

# These should run last so that poorly-written functions don't use them (e.g., something using `grep`
# instead of `command grep`) errors because `grep` is aliased to "use rg instead"
source ~/dotfiles/bash/functions.sh
source ~/.bash_aliases
