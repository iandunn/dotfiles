// See https://docs.qmk.fm/#/config_options?id=the-configh-file

/*
 * Misc
 */
#define FIRMWARE_VERSION u8"wEZWj/QM7mp"

#undef ONESHOT_TIMEOUT
#define ONESHOT_TIMEOUT 2885

#define USB_SUSPEND_WAKEUP_DELAY 0


/*
 * Mouse Keys
 */
#undef MOUSEKEY_WHEEL_DELAY
#undef MOUSEKEY_WHEEL_INTERVAL
#undef MOUSEKEY_WHEEL_TIME_TO_MAX
#undef MOUSEKEY_INTERVAL
#undef MOUSEKEY_TIME_TO_MAX

#define MOUSEKEY_INTERVAL 25
#define MOUSEKEY_TIME_TO_MAX 80

#define MOUSEKEY_WHEEL_DELAY 0
#define MOUSEKEY_WHEEL_INTERVAL 65
#define MOUSEKEY_WHEEL_TIME_TO_MAX 80

// This has potential, but may not be worth the effort to perfect and then learn.
// #include "home-row-mods.h"
