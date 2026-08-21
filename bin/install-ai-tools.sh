# ⚠️ When adding a new marketplace, you need to add `autoupdate:true` in `claude/settings.json`

source ~/dotfiles/bash/functions.sh

section "Claude Code"
npm update -g @anthropic-ai/claude-code


section "LocalWP Agent Tools"

REPO_SLUG=localwp-agent-tools
LOCALWP_AGENT_TOOLS_DIR="$HOME/vhosts/tools/$REPO_SLUG"
LOCALWP_ADDONS_DIR="$HOME/Library/Application Support/Local/addons"

if [ -d "$LOCALWP_AGENT_TOOLS_DIR" ]; then
    cd $LOCALWP_AGENT_TOOLS_DIR
	git reset --hard main
	git -C "$LOCALWP_AGENT_TOOLS_DIR" pull
else
	gh repo clone 10up/$REPO_SLUG ~/vhosts/tools/$REPO_SLUG
fi

cd ~/vhosts/tools/$REPO_SLUG
npm install --legacy-peer-deps
npm run build

printf "\n"

cp -r . "$LOCALWP_ADDONS_DIR/$REPO_SLUG/"
cd "$LOCALWP_ADDONS_DIR/$REPO_SLUG/"
npm install --production --ignore-scripts

# then have to manually activate
# then manually add to every site?
# maybe can script those last steps?
# already manually to everything though, but maybe wanna script it to auto update future sites?
# just make sure that it doesn't overwrite existing project-specific files




#
# WP Agent Skills
#
section "WP Agent Skills"

SKILLS_DIR="$HOME/vhosts/tools/wp-agent-skills"

if [ -d "$SKILLS_DIR" ]; then
    git -C "$SKILLS_DIR" pull
else
    git clone https://github.com/WordPress/agent-skills.git "$SKILLS_DIR"
fi

cd "$SKILLS_DIR"
node shared/scripts/skillpack-build.mjs --clean

# Need to periodically update this list as thing evolve. Don't install ones that 10up has a fork of though.
node shared/scripts/skillpack-install.mjs --global --skills=wp-playground,wp-abilities-api,wp-wpcli-and-ops,wp-phpstan




#
# Misc
#
# Installed from a local clone instead of GitHub so that local customizations to the
# bundled skills stay in effect. `$RELAY_BRANCH` is `main` plus those customizations, and
# each feature lives on its own `feat/` branch for contributing back upstream.
section "10up Relay Plugins"

RELAY_PLUGINS_DIR="$HOME/vhosts/tools/relay-plugins"
RELAY_BRANCH="local-main"

if [ -d "$RELAY_PLUGINS_DIR" ]; then
	if [ -n "$(git -C "$RELAY_PLUGINS_DIR" status --porcelain)" ]; then
		printf "\n⚠️ %s has uncommitted changes, skipping its update.\n" "$RELAY_PLUGINS_DIR"
	else
		git -C "$RELAY_PLUGINS_DIR" fetch origin
		git -C "$RELAY_PLUGINS_DIR" checkout "$RELAY_BRANCH"

		if ! git -C "$RELAY_PLUGINS_DIR" merge origin/main; then
			git -C "$RELAY_PLUGINS_DIR" merge --abort
			printf "\n⚠️ Merging origin/main into %s conflicted, so the merge was aborted and nothing was updated. Resolve it by hand, then re-run.\n" "$RELAY_BRANCH"
		else
			printf "\n✅ Merged origin/main into %s successfully.\n" "$RELAY_BRANCH"
		fi
	fi
else
	# A fresh clone has no customizations — they only exist on branches in the previous
	# clone, and are not pushed to the shared upstream. Warn loudly rather than installing
	# vanilla relay as though it were the customized build.
	git clone git@github.com:10up/relay-plugins.git "$RELAY_PLUGINS_DIR"
	git -C "$RELAY_PLUGINS_DIR" checkout -b "$RELAY_BRANCH"
	printf "\n⚠️ Fresh clone, so %s is vanilla main. Re-apply the local skill customizations before relying on them.\n" "$RELAY_BRANCH"
fi

claude plugin marketplace add "$RELAY_PLUGINS_DIR"
claude plugin install relay-eng@relay-plugins
claude plugin install relay-pjm@relay-plugins
claude plugin install relay-core@relay-plugins

section "Daryll Doc Skills"
claude plugin marketplace add darylldoyle/docs-skills
claude plugin install docs-skills@docs-skills-marketplace

section "Superpowers"
claude plugin install superpowers@claude-plugins-official

# todo need to uninstall before updating?  https://github.com/chromeDevTools/chrome-devtools-mcp/ says
# [!NOTE] If you already had Chrome DevTools MCP installed previously for Claude Code, make sure to remove it first from your installation and configuration files.
section "Chrome Dev Tools MCP"
claude plugin marketplace add ChromeDevTools/chrome-devtools-mcp
claude plugin install chrome-devtools-mcp

section "Anthropic frontend-design plugin"
claude plugin install frontend-design@claude-plugins-official

section "Modern Web Guidance"
claude plugin marketplace add GoogleChrome/modern-web-guidance
claude plugin install modern-web-guidance@googlechrome

section "Security Guidance / Claude Security"
claude plugin install security-guidance@claude-plugins-official
claude plugin install claude-security@claude-plugins-official

# todo add localwp mcp?


# `claude plugin update` only takes one plugin at a time, so loop over everything that's installed
# rather than listing them individually above. `plugin update` resolves against the cached
# marketplace manifests, so those have to be refreshed first or there's nothing new to find.
section "Update All Claude Plugins"
claude plugin marketplace update

claude plugin list --json | jq -r '.[] | "\(.id) \(.scope)"' |
	while read -r plugin_id plugin_scope; do
		claude plugin update "$plugin_id" --scope "$plugin_scope"
	done
