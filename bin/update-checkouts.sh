#!/bin/bash

# Update checkouts that I rarely need to manually review
# This is intended to scheduled to run automatically

SVN=(
	/Users/ian/vhosts/meta.svn.wordpress.org
	/Users/ian/vhosts/vvv-personal/www/wordcamp.dev/public_html/wordpress
)

for i in "${SVN[@]}"
do :
	svn up $i
done
