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
section "10up Agent Skills"
npx @10up/agent-skills --global

section "10up Spark Plugins"
claude plugin marketplace add 10up/spark-plugins
claude plugin install spark-eng@10up-spark-plugins

section "Daryll Doc Skills"
claude plugin marketplace add darylldoyle/docs-skills
claude plugin install docs-skills@docs-skills-marketplace

section "Superpowers"
claude plugin install superpowers@claude-plugins-official

section "Anthropic frontend-design plugin"
claude plugin install frontend-design@claude-plugins-official

printf "\n\n⚠️ 10up agent skills not installed, see above"
printf "\n ⚠️see errors for spark plugins"
