#!/usr/bin/env python3
"""
Logs every permission prompt Claude Code shows, with the hooks that asked for it (PermissionRequest
hook).

This catches prompts from every source: a hook's `ask`, a `settings.json` ask rule, an unsandboxed
command, or a tool with no rule. The payload has no reason, so the logger re-runs the PreToolUse
permission hooks from `~/.claude/settings.json` on the same tool input and records each one that
returns `ask`. That re-runs the hooks, never the command. Hooks in project settings or plugins
aren't re-run.

The re-run happens in a detached process, so the prompt never waits on it, and nothing here sits in
the PreToolUse decision path. A prompt approved before the re-run finishes can change what a hook
sees, like a file `rm` already deleted, so its reason can occasionally be wrong.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from permission_log import append, payload_fields

SETTINGS_PATH = Path.home() / '.claude/settings.json'
HOOKS_DIR = Path(__file__).resolve().parent

# Hooks verified to have no side effects, so running them again is safe. Any other hook in this
# folder is logged as "not re-run", like `chrome-mcp-permissions.py`, which writes a marker the first
# time a session uses Chrome.
RERUN_HOOKS = {
    'command-allowlist-permissions.py',
    'dangerous-command-shapes.py',
    'desktop-app-permissions.py',
    'file-command-permissions.py',
    'read-deny-permissions.py',
    'safe-curl-check.py',
}

HOOK_TIMEOUT_SECONDS = 10


def matcher_covers(matcher, tool_name):
    # Claude Code treats an empty or missing matcher, and `*`, as matching every tool.
    if not matcher or matcher == '*':
        return True
    try:
        return re.fullmatch(matcher, tool_name) is not None
    except re.error:
        return False


def matching_hook_scripts(tool_name, settings_path=SETTINGS_PATH):
    """
    The PreToolUse hook scripts in this folder whose matcher covers the tool, and the names of the
    ones that cover it but are skipped.
    """
    settings = json.loads(Path(settings_path).read_text())
    scripts, skipped = [], []
    for group in settings.get('hooks', {}).get('PreToolUse', []):
        if not matcher_covers(group.get('matcher'), tool_name):
            continue
        for hook in group.get('hooks', []):
            words = shlex.split(hook.get('command', ''))
            if len(words) != 2 or os.path.basename(words[0]) not in ('python3', 'python'):
                continue
            script = Path(os.path.expanduser(words[1])).resolve()
            # Only this folder's own hooks get run, never an arbitrary command from the settings.
            if script.parent != HOOKS_DIR:
                continue
            if script.name not in RERUN_HOOKS:
                if script.name not in skipped:
                    skipped.append(script.name)
            elif script not in scripts:
                scripts.append(script)
    return scripts, skipped


def ask_reason(script, payload):
    """The hook's reason when it returns `ask` for the payload, or None."""
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=HOOK_TIMEOUT_SECONDS,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    specific = json.loads(result.stdout).get('hookSpecificOutput') or {}
    if specific.get('permissionDecision') != 'ask':
        return None
    return specific.get('permissionDecisionReason', '')


def hook_reasons(payload, settings_path=SETTINGS_PATH):
    pre_tool_use_payload = {**payload, 'hook_event_name': 'PreToolUse'}
    pre_tool_use_payload.pop('permission_suggestions', None)
    scripts, skipped = matching_hook_scripts(payload.get('tool_name') or '', settings_path)

    def safe_ask_reason(script):
        try:
            return ask_reason(script, pre_tool_use_payload)
        except Exception:
            return None

    with ThreadPoolExecutor() as pool:
        reasons = list(pool.map(safe_ask_reason, scripts))
    asked = [
        {'hook': script.name, 'reason': reason}
        for script, reason in zip(scripts, reasons)
        if reason is not None
    ]
    # A skipped hook may be the one that asked, so the report mustn't read its absence as "no hook".
    return asked + [{'hook': name, 'reason': None, 'rerun': False} for name in skipped]


def record(payload):
    try:
        reasons = hook_reasons(payload)
    except Exception:
        reasons = None
    append({
        'event': 'prompt',
        'hook_reasons': reasons,
        'permission_suggestions': payload.get('permission_suggestions'),
        **payload_fields(payload),
    })


def main():
    stdin = sys.stdin.read()

    if len(sys.argv) == 2 and sys.argv[1] == '--record':
        record(json.loads(stdin))
        return

    json.loads(stdin)
    worker = subprocess.Popen(
        [sys.executable, __file__, '--record'],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    worker.stdin.write(stdin)
    worker.stdin.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # A missing log line must never interfere with the permission prompt itself.
        pass
