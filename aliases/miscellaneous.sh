#!/bin/bash

# I'm using autojump instead of z, but this is more ergonomic on Colemak, and I'm already used to it from using rupa/z.
alias z='j'

# Usage: watch curl -iks https://misc.wordcamp.test/2016/tmp/ |grep WordCampBlocks
# Note this will watch the current working directory and rerun the command when any file changes.
alias watch='fswatch -o $(pwd) |xargs -n1 -I{} $1'

alias mic='micro'
alias omp='oh-my-posh'
alias soal='source ~/.bash_aliases'
alias soba='source ~/.bashrc'

alias qmklf='qmk lint && qmk flash'

# When unplug external webcam (like when traveling), then plug back in, it's not recognized until restart service
alias fix-camera='sudo killall VDCAssistant'

# todo see if there's one for the headset mic too
# try sudo pkill coreaudiod
# that didn't work, is there anything else?
