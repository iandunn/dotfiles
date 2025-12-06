// Copyright 2021 Ian Dunn (@iandunn)
// SPDX-License-Identifier: GPL-2.0-or-later
#include QMK_KEYBOARD_H
#include "version.h"

#ifdef CONSOLE_ENABLE
	#include <print.h>
#endif

// This has to come before `keycodes` and `process_record_user`.
enum custom_keycodes {
	RGB_SLD = SAFE_RANGE,
	ST_MACRO_NULL, // Unused, but must exist to avoid weird conflict between macros and one-shot keys.
	ST_MACRO_DASHES,
	ST_MACRO_CHECKBOX,
	ST_MACRO_YAHOO
};

static bool key_lock_waiting   = false;
static bool key_lock_active    = false;
static uint16_t locked_keycode = KC_NO;

// Check if a keycode can be locked (alphanumeric, symbols, and arrow keys only)
bool is_lockable_key( uint16_t keycode ) {
	if ( keycode >= KC_A && keycode <= KC_Z ) {
		return true;
	}

	if ( keycode >= KC_1 && keycode <= KC_0 ) {
		return true;
	}

	switch ( keycode ) {
		case KC_MINUS:
		case KC_EQUAL:
		case KC_LEFT_BRACKET:
		case KC_RIGHT_BRACKET:
		case KC_BACKSLASH:
		case KC_SEMICOLON:
		case KC_QUOTE:
		case KC_GRAVE:
		case KC_COMMA:
		case KC_DOT:
		case KC_SLASH:
		case KC_UP:
		case KC_DOWN:
		case KC_LEFT:
		case KC_RIGHT:
			return true;
	}

	return false;
}

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
	// Base Layer
	[0] = LAYOUT_ergodox_pretty(
		KC_ESCAPE,       KC_1, KC_2, KC_3, KC_4, KC_5, KC_6,                     _______,          KC_7, KC_8, KC_9, KC_0, KC_MINUS,     KC_EQUAL,
		KC_GRAVE,        KC_Q, KC_W, KC_F, KC_P, KC_G,       KC_LCBR,            KC_RCBR,          KC_J, KC_L, KC_U, KC_Y, KC_SEMICOLON, KC_BACKSLASH,
		KC_TAB,          KC_A, KC_R, KC_S, KC_T, KC_D,                                             KC_H, KC_N, KC_E, KC_I, KC_O,         KC_QUOTE,
		OSM( MOD_LSFT ), KC_Z, KC_X, KC_C, KC_V, KC_B,       KC_LEFT_BRACKET,    KC_RIGHT_BRACKET, KC_K, KC_M, KC_COMMA, KC_DOT, KC_SLASH, OSM( MOD_RSFT ),
		_______, OSM( MOD_LCTL ), _______, OSM( MOD_LALT ), OSM( MOD_LGUI ),    OSM( MOD_RGUI ), OSM( MOD_RALT ), _______, OSM( MOD_RCTL ), _______,

					 OSL(2), KC_PAGE_UP,       KC_LEFT, KC_RIGHT,
					       KC_PAGE_DOWN,       KC_UP,
		KC_BACKSPACE, OSL(1), KC_DELETE,       KC_DOWN, KC_ENTER, KC_SPACE
	),

	// Navigation, macros, misc commonly used
	[1] = LAYOUT_ergodox_pretty(
		_______, KC_F1,   KC_F2,      MS_BTN3, _______, _______, _______,            _______, KC_PAGE_UP, MS_ACL0, MS_ACL1, ST_MACRO_YAHOO, ST_MACRO_DASHES, ST_MACRO_CHECKBOX,
		_______, _______, MS_BTN1, MS_UP,   MS_BTN2, _______, _______,         _______, MS_WHLU, RGUI(RSFT(KC_LEFT_BRACKET)), KC_UP, RGUI(RSFT(KC_RIGHT_BRACKET)), KC_HOME, _______,
		_______, _______, MS_LEFT, MS_DOWN, MS_RGHT, _______,                          MS_WHLD, KC_LEFT, KC_DOWN, KC_RIGHT, KC_END, _______,
		_______, _______, _______, _______, _______, _______, _______,                  _______, KC_PAGE_DOWN, RGUI(KC_LEFT_BRACKET), _______, RGUI(KC_RIGHT_BRACKET), _______, _______,
		_______, _______, _______, _______, _______, _______, _______,                  _______, _______, _______,

				 _______, _______,     _______, _______,
						  _______,     _______,
		_______, _______, _______,     _______, _______, _______
	),

	// Misc rarely used
	[2] = LAYOUT_ergodox_pretty(
		_______, _______, _______, _______, _______, _______, _______,                                                      _______, _______, DT_PRNT, DT_UP, DT_DOWN, _______, _______,
		_______, _______, _______, _______, _______, _______, _______,                                                      _______, _______, KC_BRIGHTNESS_UP, RSFT(RALT(KC_AUDIO_VOL_UP)), _______, _______, _______,
		_______, KC_MEDIA_PREV_TRACK, KC_MEDIA_REWIND, KC_MEDIA_PLAY_PAUSE, KC_MEDIA_FAST_FORWARD, KC_MEDIA_NEXT_TRACK,     _______, KC_BRIGHTNESS_DOWN, RSFT(RALT(KC_AUDIO_VOL_DOWN)), _______, _______, _______,
		_______, _______, _______, _______, _______, _______, WEBUSB_PAIR,                                                  WEBUSB_PAIR, _______, _______, KC_AUDIO_MUTE, _______, _______, _______,
		_______, _______, _______, _______, _______,                                                                        _______, _______, _______, _______, _______,

				 _______, _______,     _______, _______,
						  _______,     _______,
		_______, _______, _______,     _______, _______, _______
	),
};

/*
 * Custom logic for keydown/up events.
 *
 * This gets called on every key press, and every release.
 * Returning `true` allows normal processing to continue, `false` stops it.
 */
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

	switch ( keycode ) {
		// Disable the `OSM(cmd) + enter` sequence, because it often causes me to accidentally submit Slack/GitHub/etc messages.
		// All other OSM combinations should remain active.
		case KC_ENTER:
			if ( record->event.pressed ) {
				if ( get_oneshot_mods() == MOD_LGUI ) {
					return false; // Don't continue processing
				}
			}
			break;

		// Macros
		case ST_MACRO_DASHES:
			if ( record->event.pressed ) {
				SEND_STRING( "-------------------------------" );
			}
			break;

		case ST_MACRO_CHECKBOX:
			if ( record->event.pressed ) {
				SEND_STRING( "- [ ] " );
			}
			break;

		case ST_MACRO_YAHOO:
			if ( record->event.pressed ) {
				SEND_STRING( "ian_dunn@yahoo.com" );
			}
			break;

		case KC_BACKSPACE:
			if ( record->event.pressed && layer_state_is(1) ) {
				key_lock_waiting = true;

				// Backspace is just triggering the lock key, it shouldn't be sent.
				return false;
			}
			break;
	}

	if ( key_lock_waiting ) {
		if ( record->event.pressed ) {
			if ( is_lockable_key( keycode ) ) {
				key_lock_waiting = false;
				key_lock_active  = true;
				locked_keycode   = keycode;

				register_code( keycode );

				return false;

			} else {
				key_lock_waiting = false;
			}
		}

		// Ignore key releases while waiting
		return false;
	}

	if ( key_lock_active ) {
		if ( keycode == locked_keycode ) {
			// Ignore all events for the locked key itself
			return false;
		}

		if ( record->event.pressed ) {
			// Release the locked key when any other key is pressed
			unregister_code( locked_keycode );

			key_lock_active = false;
			locked_keycode  = KC_NO;
		}
	}

	return true;
}

// Layer indicator lights
layer_state_t layer_state_set_user( layer_state_t state ) {
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
