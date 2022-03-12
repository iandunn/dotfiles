#!/usr/bin/php
<?php

/*
 * This copies `wordpress-develop` `src/` files to `build/`, as a backup for the buggy `npm run watch` script.
 * Core's build script often misses files or messes up, and it ruins the devex.
 *
 * See https://core.trac.wordpress.org/ticket/51960
 *
 * Setup:
 *
 * phpstorm > preferences > tools > file watchers
 * type: php
 * scope: open files
	* ugh wait, this doesn't handle things like `git checkout {branch}`, so needs to be all src files?
 * arguments: $FilePath$
 * advanced:
 * 	uncheck `auto save...`
 * 	check both `trigger...`
 * show console: `always` to test/troubleshoot, `on error` once working
 */

$source      = $argv[1];
$destination = str_replace( '/src/', '/build/', $source );

exec( "cp $source $destination", $output, $status );

exit( $status );

