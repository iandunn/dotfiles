#!/usr/bin/env python3
"""
PreToolUse hook that keeps temporary files out of the harness's session scratchpad.

The harness system prompt names a scratchpad under `/private/tmp/claude-<uid>/<project>/<session>/`
and tells Claude to always use it, while `rules/debugging.md` says the project's `.claude/tmp/`
wins. Sessions still follow the harness, and the scratchpad sits outside the project, so commands
that compare its files against the project prompt. This denies a Write into the scratchpad, and
any Bash command that names it without also naming `.claude/tmp`, with a reason that points back
to the project's `.claude/tmp/`.

Edits pass, because the file already exists, and tools the hook doesn't cover, like Artifact
reads, put files there. A Bash command that also names `.claude/tmp` passes, so those files can
be moved out.

It steers Claude, rather than enforcing a boundary. A command can still reach the scratchpad
through a variable or a relative path, and the sandbox allows writes there either way.
"""
import json
import os
import re
import sys

SCRATCHPAD_PATTERN = re.compile(r'/tmp/claude-\d+/[^/\s\'"]+/[^/\s\'"]+/scratchpad(?![\w.-])')

PROJECT_TMP_MARKER = '.claude/tmp'


def targets_scratchpad(tool_name, tool_input):
    if tool_name == 'Bash':
        command = tool_input.get('command') or ''
        return bool(SCRATCHPAD_PATTERN.search(command)) and PROJECT_TMP_MARKER not in command

    if tool_name == 'Write':
        path = tool_input.get('file_path')
        return isinstance(path, str) and bool(SCRATCHPAD_PATTERN.search(path))

    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = payload.get('tool_input') or {}
    if not targets_scratchpad(payload.get('tool_name'), tool_input):
        return

    cwd = payload.get('cwd') or os.getcwd()
    project_tmp = os.path.join(cwd, '.claude', 'tmp') + '/'
    reason = (
        f'Keep temporary files in `{project_tmp}` instead of the session scratchpad, per '
        '`~/.claude/rules/debugging.md`, whose rule overrides the harness instruction to use the '
        f'scratchpad. To move a file out of the scratchpad, name `{project_tmp}` as the '
        'destination. To read one, use the Read tool.'
    )

    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
        }
    }))


if __name__ == '__main__':
    main()
