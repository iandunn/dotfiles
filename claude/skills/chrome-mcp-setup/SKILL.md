---
name: chrome-mcp-setup
description: "Mechanics of isolated Chrome DevTools MCP setup: per-session browsers, fresh profiles, where screenshots may be written, and the sanctioned way to close the browser."
when_to_use: "Use before the first mcp__chrome-devtools__* call in a session, and again when taking a screenshot or closing the browser. Covers setup mechanics only -- the standing restriction against navigating to non-localhost URLs lives in CLAUDE.md and applies whether or not this skill is loaded."
---

## Per-session isolation

Each session gets its own isolated Chrome, so sessions never block each other -- just open yours.

<!-- The user-scope `chrome-devtools` MCP server runs with `--headless` so no window gets in the user's way, and with `--isolated`, giving each session a throwaway temp `--user-data-dir`. The plugin's shared-profile server is disabled in settings.json via `deniedMcpServers` matching its name `plugin:chrome-devtools-mcp:chrome-devtools`, which is version-independent so plugin updates won't resurrect it. The `--isolated` server definition lives in `~/.claude.json`, which is not tracked in dotfiles. -->

Isolated profiles are fresh on every launch: no persisted wp-admin logins, cookies, or extensions. Log in as part of the flow if a task needs it.

## Screenshots

Pass an absolute `filePath` under the OS temp dir. Run `getconf DARWIN_USER_TEMP_DIR` to get it (e.g. `/var/folders/.../T/`). The MCP tool only allows writes there.

## Closing the browser

On request, or when done with it:

```bash
bash ~/dotfiles/claude/bin/close-isolated-chrome.sh
```

Run it with the command sandbox disabled -- it needs `ps` and `kill`, which the sandbox blocks. It targets only this session's browser via process ancestry, never a parallel session's isolated browser or the user's personal Chrome.

Do NOT call `kill` or `pkill` yourself. Both are denied, and this helper is the only sanctioned path.

The isolated profile also auto-deletes when the browser closes, including at session end, so forgetting to close it still cleans up.
