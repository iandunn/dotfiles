# US No Dead Keys

## What?

This is a Mac keyboard layout bundle; i.e., the kind you select from `System Preferences > Keyboard > Input Sources`.

It is based on the `US` layout, but has been modified to remove all [dead keys](https://wikipedia.org/wiki/Dead_key).

This is different from the layout that gets programmed into a mechanical keyboard, and works in conjunction with it. It's entirely possible (and often desirable) to have a US layout in OS X, but a totally different layout on the keyboard (like [Colemak](https://colemak.com)).


## Why?

For me, when using [home row modifiers](https://precondition.github.io/home-row-mods), the dead keys interfere with finger rolls like "ion" on the Colemak layout. Instead of producing the desired characters, you'd get something like `ø˜`.

There are presumably many other situations where they're undesirable.


## Installation

1. `cp -R "US No Dead Keys.bundle" "~/Library/Keyboard Layouts"`
1. (optional) If you want to keep a canonical source in a different folder, you can symlink the individual `.keylayout` file:
	`cd "~/Library/Keyboard Layouts/US No Dead Keys.bundle/Contents/Resources"`
	`ln -sf "path/to/canonical/file.keylayout" "~/Library/Keyboard Layouts/US No Dead Keys.bundle/U.S. No Dead Keys.keylayout"`

1. Logout and back in, so OSX will load the new bundle.
1. Open `System Preferences > Keyboard > Input Sources` and add `U.S. No Dead Keys`. It will be at the top of the list rather than sorted alphabetically.
1. Activate it by clicking the "input sources" icon in the menu bar, or by using the keyboard shortcut `command alt space`.

This entire folder has do be copied, it isn't enough to just copy the `.keylayout` file. OSX won't follow a symlink for the entire folder, and hard links can't be created for directories. OSX will follow the symlink for the `.keylayout` file if it's parent folder is physically present in `~/Library/Keyboard Layouts` though.


## Notes

This file cannot be inside the `.bundle` folder, because Ukelele will delete it automatically when opening the bundle.
