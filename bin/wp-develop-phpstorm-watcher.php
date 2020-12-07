#!/usr/bin/php
<?php

/*
 * This copies `wordpress-develop` `src/` files to `build/`, as a backup for the buggy `npm run watch` script.
 * Core's build script often misses files or messes up, and it's very frustrating, and makes it difficult to get anything done.
 *
 * Setup:
 *
 * phpstorm > preferences > tools > file watchers
 * type: php
 * scope: open files
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

