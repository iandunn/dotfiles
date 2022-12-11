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

// Necessary for home row mods
#define IGNORE_MOD_TAP_INTERRUPT

//#define TAPPING_TERM 220
	// todo fail b/c redefining var from upstream
	// is there a way to not include the upstream config? or to change the value?
	// otherwise that's bad. could work around with the get_tapping_term() func but shouldn't have to
	// work around with get_tapping_term for now, but circle back if stick with this to clean up

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
