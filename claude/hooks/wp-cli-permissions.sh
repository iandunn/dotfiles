#!/bin/bash

# This is a WP-CLI permissions hook script for Claude. It checks the command being run against a list of safe prefixes and allows it if it matches.
# Otherwise, it falls back to the normal permission prompt.

# ⚠️ This won't work if `mcp__local-wp__wp_cli` is enabled in your claude `permissions.allow` settings. Make sure it's not there.

# todo: do something similar for git, like `git show`

INPUT=$(cat)
ARGS=$(echo "$INPUT" | jq -r '.tool_input.args // empty')

SAFE_PREFIXES=(
	"--info"
	"--version"
	"akismet status"
	"cache flush"
	"cache get"
	"cache stats"
	"cap list"
	"cli info"
	"cli version"
	"comment count"
	"comment get"
	"comment list"
	"config get"
	"config list"
	"core check-update"
	"core update"
	"core update-db"
	"core version"
	"cron event list"
	"cron schedule list"
	"db check"
	"db size"
	"db tables"
	"embed provider list"
	"help"
	"jetpack module list"
	"jetpack status"
	"language is-installed"
	"language list"
	"maintenance-mode status"
	"media image-size"
	"menu list"
	"menu location list"
	"network meta get"
	"network meta list"
	"network meta pluck"
	"option get"
	"option list"
	"package list"
	"plugin active-on-sites"
	"plugin get"
	"plugin is-active"
	"plugin is-installed"
	"plugin list"
	"plugin update"
	"post get"
	"post list"
	"post meta get"
	"post meta list"
	"post-type get"
	"post-type list"
	"rewrite flush"
	"rewrite list"
	"role get"
	"role list"
	"sidebar list"
	"site list"
	"site url"
	"taxonomy get"
	"taxonomy list"
	"term get"
	"term list"
	"term meta get"
	"theme get"
	"theme is-active"
	"theme is-installed"
	"theme list"
	"theme update"
	"transient get"
	"user get"
	"user list"
	"user meta get"
	"widget list"
)

for prefix in "${SAFE_PREFIXES[@]}"; do
	if [[ "$ARGS" == "$prefix"* ]]; then
		echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"WP-CLI command matches safe prefix list"}}'
		exit 0
	fi
done

# Everything else falls through to the normal prompt
echo '{}'
exit 0
