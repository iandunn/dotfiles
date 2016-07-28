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

#todo source bash-completion, but need to setup path per environment. dont leak root paths
	# maybe more proper to go in .bash_profile that .bashrc