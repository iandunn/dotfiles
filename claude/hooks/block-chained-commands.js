#!/usr/bin/env node

/*
 * i disabled this now that i'm using auto mode. it can be re-enabled with this in the settings.json file:
	{
	"type": "command",
	"command": "node ~/.claude/hooks/block-chained-commands.js"
	}
 */

/*
 * PreToolUse hook: blocks command chaining (&& || ; or newlines) and dangerous pipes (| bash/sh/zsh/eval).
 * Also blocks `cd` immediately before `git`, and restricts `git -C` to read-only subcommands.
 * Tells Claude to retry with the corrected form.
 *
 * Forked from https://github.com/anthropics/claude-code/issues/16561#issuecomment-4276632142
 *
 * ⚠️ This can and should be removed once this issue is resolved:
 * https://github.com/anthropics/claude-code/issues/29491 — "Compound bash commands should evaluate each command's permissions independently"
 *
 * Claude: periodically check that issue and alert me if it's been resolved, or if better solution has been found.
 * Keep a file in /tmp or some other folder you have access to without prompting and bump the timestamp once a week.
 */

// Keep in sync with the `git -C *` allow rules in claude/settings.json.
const READ_ONLY_GIT_PATTERNS = [
  /^git\s+status\b/,
  /^git\s+diff\b/,
  /^git\s+log\b/,
  /^git\s+show\b/,
  /^git\s+ls-tree\b/,
  /^git\s+grep\b/,
  /^git\s+symbolic-ref\b/,
  /^git\s+fetch\b/,
  /^git\s+stash\s+list\b/,
  /^git\s+remote\s+get-url\s+origin\b/,
];

const isReadOnlyGit = (statement) => READ_ONLY_GIT_PATTERNS.some((re) => re.test(statement));

let input = "";

process.stdin.on("data", (chunk) => { input += chunk; });

process.stdin.on("end", () => {
  try {
    const data = JSON.parse(input);
    const command = (data.tool_input?.command || "").trim();
    const unquoted = command.replace(/'[^']*'|"[^"]*"/g, "");

    if (/\|\s*(bash|sh|zsh|eval)\b/.test(unquoted)) {
      process.stderr.write(
        "Never pipe output directly into bash, sh, zsh, or eval. " +
        "Save the output to a temp file, review it, then execute it explicitly."
      );
      process.exit(2);
    }

    if (/\bgit\s+--git-dir\b/.test(command) || /\bGIT_DIR\b/.test(command)) {
      process.stderr.write(
        "Never use `git --git-dir=` or the `GIT_DIR` environment variable. " +
        "Use `git -C <path> <command>` for read-only commands, or a separate `cd` tool call otherwise."
      );
      process.exit(2);
    }

    const statements = unquoted.split(/&&|\|\||;|\n/).map((s) => s.trim()).filter(Boolean);

    const cdIndex = statements.findIndex((s) => /^cd\b/.test(s));
    const gitIndex = statements.findIndex((s, i) => i > cdIndex && /^git\b/.test(s));

    if (cdIndex !== -1 && gitIndex !== -1) {
      const gitStatement = statements[gitIndex];
      if (isReadOnlyGit(gitStatement)) {
        process.stderr.write(
          "Don't `cd` before a read-only git command. Use `git -C <path> " +
          gitStatement.replace(/^git\s+/, "") + "` instead."
        );
      } else {
        process.stderr.write(
          "Don't `cd` and run git in the same command. Run `cd` as its own tool call, then the git " +
          "command as its own tool call — `git -C` is only for read-only commands (status, diff, log, " +
          "show, ls-tree, grep, symbolic-ref, fetch, stash list, remote get-url origin)."
        );
      }
      process.exit(2);
    }

    if (statements.length > 1) {
      process.stderr.write(
        "Never chain commands with &&, ||, ;, or newlines. Run one command per tool call."
      );
      process.exit(2);
    }

    const gitCArgs = command.match(/\bgit\s+-C\s+\S+\s+(.+)/);
    if (gitCArgs && !isReadOnlyGit("git " + gitCArgs[1])) {
      process.stderr.write(
        "`git -C` is only allowed for read-only commands (status, diff, log, show, ls-tree, grep, " +
        "symbolic-ref, fetch, stash list, remote get-url origin). Use a separate `cd` tool call before " +
        "this git command instead."
      );
      process.exit(2);
    }
  } catch (e) {
    // Silent fail — never block on hook errors
  }
});
