#include QMK_KEYBOARD_H
#include "version.h"

#ifdef CONSOLE_ENABLE
	#include <print.h>
#endif

// This has to come before `keycodes` and `process_record_user`.
enum custom_keycodes {
	RGB_SLD = EZ_SAFE_RANGE,
	ST_MACRO_NULL, // Unused, but must exist to avoid weird conflict between macros and one-shot keys.
	ST_MACRO_DASHES,
	ST_MACRO_CHECKBOX,
	ST_MACRO_YAHOO
};

// Enable the constant to see output in QMK Toolkit.
// Mac's on-screen keyboard viewer is also useful, and works even when not active application.
void keyboard_post_init_user( void ) {
	#ifdef CONSOLE_ENABLE
		debug_enable = true;
	#endif

	//debug_matrix = true;      // on/off matrix for each key
	//debug_keyboard = true;    // keyboard_report: 00 00 29 00 00 00 00 00
	//debug_mouse = true;       // mousekey [btn|x y v h](rep/acl): [00|0 0 0 0](0/0) - for simulated mouse keys
}

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
	/*
	 * Both sides use LALT because RALT is AltGR and I don't need those characters, and they occasionally cause accidents.
	 */
	[0] = LAYOUT_ergodox_pretty(
		KC_ESCAPE, KC_1, KC_2, KC_3, KC_4, KC_5, KC_6,              KC_TRANSPARENT, KC_7, KC_8, KC_9,     KC_0,   KC_MINUS,  KC_EQUAL,
		KC_GRAVE,  KC_Q, KC_W, KC_F, KC_P, KC_G, KC_LCBR,           KC_RCBR,        KC_J, KC_L, KC_U,     KC_Y,   KC_SCOLON, KC_BSLASH,
		KC_TAB,    KC_A, KC_R, KC_S, KC_T, KC_D,                    KC_H,           KC_N, KC_E, KC_I,     KC_O,   KC_QUOTE,
		OSM(MOD_LSFT), KC_Z, KC_X, KC_C, KC_V, KC_B, KC_LBRACKET,   KC_RBRACKET,    KC_K, KC_M, KC_COMMA, KC_DOT, KC_SLASH,   OSM(MOD_RSFT),
		OSM(MOD_LCTL), KC_TRANSPARENT, KC_TRANSPARENT, OSM(MOD_LALT), OSM(MOD_LGUI), OSM(MOD_RGUI), OSM(MOD_LALT), KC_TRANSPARENT, KC_TRANSPARENT, OSM(MOD_RCTL),

					 OSL(2), KC_PGUP,                               KC_LEFT, KC_RIGHT,
					       KC_PGDOWN,                               KC_UP,
		KC_BSPACE, OSL(1), KC_DELETE,                               KC_DOWN, KC_ENTER, KC_SPACE
	),

	[1] = LAYOUT_ergodox_pretty(
		KC_TRANSPARENT, KC_F1, KC_F2, KC_MS_BTN3, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,         KC_TRANSPARENT, KC_PGUP,KC_MS_ACCEL0, KC_MS_ACCEL1, ST_MACRO_YAHOO, ST_MACRO_DASHES, ST_MACRO_CHECKBOX,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_MS_BTN1, KC_MS_UP, KC_MS_BTN2, KC_TRANSPARENT, KC_TRANSPARENT,                   KC_TRANSPARENT, KC_MS_WH_DOWN, RGUI(RSFT(KC_LBRACKET)),KC_UP, RGUI(RSFT(KC_RBRACKET)),KC_HOME,KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_MS_LEFT, KC_MS_DOWN, KC_MS_RIGHT,KC_TRANSPARENT, KC_MS_WH_UP,                    KC_LEFT,KC_DOWN,KC_RIGHT, KC_END, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,     KC_TRANSPARENT, KC_PGDOWN, RGUI(KC_LBRACKET),KC_TRANSPARENT, RGUI(KC_RBRACKET),KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,     KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,

		KC_TRANSPARENT, KC_TRANSPARENT,                     KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT,                                     KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,     KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT
	),

	[2] = LAYOUT_ergodox_pretty(
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_BRIGHTNESS_UP,KC_AUDIO_VOL_UP,KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_MEDIA_PREV_TRACK,KC_MEDIA_REWIND,KC_MEDIA_PLAY_PAUSE,KC_MEDIA_FAST_FORWARD,KC_MEDIA_NEXT_TRACK,KC_TRANSPARENT, KC_BRIGHTNESS_DOWN,KC_AUDIO_VOL_DOWN,KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, WEBUSB_PAIR,WEBUSB_PAIR,KC_TRANSPARENT, KC_TRANSPARENT, KC_AUDIO_MUTE, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,

		KC_TRANSPARENT, KC_TRANSPARENT,                     KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT,                                     KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,     KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT
	),

	[3] = LAYOUT_ergodox_pretty(
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT, KC_MEH,         KC_HYPR,        KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT, KC_MEH,         KC_HYPR,        KC_TRANSPARENT,

		KC_TRANSPARENT, KC_TRANSPARENT,                     KC_TRANSPARENT, KC_TRANSPARENT,
		KC_TRANSPARENT,                                     KC_TRANSPARENT,
		KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT,     KC_TRANSPARENT, KC_TRANSPARENT, KC_TRANSPARENT
	),
};

bool process_record_user( uint16_t keycode, keyrecord_t *record ) {
	dprintf(
		"keycode: %u, layer_state: %u, pressed: %u \n",
			// something wrong here? they don't seem to correspond to what i expect
			// maybe it's some kind of bitwise thing rather than bool on/off?
			// look at source to understand
		keycode,
		layer_state,
		record->event.pressed
	);

	switch (keycode) {
		case ST_MACRO_DASHES:
			if (record->event.pressed) {
				SEND_STRING( "-------------------------------" );
			}
			break;

		case ST_MACRO_CHECKBOX:
			if (record->event.pressed) {
				SEND_STRING( "- [ ] " );
			}
			break;

		case ST_MACRO_YAHOO:
			if (record->event.pressed) {
				SEND_STRING( "ian_wdunn@yahoo.com" );
			}
			break;
	}

	return true; // Continue processing the key event
}

uint32_t layer_state_set_user( uint32_t state ) {
	uint8_t layer = biton32( state );
	ergodox_board_led_off();
	ergodox_right_led_1_off();
	ergodox_right_led_2_off();
	ergodox_right_led_3_off();

	switch ( layer ) {
		case 1:
			ergodox_right_led_1_on();
		break;

		case 2:
			ergodox_right_led_2_on();
		break;

		case 3:
			ergodox_right_led_3_on();
		break;

		case 4:
			ergodox_right_led_1_on();
			ergodox_right_led_2_on();
		break;

		case 5:
			ergodox_right_led_1_on();
			ergodox_right_led_3_on();
		break;

		case 6:
			ergodox_right_led_2_on();
			ergodox_right_led_3_on();
		break;

		case 7:
			ergodox_right_led_1_on();
			ergodox_right_led_2_on();
			ergodox_right_led_3_on();
		break;
	}

	return state;
};
