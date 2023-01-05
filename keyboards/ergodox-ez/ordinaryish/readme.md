# ordinary-ish Ergodox EZ layout

The primary goal for this is to reduce RSI pain.
The secondary goal is to stay as close to an "ordinary" keyboard layout as possible, to reduce the learning curve and time spent creating it.

## Layers

0. Base
	* Similar to [Ordinary](https://github.com/qmk/qmk_firmware/blob/7eb6f86bc0aac3ff83abe4365cd11c5c195dc403/layouts/community/ergodox/ordinary/readme.md), including arrow keys on the right thumb cluster.
	* [Colemak](https://colemak.com/).
	* [Home row modifiers](https://precondition.github.io/home-row-mods).
		* The CASG order was chosen to [minimize hand swaping](https://precondition.github.io/home-row-mods#gasc) when typing capital letters.
		* The [US No Dead Keys](https://github.com/iandunn/dotfiles/tree/master/keyboards/US%20No%20Dead%20Keys) OSX layout is also needed, to prevent accidental dead keys with words like "version", "vacation", etc.
	* Remove some hard-to-reach keys to avoid twisting and stretching hands.
1. [One shot modifiers](https://github.com/qmk/qmk_firmware/blob/7eb6f86bc0aac3ff83abe4365cd11c5c195dc403/docs/one_shot_keys.md) on the home row.
    * Use these whenever possible, because chording the home row modifiers on the base layer contributes to RSI. Sometimes it's not practical, though, like when multiple modifiers need to be activated.
    * Note that there's a QMK bug that locks them, but [a workaround is available](https://github.com/qmk/qmk_firmware/issues/3963#issuecomment-1074525658).
2. Navigation, macros, and other miscellaneous keys that are commonly used.
	* Home row arrow keys on the right hand. These are comfortable when you don't need to combine them with any modifiers. When you need to do things like `alt-left` to jump words though, the arrows on the base layer are sometimes easier to work with. The tradeoff is that you have to move your hand to get there, since the Ergodox thumb cluster so big that not all the thumb keys are accessible with a thumb.
	* Tab navigation
	* Home row mouse keys on the left hand.
3. Miscellaneous keys that aren't commonly used: Volume, brightness, etc.

## Installation

1. [Setup QMK](https://docs.qmk.fm/#/newbs_getting_started). The latest release I've tested is `0.19.6`, but it may work on newer ones.
1. Symlink this folder to `{qmk checkout}/keyboards/ergodox_ez/keymaps/iandunn/`
1. Set these config values
	```sh
	> qmk config
	multibuild.keymap=default
	user.keyboard=ergodox_ez
	user.keymap=iandunn
	```
1. `cd {qmk checkout}`
1. `qmk lint && qmk flash`
