source ~/dotfiles/bash/functions.sh

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

section "Daryll Doc Skills"
claude plugin marketplace add darylldoyle/docs-skills
claude plugin install docs-skills@docs-skills-marketplace
