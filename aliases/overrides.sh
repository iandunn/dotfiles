#!/bin/bash

# The default aliases are for my primary workstation, but some of them won't work on other devices, especially Linux servers.
# Those can be overridden here when needed.

case $(hostname) in
    "foo" | "bar" )
		alias tar='tar --exclude-vcs'
	;;
esac;
