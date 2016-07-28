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

# Reduce transparency of the Finder sidebar
defaults write com.apple.universalaccess reduceTransparency -boolean true


###
### Misc
###

# Increase the dock appear delay to ~4 seconds. I never use it and it pops up when I am trying to hover on horizontal scroll bars in Chrome.
# TODO

# Remove or reduce window shadows to avoid them overlapping full screen windows.
# TODO - There doesn't seem to be a good, reliable solution to this, but keep looking.

# Save screenshots to the Downloads directory instead of the Desktop
defaults write com.apple.screencapture location ~/Downloads/

# Don't change spaces when closing an application
defaults write com.apple.Dock workspaces-auto-swoosh -bool NO

# Repeat characters when holding down a key, instead of showing accent dialog box
defaults write -g ApplePressAndHoldEnabled -bool false

# Check for software updates daily instead of once per week
defaults write com.apple.SoftwareUpdate ScheduleFrequency -int 1

# Limit Time Machine to 400GB, because it shares the disk with other things
sudo defaults write /Library/Preferences/com.apple.TimeMachine MaxSize 400000

# todo disable Spotlight Suggestions

# Full keyboard mode
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

# Make notification banners show up for longer than the default
defaults write com.apple.notificationcenterui bannerTime 6