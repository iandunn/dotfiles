// See https://docs.qmk.fm/#/config_options?id=the-configh-file

#undef ONESHOT_TIMEOUT
#define ONESHOT_TIMEOUT 2885

#define USB_SUSPEND_WAKEUP_DELAY 0
#undef MOUSEKEY_WHEEL_DELAY
#define MOUSEKEY_WHEEL_DELAY 0

#undef MOUSEKEY_WHEEL_INTERVAL
#define MOUSEKEY_WHEEL_INTERVAL 75

#undef MOUSEKEY_WHEEL_TIME_TO_MAX
#define MOUSEKEY_WHEEL_TIME_TO_MAX 80

#define FIRMWARE_VERSION u8"wEZWj/QM7mp"

// Necessary for home row mods to work well
#define IGNORE_MOD_TAP_INTERRUPT

// see https://precondition.github.io/home-row-mods#finding-the-sweet-spot for tips on setting this
// default is 200, people generally choose between 150-220
// if mods are being accidentally activated, you need to increase the tapping term. if they're not, you need to lower it
#undef TAPPING_TERM
#define TAPPING_TERM 210

#define TAPPING_TERM_PER_KEY
	// tmp to work around not being able to redefine taippingterm

// solves problems when need to type something like sI, where you tap a mod-tap and then need to hold that same key immediately after
// may cause problems with holding down arrow keys? no, seems ok so far
// may cause problems with using WSAD in games? need to test. if does, not sure if better to turn off, or work around.
// may cause problems with layer keys? if so then TAPPING_FORCE_HOLD_PER_KEY might help
// read https://precondition.github.io/home-row-mods#tapping-force-hold again to consider options
#define TAPPING_FORCE_HOLD

// might do more harm than good?
// if you start getting accidental mod activations then reconsider. read precondition article for more info
#define PERMISSIVE_HOLD
