<?php
/**
 * Common functionality for all local sandbox sites.
 *
 * Symlink this into mu-plugins.
 *
 * @package PHPCS_Is_Annoying
 */

namespace iandunn\Sandbox_Common;

define( 'TENUPSSO_DISABLE', true );


// Automatically install the latest RC
add_filter( 'allow_dev_auto_core_updates', '__return_true' );
add_filter( 'allow_minor_auto_core_updates', '__return_true' );
add_filter( 'allow_major_auto_core_updates', '__return_true' );
add_filter( 'auto_update_plugin', '__return_false' );
add_filter( 'auto_update_theme', '__return_false' );

// Jetpack prevents me from logging in w/ "password" as my password.
// This doesn't make sense in a local env
// https://github.com/Automattic/jetpack/issues/45145
add_filter( 'jetpack_account_protection_user_requires_protection', '__return_false' );


add_filter(	'auth_cookie_expiration', __NAMESPACE__ . '\stay_logged_in', 1001, 3 );// after 10up-experience
add_filter( 'vip_show_non_prod_bar', '__return_false' );
add_action( 'admin_init', __NAMESPACE__ . '\register_admin_screen_items_callback' );
add_action( 'admin_head', __NAMESPACE__ . '\admin_bar_flex_css' );
add_action( 'wp_head', __NAMESPACE__ . '\admin_bar_flex_css' );
add_action( 'admin_footer', __NAMESPACE__ . '\admin_bar_sync_margin_js' );
add_action( 'wp_footer', __NAMESPACE__ . '\admin_bar_sync_margin_js' );


/**
 * Register set_minimum_number_admin_screen_items to all admin screens.
 *
 * It's necessary to manually add it for each screen name because WP_Screen::render_per_page_options
 * doesn't have a generic filter.
 */
function register_admin_screen_items_callback() {
	$core_screens = [
		'edit_comments',
		'upload',
		'users',
		'plugins',
		'themes',
		'edit_tags',
		'export_personal_data_requests',
		'remove_personal_data_requests',
		'sites_network',
		'users_network',
		'site_users_network',
		'plugins_network',
		'themes_network',
		'site_themes_network',
		'comments',
		'edit_categories',
	];

	$post_types        = get_post_types( [], 'names' );
	$taxonomies        = get_taxonomies( [], 'names' );
	$post_type_screens = array_map( fn( $post_type ) => "edit_{$post_type}", $post_types );
	$taxonomy_screens  = array_map( fn( $taxonomy ) => "edit_{$taxonomy}", $taxonomies );
	$screen_hooks      = array_merge( $core_screens, $post_type_screens, $taxonomy_screens );

	foreach ( $screen_hooks as $hook ) {
		add_filter( "get_user_option_{$hook}_per_page", __NAMESPACE__ . '\set_minimum_number_admin_screen_items' );
	}
}

/**
 * Admin screens should always show at least 120 items on each page.
 */
function set_minimum_number_admin_screen_items( $result ) {
	return max( 120, (int) $result );
}

// It's pointless to enforce login expiration on a local sandbox site.
function stay_logged_in( $expiration, $user_id, $remember ) {
	return 5 * YEAR_IN_SECONDS;
}

function admin_bar_flex_css() {
	if ( ! is_admin_bar_showing() ) {
		return;
	}
	?>
	<style>
	@media screen and (min-width: 757px) {
		#wpadminbar {
			height: auto !important;
			min-height: 32px;
		}
	}
	@media screen and (min-width: 783px) {
		/* Core hardcodes top:32px here; override with our dynamic variable */
		.interface-interface-skeleton {
			top: var(--wp-admin--admin-bar--height, 32px) !important;
		}
	}
	</style>
	<?php
}

function admin_bar_sync_margin_js() {
	if ( ! is_admin_bar_showing() ) {
		return;
	}
	?>
	<script>
	(function() {
		var pending = false;

		function syncAdminBarMargin() {
			if ( pending ) { return; }
			pending = true;
			requestAnimationFrame( function() {
				pending = false;
				var bar = document.getElementById( 'wpadminbar' );
				if ( ! bar ) { return; }
				var heightPx = bar.offsetHeight + 'px';
				document.documentElement.style.setProperty( 'margin-top', heightPx, 'important' );
				document.documentElement.style.setProperty( '--wp-admin--admin-bar--height', heightPx );
			} );
		}

		syncAdminBarMargin();
		window.addEventListener( 'resize', syncAdminBarMargin );

		var bar = document.getElementById( 'wpadminbar' );
		if ( bar && window.ResizeObserver ) {
			new ResizeObserver( syncAdminBarMargin ).observe( bar );
		}

		// Catches Gutenberg fullscreen mode toggle (adds/removes is-fullscreen-mode on body)
		new MutationObserver( syncAdminBarMargin ).observe( document.body, {
			attributes: true,
			attributeFilter: [ 'class' ],
		} );
	})();
	</script>
	<?php
}
