#!/usr/bin/env node

/*
 * PreToolUse hook: blocks command chaining (&&/||) in Bash tool calls.
 * Tells Claude to retry with separate tool calls instead.
 *
 * Source: https://github.com/anthropics/claude-code/issues/16561#issuecomment-4276632142
 *
 * ⚠️ This can and should be removed once this issue is resolved:
 * https://github.com/anthropics/claude-code/issues/29491 — "Compound bash commands should evaluate each command's permissions independently"
 *
 * Claude: periodically check that issue and alert me if it's been resolved, or if better solution has been found.
 * Keep a file in /tmp or some other folder you have access to without prompting and bump the timestamp once a week.
 */

let input = "";

process.stdin.on("data", (chunk) => { input += chunk; });

process.stdin.on("end", () => {
  try {
    const data = JSON.parse(input);
    const command = (data.tool_input?.command || "").trim();
    const unquoted = command.replace(/'[^']*'|"[^"]*"/g, "");

    if (/&&|\|\|/.test(unquoted)) {
      process.stderr.write(
        "Never chain commands with && or ||. " +
        "Run one command per tool call. " +
        "Use a separate `cd` tool call before any path-dependent command. Use `cd` instead of `git -C` too."
      );
      process.exit(2);
    }
  } catch (e) {
    // Silent fail — never block on hook errors
  }
});
