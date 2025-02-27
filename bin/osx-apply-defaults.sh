#!/bin/bash

## Host-specific aliases
case $(sysctl hw.model) in
	*"iMac"* | "Mac 14,12" )
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
# set dock "Prefer tabs when opening documents” to "manually". otherwise opening new textedit window will grab a window from another desktop and pull it to the current one
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
# Prefs > Mission > When switching to an applicaiton, switch space... > disable
# prefs > accessibi > display > reduce transparency
# prefs > sec > advanced > required admin password for network-wide prefs
# prefs > sound > sound effects > play sound on startup > off
# time machine ignored folders
# default skin tone - maybe com.apple.EmojiPreferences
# test out disabling desktop icons - defaults write com.apple.finder CreateDesktop false; killall Finder
# shorten incorrect pw delay, tradeoffs not worth it - https://www.google.com/search?q=mac+pam.d+incorrect+password+delay&sxsrf=ALeKk00b0kcTN20ch8UYhpPHKMlQUIhmtA%3A1621802079762&ei=X7yqYPvzLc610PEP26WwoAI&oq=mac+pam.d+incorrect+password+delay&gs_lcp=Cgdnd3Mtd2l6EAM6BwgAEEcQsANQ4JMHWLeWB2DPlwdoAXACeACAAUKIAa8CkgEBNZgBAKABAaoBB2d3cy13aXrIAQjAAQE&sclient=gws-wiz&ved=0ahUKEwi7n_DG0-DwAhXOGjQIHdsSDCQQ4dUDCA4&uact=5


# sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.locate.plist

###
### Finder
###

# Show all filename extensions - not sure if both are necessary
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
defaults write com.apple.finder AppleShowAllFiles -boolean true

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
#defaults write com.apple.universalaccess reduceTransparency -boolean true
#  get error: 2021-03-16 07:37:11.901 defaults[8022:3831499] Could not write domain com.apple.universalaccess; exiting


###
### Dock
###

# Get rid of the Dock as much as humanly possible
defaults write com.apple.dock autohide -bool true

# Increase the dock appear delay to prevent it from getting in the way when trying to hover on scroll bars
defaults write com.apple.dock autohide-delay -float 2500

# Keep the obnoxious 5px Dock gap on the secondary monitor so it's less noticeable
# defaults write com.apple.Dock orientation -string right
# don't see this anymore, might not be needed

# Show the window switcher on both monitors
defaults write com.apple.Dock appswitcher-all-displays -bool true


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
#sudo pmset -c displaysleep 20
#sudo pmset -c disksleep 20
#sudo pmset -c sleep 30
# tmp disabled to see if it was causing problems w/ external hard drive disconnected while sleep warnings

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
# want more for mac mini than macbook, or vice versa? this is just a bash script, so just check the hostname

# Full keyboard mode
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

# Make notification banners show up for longer than the default
defaults write com.apple.notificationcenterui bannerTime 6

# Disable mouse acceleration, to improve aiming in games. Default value is 0.875.
#defaults write .GlobalPreferences com.apple.mouse.scaling -1
#tmp disable to b/c might want it with new mice?
# need to write sensitivity too

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
#ln -s "/System/Library/Desktop Pictures/Big Sur.heic" "/Library/Caches/Desktop Pictures/DC73FE49-1CB7-459B-AD9D-E9BA6173FCFB/lockscreen.heic"
# tmp disable b/c need to update uuid and want to make sure no problems before doing this


# todo from running:
# Warning: Idle sleep timings for "AC Power" may not behave as expected.
#- Disk sleep should be non-zero whenever system sleep is non-zero.


# Specify the preferences directory for tracked app
defaults write com.googlecode.iterm2 PrefsCustomFolder -string "~/.dotfiles/iterm2"

# Tell iTerm2 to use the custom preferences in the directory
defaults write com.googlecode.iterm2 LoadPrefsFromCustomFolder -bool true


###
### Restart any services that were affected
###

killall Dock
killall Finder
