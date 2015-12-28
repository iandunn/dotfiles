# Environmental variables
export EDITOR="nano"
export SVN_EDITOR="nano -w"

# todo maybe use \nano or /usr/bin/nano to avoid the -w and force line wrapping during git/svn commits

# Host-specific environmental variables
case $(hostname) in
	"iandunn.name" )
		export PATH="$HOME/bin:$PATH"
	;;
esac
