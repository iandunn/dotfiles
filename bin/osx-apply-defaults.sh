#!/bin/bash

## Host-specific aliases
case $(sysctl hw.model) in
	*"iMac"* )
		DEVICE_TYPE="desktop"
	;;

	*"MacBook"* )
		DEVICE_TYPE="laptop"
	;;

	* )
		echo "Device type could not be determined, aborting."
		exit 1
	;;
esac


# TODO
#
# Browse through http://defaults-write.com for more
# Disable keyboard backlighting
# will need to sync these changes w/ local uncommitted mods from Mackenzie
# Ctrl-left/right to switch desktops: make it faster
# only show menu bar on secondary screen, not primary
# Speed up character reapeat in terminal
# Turn on character repeat in regular apps
# Turn of fracking autocorrect
# Other security best practices that you can automate?
# disable Spotlight Suggestions

###
### Finder
###

# Show all filename extensions
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Show hidden files by default
defaults write com.apple.finder AppleShowAllFiles -bool true

# Show hidden files in the Open dialog (not working)
defaults write -g AppleShowAllFiles -bool true

# Show the ~/Library folder
chflags nohidden ~/Library

# Show the full path in the title bar
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true

# Disable the warning when changing a file extension
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# Empty Trash securely by default
defaults write com.apple.finder EmptyTrashSecurely -bool true

# Reduce transparency of the Finder sidebar
defaults write com.apple.universalaccess reduceTransparency -boolean true


###
### Dock
###

# Get rid of the Dock as much as humanly possible
defaults write com.apple.dock autohide -bool true

# Increase the dock appear delay to prevent it from getting in the way when trying to hover on scroll bars
defaults write com.apple.dock autohide-delay -float 2500

# Keep the obnoxious 5px Dock gap on the secondary monitor so it's less noticeable
defaults write com.apple.Dock orientation -string right


###
### Screen Saver / Energy / Lock time
###

# Use secure/energy saving settings while travelling, and more convenient settings at home
if [ 'desktop' == $DEVICE_TYPE ]; then
	SCREEN_SAVER_IDLE_TIME=900
	SCREEN_SAVER_LOCK_DELAY=60
else
	SCREEN_SAVER_IDLE_TIME=300
	SCREEN_SAVER_LOCK_DELAY=10
fi

# Set screen saver time.
#
# Arrogant and short-sighted designers at Apple only allow picking set values from dropdown in the UI, instead of
# entering desired value via input field.
defaults write com.apple.screensaver idleTime $SCREEN_SAVER_IDLE_TIME

# Turn the monitor off when idle.
#
# Let the screen saver run for a bit first, though, since I like seeing my iTunes album covers
if [ 'laptop' == $DEVICE_TYPE ]; then
	sudo pmset -b displaysleep 5
	sudo pmset -b disksleep 5
	sudo pmset -b sleep 10
fi
sudo pmset -c displaysleep 20
sudo pmset -c disksleep 20
sudo pmset -c sleep 30

# Require password to unlock, with an optional grace period
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int $SCREEN_SAVER_LOCK_DELAY



###
### Misc
###

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

# Limit Time Machine space, because it shares the disk with other things
#sudo defaults write /Library/Preferences/com.apple.TimeMachine MaxSize 850000
# want more for flanders, less for macenzie. this is just a bash script, so just check the hostname

# Full keyboard mode
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

# Make notification banners show up for longer than the default
defaults write com.apple.notificationcenterui bannerTime 6

# Disable mouse acceleration, to improve aiming in games. Default value is 0.875.
defaults write .GlobalPreferences com.apple.mouse.scaling -1

# https://github.com/electron/electron/issues/13164#issuecomment-435735605
defaults write -g NSRequiresAquaSystemAppearance -bool Yes
# todo need to logout to see if ^ worked

# Change the login screen background
# This can be an HEIC, JPG, or PNG. HEICs with multiple frames will just use the first? or is there a way to specify one?
# WARNING: For this to take effect, you have to manually toggle "Preferences > Security > Show message when screen locked" b/c of https://superuser.com/a/364587/121091. Can change them back afterwards
# Doesn't seem like you need to delete `lockscreen.png`, the `heic` takes precendence.
# todo - get UUID dynamically
# ln -sf "/System/Library/Desktop Pictures/Solid Colors/Stone.png" "/Library/Caches/Desktop Pictures/DC73FE49-1CB7-459B-AD9D-E9BA6173FCFB/lockscreen.png"
# ln -sf "/Library/Desktop Pictures/Mojave Night.jpg" "/Library/Caches/Desktop Pictures/DC73FE49-1CB7-459B-AD9D-E9BA6173FCFB/lockscreen.jpg"
ln -s "/System/Library/Desktop Pictures/Big Sur.heic" "/Library/Caches/Desktop Pictures/DC73FE49-1CB7-459B-AD9D-E9BA6173FCFB/lockscreen.heic"



###
### Restart any services that were affected
###

killall Dock
