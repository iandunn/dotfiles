# Share ssh-agent between terminal sessions.
# Without this, you'd have to `ssh-add [key]` every time you open a new terminal.
# This can't be in `.bashrc`, it has to be here.
function share_ssh_agent {
	export SSH_AUTH_SOCK=~/.ssh/ssh-agent.$HOSTNAME.sock

	# might need to rm the old file when shutting down? otherwise get error after reboot:
	# 	unix_listener: cannot bind to path /Users/iandunn/.ssh/ssh-agent.milo.local.sock: Address already in use
	# but maybe that was just because it crashed instead of rebooting normally

	# even if above is fixed, it stiil seems like the keys are only added to memory, not the keychain

	# maybe all this is no longer needed after running `ssh-add --apple-use-keychain` instead of plain `ssh-add`?
	# ran that for 10up/personal/cadmv on 9/5/2025, see if still need to enter pw after rebooting
	# note, that didn't fix it

	ssh-add -l 2>/dev/null >/dev/null

	if [ $? -ge 2 ]; then
		ssh-agent -a "$SSH_AUTH_SOCK" >/dev/null
	fi
}

#share_ssh_agent

source ~/.bashrc
