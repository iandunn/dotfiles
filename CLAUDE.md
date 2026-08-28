# Dotfiles

Personal config files for bash, git, Claude, WordPress tooling, etc. Files here are
symlinked (or hard-linked, for tools like `ssh` that don't follow symlinks) into `$HOME`
by `bin/install.sh`. Editing a file here changes the live config immediately via the symlink.

Public repo, but some files are intentionally `.gitignore`d because they're private.

## Two different CLAUDE.md files (don't confuse them)
- `claude/CLAUDE.md` — tracked; symlinked to `~/CLAUDE.md`. Global user/agent instructions
  (role, stack, response style) applied in every session everywhere.
- `CLAUDE.md` (this root file) — gitignored; project instructions applied only when working
  inside this dotfiles repo.

## Layout
- `bash/` — `.bashrc`/`.bash_profile`/aliases/functions, Oh My Posh theme (`iandunn.omp.yml`)
- `git/` — `.gitconfig` + split configs (`.aliases`, `.delta`, `.signing`, per-org `.10up`/`.cadmv`), hooks
- `claude/` — Claude Code config: `settings.json`, `hooks/`, `bin/`, `skills/` (symlinked to `~/.claude/*`)
- `bin/` — install/setup scripts (`install.sh` does the symlinking; `install-*.sh` for brew/npm/composer/wpcli/ai-tools)
- `wordpress/`, `localwp/`, `phpcs/`, `phpmd/`, `php/`, `wp-cli.yml`, `.eslintrc.js` — WP/PHP dev tooling
- `keyboards/`, `iterm2/`, `nginx/`, `firefox/`, `.config/` — misc app configs
- `docs/` — dev-flow and project-management notes

## Claude hooks
Live in `claude/hooks/` (Python + a few shell/JS), symlinked into `~/.claude/hooks`. They gate
tool permissions (Chrome MCP, WP-CLI, worktrees, curl, textutil, dangerous command shapes). Create new
hooks here, then symlink. Tests are in `claude/hooks/tests/`.
