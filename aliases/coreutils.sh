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

alias updatedb='sudo /usr/libexec/locate.updatedb'
