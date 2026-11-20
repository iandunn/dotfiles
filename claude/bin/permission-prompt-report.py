#!/usr/bin/env python3
"""
Groups the permission prompts Claude Code showed by the reason they came up, most frequent first.

Reads the log that `claude/hooks/log-permission-prompts.py` writes. A prompt no hook asked for came
from a `settings.json` rule, an unsandboxed command, a hook outside `~/.claude/settings.json`, or a
tool with no rule, so those are grouped by the program they ran instead.

Usage: permission-prompt-report.py [--days N] [--log PATH]
"""

import argparse
import json
import re
import shlex
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'hooks'))
from permission_log import log_path  # noqa: E402

NO_HOOK_REASON = (
    'no hook in ~/.claude/settings.json asked (a settings rule, an unsandboxed command, or no rule)'
)
UNKNOWN_REASON = 'reason unknown (the hooks could not be re-run)'
EXAMPLE_LENGTH = 200


def read_prompts(path, since):
    prompts = []
    with open(path, encoding='utf-8') as log:
        for line in log:
            try:
                entry = json.loads(line)
                entry['time'] = datetime.fromisoformat(entry['ts'])
            except (ValueError, KeyError, TypeError):
                continue
            if entry.get('event') == 'prompt' and entry['time'] >= since:
                prompts.append(entry)
    return prompts


def printable(text):
    """Escapes control characters, so a logged command can't rewrite the terminal's output."""
    return ''.join(
        character if character.isprintable() else character.encode('unicode_escape').decode()
        for character in text
    )


def normalize(reason):
    """Collapses the specifics in a reason, like a path in backticks, so similar prompts group."""
    reason = printable(' '.join(reason.split()))
    reason = re.sub(r'`[^`]*`', '`...`', reason)
    reason = re.sub(r'"[^"]*"', '"..."', reason)
    return re.sub(r'\d+', 'N', reason)


def program_of(entry):
    """The program and subcommand a prompt ran, like `git worktree`, to group reasonless prompts."""
    tool_input = entry.get('tool_input') or {}
    if entry.get('tool_name') != 'Bash' or not tool_input.get('command'):
        return entry.get('tool_name') or 'unknown tool'
    try:
        words = shlex.split(tool_input['command'])
    except ValueError:
        words = tool_input['command'].split()
    if words and words[0] == 'command':
        words = words[1:]
    if not words:
        return 'Bash'
    if words[0] == 'git':
        rest = words[1:]
        while rest[:1] == ['-C'] and len(rest) > 1:
            rest = rest[2:]
        return f"git {rest[0]}" if rest else 'git'
    return words[0]


def reason_for(entry):
    reasons = entry.get('hook_reasons')
    if reasons is None:
        return UNKNOWN_REASON
    labels = sorted({
        f"{item['hook']}: not re-run, so it may have asked"
        if item.get('rerun') is False
        else f"{item['hook']}: {normalize(item.get('reason') or '')}"
        for item in reasons
    })
    return ' + '.join(labels) or f"{NO_HOOK_REASON}: `{printable(program_of(entry))}`"


def example_text(entry):
    tool_input = entry.get('tool_input') or {}
    text = tool_input.get('command') if entry.get('tool_name') == 'Bash' else json.dumps(tool_input)
    text = printable(' '.join(str(text).split()))
    if len(text) > EXAMPLE_LENGTH:
        text = text[:EXAMPLE_LENGTH] + '...'
    return f"{entry.get('tool_name') or 'unknown tool'}: {text}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--days', type=int, default=30, help='how far back to look (default 30)')
    parser.add_argument('--log', type=Path, default=None, help='log file to read')
    arguments = parser.parse_args()

    path = arguments.log or log_path()
    if not path.exists():
        print(f'No log yet at {path}')
        return

    since = datetime.now(timezone.utc) - timedelta(days=arguments.days)
    prompts = read_prompts(path, since)

    groups = defaultdict(list)
    for prompt in prompts:
        groups[reason_for(prompt)].append(prompt)

    print(f'Prompts in the last {arguments.days} days: {len(prompts)}')
    print()
    for reason, entries in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True):
        last_seen = max(entry['time'] for entry in entries).astimezone().strftime('%Y-%m-%d')
        print(f'  {len(entries):>4}  last {last_seen}  {reason}')
        print(f'        e.g. {example_text(entries[-1])}')
        print()


if __name__ == '__main__':
    main()
