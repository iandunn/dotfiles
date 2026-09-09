#!/usr/bin/env node

/*
 * PreToolUse hook: blocks command shapes that slip past the prefix-matched deny rules in
 * settings.json. Those rules match from the start of the line, so a destructive command wearing
 * a `-C <path>` flag, or sitting second in a chain, matches nothing.
 *
 * Three shapes are covered:
 *   - piping into a shell (`| bash`, `| sh`, `| zsh`, `| eval`), where the line starts with
 *     whatever produced the script
 *   - `git --git-dir=` and `GIT_DIR`, which retarget a git command at another repository
 *   - destructive git subcommands reached via `git -C <path>` or from later in a chain
 *
 * Runs unfiltered on every Bash call, because the first shape can begin with any command.
 *
 * Read-only and recoverable git forms pass through: `settings.json` allows the read-only
 * subcommands and `git config --get`, and `file-command-permissions.py` owns
 * `git -C <worktree> add|commit`.
 *
 * ⚠️ Forked from https://github.com/anthropics/claude-code/issues/16561#issuecomment-4276632142.
 * The chaining and `cd`-before-`git` checks this hook used to carry were dropped once Claude Code
 * began evaluating literal `&&` chains independently; see
 * https://github.com/anthropics/claude-code/issues/29491.
 */

// Destructive git subcommands, mirroring the `Bash(git ...)` entries in `permissions.deny`. Each
// is tested against a statement whose `-C <path>` has been stripped, so `git -C /repo reset --hard`
// is caught by the same pattern as `git reset --hard`.
const DESTRUCTIVE_GIT_PATTERNS = [
  /^git\s+clean\b/,
  /^git\s+push\s+(--force|-f|--mirror|--delete)\b/,
  /^git\s+reset\s+--hard\b/,
  /^git\s+checkout\s+(\.|--\s)/,
  /^git\s+restore\s+(\.|--worktree\b)/,
  /^git\s+config\b(?!\s+--get)/,
  /^git\s+cherry-pick\b/,
  /^git\s+filter-/,
  /^git\s+update-ref\b/,
  /^git\s+tag\s+-d\b/,
  /^git\s+submodule\s+deinit\b/,
];

const isDestructiveGit = (statement) => DESTRUCTIVE_GIT_PATTERNS.some((re) => re.test(statement));

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
        "Use `git -C <path> <command>` instead."
      );
      process.exit(2);
    }

    const statements = unquoted.split(/&&|\|\||;|\||\n/).map((s) => s.trim()).filter(Boolean);
    const destructive = statements
      .map((s) => s.replace(/^git\s+-C\s+\S+\s+/, "git "))
      .find(isDestructiveGit);

    if (destructive) {
      process.stderr.write(
        "`" + destructive.split(/\s+/).slice(0, 3).join(" ") + "` is denied by `permissions.deny`, " +
        "and reaching it through `-C` or a chain doesn't exempt it. If the task genuinely needs it, " +
        "stop and say so rather than rewording the command."
      );
      process.exit(2);
    }
  } catch (e) {
    // Silent fail — never block on hook errors
  }
});
