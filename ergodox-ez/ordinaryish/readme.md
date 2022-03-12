# ordinary-ish Ergodox EZ layout

[View layout](https://configure.zsa.io/ergodox-ez/layouts/wEZWj/latest/0)

* Base layer based on [Ordinary](/layouts/community/ergodox/ordinary/readme.md)
* [Colemak](https://colemak.com/)
* [One shot modifiers](/docs/one_shot_keys.md), using [Callum Oakley's implementation](/users/callum/readme.md)
* Additional layers for navigation & media
* Remove some hard to reach keys


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
1. `qmk flash`