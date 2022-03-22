# ordinary-ish Ergodox EZ layout

[View layout](https://configure.zsa.io/ergodox-ez/layouts/wEZWj/latest/0)

* Base layer based on [Ordinary](https://github.com/qmk/qmk_firmware/blob/7eb6f86bc0aac3ff83abe4365cd11c5c195dc403/layouts/community/ergodox/ordinary/readme.md)
* [Colemak](https://colemak.com/)
* [One shot modifiers](https://github.com/qmk/qmk_firmware/blob/7eb6f86bc0aac3ff83abe4365cd11c5c195dc403/docs/one_shot_keys.md).
	* Note that there's a QMK bug that locks them, but [a workaround is available](https://github.com/qmk/qmk_firmware/issues/3963#issuecomment-1074525658).
* Additional layers for navigation & media
* Remove some hard-to-reach keys


## Installation

1. [Setup QMK](https://docs.qmk.fm/#/newbs_getting_started)
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
