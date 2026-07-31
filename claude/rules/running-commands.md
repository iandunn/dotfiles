# Running Commands

- Be aware that I often have aliases for commands, like `rm` is actually `rm -i`. You'll sometimes need to prefix those with `command` to avoid that. Don't do that generally though because permission rules match the literal command string, so `command ls` doesn't match `Bash(ls *)` and would need a duplicate `settings.json` rule for every command.

- Use `rg` and `fd` as faster alternatives to recursive `grep` and `find`, respectively. `rg` searches recursively with no flag, so recursive search with line numbers is just `rg -n 'pattern' path/`. Never run `rg -r` because that takes replacement text and rewrites the matches it prints, so the output shows something other than what's in the file.

- Use `jq` for handling json instead of calling python just to parse JSON.

- Paths in commands you hand me to run -- or mention in prose -- must be absolute; your cwd isn't mine, and `EnterWorktree` moves yours without moving mine. When a path-based command fails, show me `pwd` rather than guessing a different prefix.

- Don't run things like `npx jest` when you can run `npm run test` instead.

- `cr` and `nr` are my aliases for `composer run` and `npm run`

- Never wrap a command in a subshell or group -- `( a && echo yes || echo no )`, `{ ... }` -- just to make its exit code readable; that introduces nuisance approval prompts. Run the bare commands and use exit codes instead.

- Don't `cd` into a directory and then run `git` in the same command; use `git -C <path> <read-only command>`, or a separate `cd` call followed by the git call. Never put more than one `cd` in a single command. Both shapes are hardcoded permission prompts.

- `git commit` and `git mv` need `dangerouslyDisableSandbox: true` on the first attempt, not as a retry after a failure. My commits are SSH-signed, and `ssh-keygen` can't reach the agent socket from inside the sandbox, so it dies with "Couldn't get agent socket"; `git mv` fails its rename syscall with "Operation not permitted". Both are known and expected, so treating them as a sandbox-caused failure you have to discover first just wastes a round trip. This is the same sanctioned-exception shape as the Chrome close script -- it is not a workaround, and it does not extend to any other command.
