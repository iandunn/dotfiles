#!/usr/bin/env python3
"""
PreToolUse hook: auto-approve compound Bash commands where every
individual subcommand matches an existing allow rule.

Addresses the known bug where `cd subdir && git log` requires manual
approval even though both `cd *` and `git log *` are in the allow list.

⚠️ This can and should be removed once these issues are resolved:
* https://github.com/anthropics/claude-code/issues/29491 — "Compound bash commands should evaluate each command's permissions independently"
* https://github.com/anthropics/claude-code/issues/28183 — "Compound commands of individually-allowed safe commands prompt with incorrect safety reason"

Claude: periodically check those issues and alert me if they've been resolved, or if better solution has been found.
Keep a file in /tmp or some other folder you have access to without prompting and bump the timestamp once a week.


INSTALL
-------
1. Save to ~/.claude/hooks/compound_allow.py
2. chmod +x ~/.claude/hooks/compound_allow.py
3. Add to ~/.claude/settings.json:

   "hooks": {
     "PreToolUse": [
       {
         "matcher": "Bash",
         "hooks": [
           {
             "type": "command",
             "command": "python3 ~/.claude/hooks/compound_allow.py"
           }
         ]
       }
     ]
   }
4. Restart claude
"""

import fnmatch
import json
import os
import re
import sys

# Reject subcommands containing shell expansion/redirection metacharacters.
# fnmatch's * would otherwise allow patterns like "git log *" to match
# "git log $(cat /etc/shadow)", causing the subshell to execute on approval.
_SHELL_METACHAR_RE = re.compile(r"[$`<>|]")


def load_bash_allow_rules() -> list[str]:
    """Load Bash allow patterns from all applicable settings files."""
    patterns: list[str] = []

    project_dir = os.path.realpath(
        os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    )
    # User settings are trusted; project settings are not — a malicious repo
    # could include Bash(*) to make every compound command auto-approve.
    settings_paths = [
        (os.path.expanduser("~/.claude/settings.json"), True),
        (os.path.join(project_dir, ".claude/settings.json"), False),
        (os.path.join(project_dir, ".claude/settings.local.json"), False),
    ]

    for path, trusted in settings_paths:
        try:
            with open(path) as f:
                data = json.load(f)
            for rule in data.get("permissions", {}).get("allow", []):
                if rule in ("Bash", "Bash(*)"):
                    if trusted:
                        patterns.append("*")
                    # Skip wildcard rules from project settings.
                elif rule.startswith("Bash(") and rule.endswith(")"):
                    pat = rule[5:-1]
                    # Normalize deprecated :* suffix → space wildcard
                    if pat.endswith(":*"):
                        pat = pat[:-2] + " *"
                    patterns.append(pat)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    return patterns


_GIT_DASH_C_RE = re.compile(r"^git\s+-C\s+\S+\s+")


def normalize_cmd(cmd: str) -> str:
    """Strip flags that don't change which subcommand is being run."""
    # `git -C /path diff` → `git diff` so existing `git diff:*` rules apply
    return _GIT_DASH_C_RE.sub("git ", cmd)


def matches_any_rule(cmd: str, patterns: list[str]) -> bool:
    """Return True if cmd matches at least one allow pattern."""
    cmd = normalize_cmd(cmd.strip())
    if _SHELL_METACHAR_RE.search(cmd):
        return False
    for pat in patterns:
        if pat == "*":
            return True
        if fnmatch.fnmatch(cmd, pat):
            return True
        # "git log *" requires a space+arg, but bare "git log" is also fine
        if pat.endswith(" *") and cmd == pat.removesuffix(" *"):
            return True
    return False


def split_compound(cmd: str) -> list[str]:
    """
    Split on &&, ||, ; shell operators, ignoring operators inside quotes.
    e.g., git commit -m "fix && cleanup" is a single command, not compound.
    """
    unquoted = re.sub("'[^']*'" + '|"[^"]*"', "", cmd)
    if not re.search(r"&&|\|\||;|\n", unquoted):
        return [cmd.strip()] if cmd.strip() else []
    parts = re.split(r"\s*(?:&&|\|\||;|\n)\s*", cmd)
    return [p.strip() for p in parts if p.strip()]


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "").strip()
    if not cmd:
        sys.exit(0)

    # Only intervene on compound commands; simple ones are handled by
    # the normal allow-list logic fine.
    parts = split_compound(cmd)
    if len(parts) <= 1:
        sys.exit(0)

    patterns = load_bash_allow_rules()
    if not patterns:
        sys.exit(0)

    if all(matches_any_rule(part, patterns) for part in parts):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason":
                    "All subcommands match existing allow rules",
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()