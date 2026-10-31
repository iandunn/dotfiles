#!/usr/bin/env python3
"""UserPromptSubmit hook that adds a keyword's rules to the context only when a prompt uses it.

The hold/resume and parallel-plan rules are long and only matter in sessions that use those
keywords, so they live in `claude/prompt-rules/` instead of `CLAUDE.md`. `CLAUDE.md` keeps a short
guardrail for each, because compaction can summarize away the injected copy.
"""
import json
import re
import sys
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent.parent / 'prompt-rules'

# "resume" joined to a path, a hyphenated name, or a file extension, like `/relay-eng:resume-work`
# or `resume.pdf`, isn't the keyword. "go" only counts at the very start of the prompt, like "go
# but keep the old name", and not as "go ahead" or "go-live".
TRIGGERS = {
    'hold-resume.md': [r'\bhold\b', r'(?<![\w/-])resume(?![\w-]|\.[a-z])'],
    'parallel-plan.md': [r'\bpplan\b', r'\bparallel plan\b', r'\A\W*go\b(?![\W_]*ahead\b)(?!-)'],
}

# Background-task notifications and agent messages arrive through this hook too, but they're
# never the user's keyword.
NON_USER_PROMPT_MARKERS = ('<task-notification>', '<agent-message ', '[SYSTEM NOTIFICATION')


def matching_rule_files(prompt):
    if any(marker in prompt for marker in NON_USER_PROMPT_MARKERS):
        return []

    return [
        name for name, patterns in TRIGGERS.items()
        if any(re.search(pattern, prompt, re.IGNORECASE) for pattern in patterns)
    ]


def read_rules(name):
    try:
        return (RULES_DIR / name).read_text()
    except OSError as error:
        # A missing file would silently drop a guardrail, so surface it instead.
        path = RULES_DIR / name
        return f'The keyword rules file `{path}` could not be read ({error}). Tell the user.'


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if not isinstance(payload, dict):
        return 0

    prompt = payload.get('prompt') or ''
    sections = [read_rules(name) for name in matching_rule_files(prompt)]

    if not sections:
        return 0

    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'UserPromptSubmit',
            'additionalContext': '\n\n'.join(sections),
        }
    }))
    return 0


if __name__ == '__main__':
    sys.exit(main())
