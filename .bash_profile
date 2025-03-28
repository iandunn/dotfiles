# Share ssh-agent between terminal sessions.
# Without this, you'd have to `ssh-add [key]` every time you open a new terminal.
# This can't be in `.bashrc`, it has to be here.
function share_ssh_agent {
	export SSH_AUTH_SOCK=~/.ssh/ssh-agent.$HOSTNAME.sock

	ssh-add -l 2>/dev/null >/dev/null

	if [ $? -ge 2 ]; then
		ssh-agent -a "$SSH_AUTH_SOCK" >/dev/null
	fi
}

share_ssh_agent

source ~/.bashrc
