# iandunn's Dotfiles

These are my config files for various programs. They implement my preferences, tweaks, and workflow optimizations.

> There are many like it, but this one is mine

Some things that might be useful to others are below, though.

* [bin\generate-config-files](./bin/generate-config-files.sh) - Concatenates public and private SSH config files into `~/.ssh/config`. This lets you track your foundational and non-sensitive configuation, without disclosing private information.
* [.gitconfig](./.gitconfig) - Configuration for commit signing, and per-repository overrides. Also has lots of aliases and general configuation.
* [docs](./docs) - Processes and best practices for development flow and basic project management.
* [git-hooks](./git-hooks/) - Boilerplate for good commit messages, and scripts for helping to write them. One example is how `pre-commit-msg-wordcamp` pulls previous commit messages to help follow repository conventions for the files that are being changed. There are also pre-commit and pre-push hooks to run linters etc.
* [ordinaryish](./keyboards/ergodox-ez/ordinaryish) - My custom keyboard layout for the [Ergodox EZ](https://ergodox-ez.com/) and [Colemak](https://colemak.com/) layout. Built with [QMK](https://qmk.fm/) firmware.
* [US No Dead Keys](./keyboards\US No Dead Keys) - A mac keyboard layout that disables dead keys, to prevent typos.
* [localwp\ssh-entry](./localwp/ssh-entry) - Customizing BASH prompt, $PATH, etc for [Local WP](https://localwp.com/) SSH sessions
* [.bash_prompt](./.bash_prompt) - Custom prompt with Git/SVN state, username, hostname, and current working directory. Adds extra whitespace to improve readability.
* [.bashrc](./.bashrc) - BASH helper functions like `findgrep` and `deploy`, SSH tab completion, deploy script wrapper, general configuation.
* [aliases](./aliases/) - BASH aliases

## Installation

In general, the original files from applications are symlinked to my custom files. In some cases, hard links need to be used for commands like `ssh` that don't follow symlinks.

1. `bash bin/install-homebrew-packages.sh`
1. `bash bin/install.sh` (symlinks all config files - overwrites existing)
1. `bash bin/generate-config-files.sh`
1. `bash bin/install-npm-packages.sh`
1. `bash bin/install.sh-wpcli-packages`
1. `bash bin/osx-apply-defaults.sh`
