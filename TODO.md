# TODO

## Quick Wins



## High Priority

- **Run `/doctor` against `claude/CLAUDE.md`.** It proposes trims -- cuts content derivable from the codebase, keeps pitfalls and conventions. Documented for a checked-in `CLAUDE.md`, and this one is user-scope that happens to live in a tracked repo, so it may not target it. One run will tell.

## Medium Priority

- **Fix the symlink nesting bug in `bin/install.sh`.** The two `# todo ^ keeps nesting` comments (`.config/gh`, `localwp/ssh-entry`) are caused by `ln -sf`: when the destination is already a symlink to a directory, `-f` follows it and creates the new link *inside* it, so every re-run nests one level deeper. The fix is `-sfn` -- `-n` replaces the symlink itself instead of dereferencing it. The claude links added on 2026-07-31 already use `-sfn`; these two predate it.

## Low Priority

- **Decide whether more of `claude/CLAUDE.md` should move to `claude/rules/`.** Currently only conventions moved. The interaction protocol and all restrictions stayed because `CLAUDE.md` is re-injected after `/compact` and the docs make no such promise for rules. If that turns out to hold for rules too, the remaining split is arbitrary and more can move.
