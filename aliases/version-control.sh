#!/bin/bash

###
### subversion
###

# todo move these below w/ version control. clean up this file in general
# cleans up externals within the pwd too
# can just do `svn cleanup --include-externals` instead?
alias svn-cleanup-deep="find . -name '.svn' | sed 's/.svn//' | xargs -I% svn cleanup %"
# todo move ^ into vcs section below
#same for others above it

# Git is a bit more forgiving than SVN, so running SVN first leads to fewer conflicts.
alias pullup='svn up && git pull'
	# todo if w.org sandbox, `svnup`
	# add a `git checkout .` before git pull? that would avoid `cant pull with rebase, you have unstaged changes` errors. but might also discard uncommitted changes that i want to keep
	# could maybe do git pull --autostash instead

# todo works manually but not as alias
# probably need to escape $2 to be \$2 and other stuff
# but probably easier to make it a function like svn-rm-untracked is
	# maybe something like this, but need to remove the `rm` stuff: svn st $DIR |awk '/^!/ { print "svn rm -q "$2; } /^[?]/ { print "svn add -q "$2; }' | sh
# todo also grep for begining of sentance, to avoid false matches
# alias svn-add-untracked="svn add $(svn status | grep [^?] | awk '{print $2}')"

alias svn-revert-clean="svn-revertr && svn-rm-untracked"


# remove noise from externals
# the full wording here is verbose, but remember that bash does tab completion on aliases too
alias svn-stat-pruned='clear && echo -e "" && svn status | grep ^[?!MAD]'
alias svn-stat-pruned-tracked='svn status | grep ^[MAD]'
# todo: "alias svn-stat-deep" which will include externals in subdirectories. probably needs to be a function rather than an alias

alias svn-showhead='svn up --ignore-externals && svn diff -rPREV |less'

# todo setup https://stackoverflow.com/a/3885594/450127 so `svn ci` also prints the diff like git does

alias svn-externals='svn propedit svn:externals .'
alias svn-ignore='svn propedit svn:ignore .'

alias svn-diffw='svn diff -x --ignore-all-space'
# naming not consistent w/ `git diffw` alias?

alias svn-revertr='svn revert -R'
#rename this and others to not have the - in it? breaks typing flow
alias svnrevr='svn revert -R'


###
### Git
###
alias push-deploy='git push && deploy'
alias pushdeploy='push-deploy'

# cd to Git repo and `pr 510` to checkout the branch for that PR
alias prc='git fetch && gh pr checkout'