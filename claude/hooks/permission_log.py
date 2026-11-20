"""
Appends permission events to a local JSONL log, so `claude/bin/permission-prompt-report.py` can
show which prompts come up most often.

`log-permission-prompts.py` writes one line per prompt Claude Code shows. Commands can hold tokens,
so the log is readable only by its owner.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_PATH = Path.home() / '.local/state/claude-permission-prompts/log.jsonl'

# Tests point the log somewhere disposable. Hooks inherit Claude Code's environment, not the
# environment of the command being judged, so a Bash command can't redirect it.
LOG_PATH_VARIABLE = 'CLAUDE_PERMISSION_LOG'

# Keeps one huge argument, like a heredoc, from bloating the log.
MAX_STRING_LENGTH = 4000


def log_path():
    return Path(os.environ.get(LOG_PATH_VARIABLE) or DEFAULT_LOG_PATH)


def truncate(value):
    if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        return value[:MAX_STRING_LENGTH] + '...[truncated]'
    if isinstance(value, dict):
        return {key: truncate(item) for key, item in value.items()}
    if isinstance(value, list):
        return [truncate(item) for item in value]
    return value


def append(entry):
    entry = {'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'), **truncate(entry)}
    # `backslashreplace` keeps a lone surrogate in a command from dropping the whole line.
    line = (json.dumps(entry, ensure_ascii=False) + '\n').encode('utf-8', 'backslashreplace')

    path = log_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    # `O_NOFOLLOW` keeps a planted symlink from turning the append into a write somewhere else.
    # One `write()` on an `O_APPEND` descriptor keeps lines from parallel hooks from interleaving.
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.write(descriptor, line)
    finally:
        os.close(descriptor)


def payload_fields(payload):
    """The parts of a hook payload worth keeping, for matching prompts to the hooks that asked."""
    fields = {
        'session_id': payload.get('session_id'),
        'cwd': payload.get('cwd'),
        'tool_name': payload.get('tool_name'),
        'tool_input': payload.get('tool_input'),
    }
    for optional in ('agent_id', 'agent_type', 'permission_mode'):
        if payload.get(optional):
            fields[optional] = payload[optional]
    return fields
