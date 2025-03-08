#!/bin/bash

# ls --group-directories-first requires `coreutils` from Homebrew on OS X b/c native `ls` doesn't support sorting folders first
alias ls='gls --almost-all --group-directories-first --color'
alias ll='ls -lh --time-style="+%b %e %Y %l:%M:%S %P"'	# always show the year, and use 12-hour time
alias less='less -SR'
alias lessn='less -N'
alias df='df -h'
alias du='du -h'
alias grep='grep -i'
alias rm='rm -i'
alias diff='diff -u'
alias diffsplit='/usr/bin/diff -y -W 250' # full path b/c -y conflicts w/ -u alias
alias stat='stat -x'
alias which='which -a'
alias locate='locate -i'
alias zip='zip -r'

alias date='gdate "+%b %e %Y %l:%M:%S %P"' # use GNU date instead of BSD date for consistency across machines
alias timeutc='gdate --utc --date="@$1"'
	# todo gdate: invalid date ‘@’
alias timelocal='gdate --date='@''
	# todo gdate: invalid date ‘@’

alias ..="cd .."
alias ...="cd .. && cd .."
alias ....="cd .. && cd .. && cd .."
alias .....="cd .. && cd .. && cd .. && cd .."

# This assumes you're in the directory you want to search
alias findgrep='find . -type f ! -path '*/.svn/*' ! -path '*/.git/*' -follow |xargs grep --ignore-case --line-number --no-messages'
# also add build, vendor, etc folders to exclude?
# maybe need something like b/c exclude above doesn't work
# function grep() {
#	/bin/grep --exclude-dir=.svn "$@"
#}
#also exclude binary files

alias updatedb='sudo /usr/libexec/locate.updatedb'
