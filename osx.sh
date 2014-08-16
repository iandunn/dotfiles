#!/bin/bash

###
### Finder
###

# Show all filename extensions
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Show hidden files by default
defaults write com.apple.finder AppleShowAllFiles -bool true

# Show hidden files in the Open dialog
defaults write -g AppleShowAllFiles -bool true

# Show the ~/Library folder
chflags nohidden ~/Library

# Disable the warning when changing a file extension
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# Empty Trash securely by default
defaults write com.apple.finder EmptyTrashSecurely -bool true



###
### Misc
###

# Increase the dock appear delay to ~4 seconds. I never use it and it pops up when I am trying to hover on horizontal scroll bars in Chrome.
# TODO

# Remove or reduce window shadows to avoid them overlapping full screen windows.
# TODO - There doesn't seem to be a good, reliable solution to this, but keep looking.

# Save screenshots to the Downloads directory instead of the Desktop
defaults write com.apple.screencapture location ~/Downloads/
