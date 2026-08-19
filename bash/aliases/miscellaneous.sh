#!/bin/bash

alias zadd='zoxide add .'

# Usage: watch curl -iks https://misc.wordcamp.test/2016/tmp/ |grep WordCampBlocks
# Note this will watch the current working directory and rerun the command when any file changes.
alias watch='fswatch -o $(pwd) |xargs -n1 -I{} $1'

alias mic='micro'
alias soal='source ~/.bash_aliases'
alias soba='source ~/.bashrc'

alias qflash='qmk lint && qmk compile && qmk flash'

# When unplug external webcam (like when traveling), then plug back in, it's not recognized until restart service
alias fix-camera='sudo killall VDCAssistant'

# todo see if there's one for the headset mic too
# try sudo pkill coreaudiod
# that didn't work, is there anything else?

# This is insane that OSX makes you do this any time you want to open a file in an app
# alias unquarantine='xattr -d com.apple.quarantine'
# need to test more, make sure this doesn't open up vulnerabilities beyond just files i download yourself (and therefore trust)
