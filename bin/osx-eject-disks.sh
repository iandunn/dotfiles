#!/bin/bash

# Use Automattor.app to create a Quick Action for this:
    # When workflow receives: no input
    # in: any application
    # Add a Run Shell Script action with the path to this file.
    # Save the Quick Action.
# Then go to Preferences > Keyboard Shortcuts > Services > General. Assign a shortcut like command+option+e


mounted_volumes=$(diskutil list | grep 'external' | grep '/dev/disk' | awk '{print $1}')

printf "\nEjecting external mounted disks..."

for volume in $mounted_volumes; do
    printf "\nEjecting $volume...\n"
    diskutil eject "$volume"
done

printf "\nAll external disks have been ejected.\n"
afplay /System/Library/Sounds/Funk.aiff
