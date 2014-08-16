#!/bin/bash


###
### Finder
###

# Show hidden files by default
defaults write com.apple.finder AppleShowAllFiles -bool true

# Show all filename extensions
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Disable the warning when changing a file extension
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# Empty Trash securely by default
defaults write com.apple.finder EmptyTrashSecurely -bool true

# Show the ~/Library folder
chflags nohidden ~/Library

# Show hidden files in the Open dialog. Not sure if there's a default for this.
# TODO


###
### Misc
###

# Make application bar appear slowly b/c i want it hidden most of the time

