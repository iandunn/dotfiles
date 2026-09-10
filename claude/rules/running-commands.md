# Running Commands

- Be aware that I often have aliases for commands, like `rm` is actually `rm -i`. You'll sometimes need to prefix those with `command` to avoid that. Don't do that generally though because permission rules match the literal command string, so `command ls` doesn't match `Bash(ls *)` and would need a duplicate `settings.json` rule for every command.

- Use `rg` and `fd` as faster alternatives to recursive `grep` and `find`, respectively.
- My shell aliases `rg` to `rg --fixed-strings --ignore-case --hidden --line-number`, so every regex is matched literally: `rg 'a|b'` searches for the three-character string `a|b`, finds nothing, and exits 1 -- indistinguishable from a genuine "no matches". Use `command rg` whenever the pattern has regex syntax (anchors, `|`, character classes, quantifiers), or use `grep -E`. Never treat an empty bare-`rg` result on a regex pattern as evidence that something doesn't exist -- re-run it with `command rg` first.

- Use `jq` for handling json instead of calling python just to parse JSON.

- Paths in commands you hand me to run -- or mention in prose -- must be absolute; your cwd isn't mine, and `EnterWorktree` moves yours without moving mine. When a path-based command fails, show me `pwd` rather than guessing a different prefix.

- Don't run things like `npx jest` when you can run `npm run test` instead.

- `cr` and `nr` are my aliases for `composer run` and `npm run`

- Name VIP-CLI targets with a single leading `@org.env` token: `vip @foo.staging wp post list`. That's the only spelling `hooks/command-allowlist-permissions.py` accepts -- it hard-denies `-e`/`--env`/`-a`/`--app` flags, a second `@` token, or an `@` token after the subcommand, because two target spellings on one line would leave it guessing which one VIP honors. It also denies `wp`/`vip` binaries at paths outside its `BINARY_ALLOWED_PATHS`; if you hit that deny legitimately, tell me instead of rewording the command.

- Never wrap a command in a subshell or group -- `( a && echo yes || echo no )`, `{ ... }` -- just to make its exit code readable; that introduces nuisance approval prompts. Run the bare commands and use exit codes instead.

- Send one plain command per tool call. Chaining with `;`, `&&`, or a pipe leaves the permission parser unable to decompose the line, so the hooks refuse it outright rather than prompting: an approval covers the whole command line, and splitting it is something you can always do yourself. Run linters, test suites, and anything else bare, and read the whole output.

- A trailing `| head`, `| tail`, or `| wc` is the exception, because those three can only trim what the command already printed. So is a redirect to `/dev/null` or a file descriptor (`2>&1`, `2>/dev/null`). Everything else in a pipeline -- `grep`, `sed`, `sort`, `jq`, `tee`, `xargs` -- makes the line a chain again. A redirect to a real file still prompts rather than being refused, since there's no split that avoids it.

- Run `rm`, `mv`, `cp`, `git add`, `git commit`, and `git worktree remove` bare -- one per tool call, subject to the same two exceptions. If you want output trimmed beyond what `head`/`tail`/`wc` give you, run the command and read the result.

- Quoted arguments are safe, so a multi-paragraph `git commit -m` message auto-approves inside a worktree; its newlines are part of one quoted string. Write commit messages in single quotes when they contain backticks, which the same hook still refuses inside double quotes because bash expands them there. An apostrophe inside a single-quoted message is spelled `'\''`.

- Don't `cd` into a directory and then run `git` in the same command; use `git -C <path> <read-only command>`, or a separate `cd` call followed by the git call. Never put more than one `cd` in a single command. Both shapes are hardcoded permission prompts.


## Commits

<!--
- Never pass a commit message through the shell -- not `-m "..."`, and not a `"$(cat <<'EOF' ... EOF)"` heredoc. Write it to the project's `.claude/tmp/commit-msg.txt` with the `Write` tool, then `git commit -F .claude/tmp/commit-msg.txt`. Reuse that same filename each time so they don't pile up, and leave it in place afterward. This prevents unintended hard wraps being introduced by the terminal width.
todo this may not be necessary now that using claude fullscreen TUI  -->

- Commit message subject lines should be at most 70 characters. Body lines never hard wrap. Markdown emphasis and indentation are fine where they are *deliberate* -- a bullet list, a code sample, a nested item under a bullet. What I don't want is emphasis or indentation that showed up as a side effect of something reflowing the text. Prefix commits with the area/feature effected, not `feat`, `chore`, `fix`, etc.

- Repositories under `~/local-sites/10up/` follow the Fueled convention, so their commit subjects are lowercase throughout, prefix and first word alike: `jobs: register JobCategory in JobHeaderTest`. Everywhere else the subject is a Title-cased area prefix and a sentence-case imperative: `Helpers: Restore switched blog when returning early`.

- Never put the current ticket/issue or PR number in a commit subject/body. Never put the ticket/issue number in a PR title. It's fine to put the ticket in a PR body. It's fine for commits and PRs to reference something that happenend in the past. For example, if a commit is part of PR `#200`, and `#200` which fixes issue `#100`, then the commit shouldn't reference `#100` or `#200`. If commit `c0a152e` from PR `#50` introduced a bug that is being fixed by the current commit, then `c0a152e` and `#50` can be mentioned. The exception to that is that a commit without a PR that's being merged directly to the main branch is allowed to reference the issue that is being fixed by the commit. That's because there's no PR to reference/close the issue.

- `git commit` and `git mv` need `dangerouslyDisableSandbox: true` on the first attempt, not as a retry after a failure. My commits are SSH-signed, and `ssh-keygen` can't reach the agent socket from inside the sandbox, so it dies with "Couldn't get agent socket"; `git mv` fails its rename syscall with "Operation not permitted". Both are known and expected, so treating them as a sandbox-caused failure you have to discover first just wastes a round trip. This is the same sanctioned-exception shape as the Chrome close script -- it is not a workaround, and it does not extend to any other command.

- The problem that the commit is fixing and the solution that the commit implements should be in separate paragraphs.
