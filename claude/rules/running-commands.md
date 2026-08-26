# Running Commands

- Be aware that I often have aliases for commands, like `rm` is actually `rm -i`. You'll sometimes need to prefix those with `command` to avoid that. Don't do that generally though because permission rules match the literal command string, so `command ls` doesn't match `Bash(ls *)` and would need a duplicate `settings.json` rule for every command.

- Use `rg` and `fd` as faster alternatives to recursive `grep` and `find`, respectively.
- My shell aliases `rg` to `rg --fixed-strings --ignore-case --hidden --line-number`, so every regex is matched literally: `rg 'a|b'` searches for the three-character string `a|b`, finds nothing, and exits 1 -- indistinguishable from a genuine "no matches". Use `command rg` whenever the pattern has regex syntax (anchors, `|`, character classes, quantifiers), or use `grep -E`. Never treat an empty bare-`rg` result on a regex pattern as evidence that something doesn't exist -- re-run it with `command rg` first.

- Use `jq` for handling json instead of calling python just to parse JSON.

- Paths in commands you hand me to run -- or mention in prose -- must be absolute; your cwd isn't mine, and `EnterWorktree` moves yours without moving mine. When a path-based command fails, show me `pwd` rather than guessing a different prefix.

- Don't run things like `npx jest` when you can run `npm run test` instead.

- `cr` and `nr` are my aliases for `composer run` and `npm run`

- Never wrap a command in a subshell or group -- `( a && echo yes || echo no )`, `{ ... }` -- just to make its exit code readable; that introduces nuisance approval prompts. Run the bare commands and use exit codes instead.

- Send one plain command per tool call. Chaining with `;` or `&&`, piping into `tail`/`head`, and `2>&1` redirects all leave the permission parser unable to decompose the line, so it prompts for confirmation rather than auto-approving commands it would otherwise recognise. Run linters, test suites, and anything else bare, and read the whole output.

- Run `rm`, `mv`, `cp`, `git add`, `git commit`, and `git worktree remove` bare -- one per tool call, with no `&&`, `;`, pipes, or redirects. `hooks/worktree-command-permissions.py` refuses to reason about shell operators, because an approval covers the whole command line, so chaining or piping one of these turns an auto-approval back into a prompt. If you want trimmed output, run the command and read the result.

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
