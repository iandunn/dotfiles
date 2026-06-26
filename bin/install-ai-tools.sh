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
# TODO need to make sure don't overwrite any uncommited changes in branchs?
# maybe first check if on main branch and clean. if so then install
# if not then skip this and warn at the end
section "10up Agent Skills"
# npx @10up/agent-skills --global
# rm -rf ~/.claude/skills/10up-update-plugins
# ln -s ~/.claude/skills/10up-update-plugins ~/vho
# install from source rather than package ? symlink all individual ones to git repo? but then how to know about new ones?
# just let it be overridden and manualy symlink when wanna work on one?

npx @10up/agent-skills --global

# TODO agent skills is part of relay now? so need to uninstall that? but then also fork relay to use your update-plugins skill?
section "10up Relay Plugins"
claude plugin marketplace add 10up/relay-plugins
claude plugin install relay-eng@relay-plugins

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

section "Security Guidance"
claude plugin install security-guidance@claude-plugins-official

# todo add localwp mcp?


printf "\n\n⚠️ 10up agent skills not installed, see above"
