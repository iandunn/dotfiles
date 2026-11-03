# Claude Code


## Permission hooks

The [hooks](./hooks/) cut down on nuisance approval prompts without opening security holes. They're `PreToolUse` hooks that auto-approve commands whose shape is safe and recoverable, prompt for anything they can't vouch for, and deny a few shapes outright.

* **[`bash_ast.py`](./hooks/bash_ast.py):** A shared parser that the other hooks use to read a Bash command. It runs `shfmt --to-json` and returns every simple command the line could run, including ones inside subshells, `$(...)`, heredocs, `bash -c` strings, and wrappers like `env`, `sudo`, and `xargs`. Hand-written quote scanners kept disagreeing with bash, and each disagreement was a way past a gate. You'll need `shfmt` installed.
* **[`dangerous-command-shapes.py`](./hooks/dangerous-command-shapes.py):** Denies chained commands (`;`, `&&`, `|`, etc), so that each approval covers exactly one command. It also prompts on commands that can't be read statically, like `$EDITOR foo` or `eval "$x"`, and denies destructive git forms however they're spelled.
* **[`file-command-permissions.py`](./hooks/file-command-permissions.py):** Auto-approves `git add`, `git commit`, `rm` of tracked files, and `cp`/`mv` that overwrite nothing untracked, inside a worktree under `.claude/worktrees/`. It also auto-approves read-only git subcommands anywhere. It checks the arguments rather than just the prefix, so `git fetch --upload-pack=<program>` or `git diff --output=<file>` still prompt.
* **[`command-allowlist-permissions.py`](./hooks/command-allowlist-permissions.py):** Auto-approves an allowlist of subcommands for a CLI, and prompts for everything else. It covers `wp`, `vip`, `localwp`, `gh`, and `glab` right now, but adding another CLI only takes a new entry in the `COMMANDS` table. It validates `wp db query` SQL so that reads pass and writes prompt, and it never auto-approves a production target.
* **[`safe-curl-check.py`](./hooks/safe-curl-check.py):** Auto-approves `curl` GET requests when every flag is on a known-safe list. Anything that could upload, write a file, or send credentials falls through to the normal prompt.
* **[`chrome-mcp-permissions.py`](./hooks/chrome-mcp-permissions.py):** Prompts before the Chrome DevTools MCP navigates to a non-local site. Once a site is approved, the agent can click and run scripts on it, so a prompt injection on the page could escalate to code execution.
* **[`desktop-app-permissions.py`](./hooks/desktop-app-permissions.py):** Denies writes into macOS app bundles, and prompts before a command launches a GUI app through `open`, `osascript`, etc.

There are tests for each hook in [`hooks/tests/`](./hooks/tests/).


## Other hooks

* **[`name-session.js`](./hooks/name-session.js):** Names a session after the ticket it's working on, and updates the name as the work changes. It looks the ticket up in Jira or Teamwork, so you'd need to swap in your own tracker. A manual `/rename` always wins.
* **[`inject-keyword-rules.py`](./hooks/inject-keyword-rules.py):** Adds a file from [`prompt-rules/`](./prompt-rules/) to the context when a prompt uses its keyword, like "hold" or "pplan". That keeps long, rarely-used instructions out of `CLAUDE.md`, so they don't take up space in every session.
* **[`inject-open-vscode-tabs.js`](./hooks/inject-open-vscode-tabs.js):** Tells Claude which tabs are open in VS Code, so "this file" or a fuzzy file name works in any terminal session, not just the one connected to the IDE. It reads state written by the [`claude-active-tab-informer`](../vscode/extensions/claude-active-tab-informer/) extension.
* **[`iterm-approval-dot.py`](./hooks/iterm-approval-dot.py):** Turns the iTerm2 tab's status dot red while Claude is waiting on a permission prompt. iTerm2 uses the same blue for that as it does for new output, so it's easy to miss a session that's blocked.


## Skills and commands

* **[`/resumebody`](./commands/resumebody.md):** Finds a past session by what was said in it. The built-in `/resume` picker only matches the title, branch, and PR, so a session that changed topics can be hard to find. It uses [`bin/claude-session-search.sh`](./bin/claude-session-search.sh), which only matches text that you typed, rather than tool output or pasted files.
* **[`blocked-site-browser`](./skills/blocked-site-browser/SKILL.md):** Rules for a second Chrome DevTools MCP server that reads pages from sites that block `curl` and WebFetch, like stores and review sites. The server overrides the headless user agent and strips the automation flags that those sites detect. [`chrome-mcp-permissions.py`](./hooks/chrome-mcp-permissions.py) auto-approves the sites listed under `blockedSiteBrowser.sites` in `settings.json` and prompts for any others, and the skill tells the agent to treat page content as untrusted data.
* **[`reading-pdfs`](./skills/reading-pdfs/SKILL.md):** Extracts PDF text with poppler, instead of letting the Read tool render every page as an image. That uses a small fraction of the tokens.
* **[`chrome-mcp-setup`](./skills/chrome-mcp-setup/SKILL.md):** Runs the Chrome DevTools MCP headless with a throwaway profile for each session, so parallel sessions don't lock each other out, and the agent never touches your real browser profile. [`bin/close-isolated-chrome.sh`](./bin/close-isolated-chrome.sh) closes only the current session's Chrome, so the agent never needs `kill` permission.
* **[`parallel-plan-worktrees`](./skills/parallel-plan-worktrees/SKILL.md):** Has the agent implement in its own git worktree, then patch the result into the main checkout when you say `go`. That lets several sessions work in the same repo without stepping on each other's changes.


## Instructions and status line

* **[`CLAUDE.md`](./CLAUDE.md):** My global instructions. They're specific to me, but some sections are easy to adapt. "Response Style" keeps replies short and tells the agent not to narrate its process. "One topic at a time" keeps a session from fanning out into a dozen open threads, by parking new topics in a file. "Hold / Resume" lets you send several prompts without getting a reply to each one.
* **[`rules/`](./rules/):** Rules for writing code and prose, running commands, and debugging. `writing-for-humans.md` is probably the most reusable one, but it refers to a `writing-in-my-voice` skill that isn't in this repo, so you'd need to remove that reference.
* **[`ccstatusline-reset-alert.js`](./ccstatusline-reset-alert.js):** A [ccstatusline](https://github.com/sirmalloc/ccstatusline) widget that only shows when your rate limit resets once you've used most of it, so it doesn't clutter the status line the rest of the time.
