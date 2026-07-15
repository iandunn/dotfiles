#!/usr/bin/env python3
"""
Permission gate for Chrome DevTools MCP tools (PreToolUse hook).

main() dispatches on the tool name so additional gates can be added over time.

Currently implemented:
  - Non-local navigation gate (navigate_page / new_page): navigations to local
    dev hosts (localhost, 127.0.0.1, *.localhost, *.test) are auto-approved;
    navigations to any other host return "ask" with a warning that approving
    also lets evaluate_script/click/fill/etc. run automatically on that site,
    where prompt injection from external page content can escalate to remote
    code execution.

    back/forward/reload navigations (no target URL) stay within already-visited
    history, so they are auto-approved.

    LIMITATION: this gate only sees explicit navigate_page/new_page calls. The
    MCP launches Chrome over a puppeteer pipe (browser.ts: `pipe: true`), not a
    TCP debug port, so there is no CDP HTTP endpoint to query for the live URL.
    The action tools (click, fill, evaluate_script) carry no URL in their input
    either. Therefore the hook CANNOT detect when an already-approved page
    redirects via JavaScript, or when a click on a link leads to a different
    external host -- those will not re-trigger this prompt.
"""
import json
import sys
from urllib.parse import urlparse


def is_local_host(host):
    """Returns True for localhost, 127.0.0.1, and *.localhost / *.test hosts."""
    host = host.lower()
    return (
        host in ('localhost', '127.0.0.1')
        or host.endswith('.localhost')
        or host.endswith('.test')
    )


def emit(decision, reason):
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': decision,
            'permissionDecisionReason': reason,
        }
    }))


def gate_navigation(tool_input):
    url = tool_input.get('url')

    # navigate_page with type back/forward/reload has no URL and stays within
    # already-visited history; nothing new to gate.
    if not url:
        emit('allow', 'Navigation stays within current/visited pages')
        return

    host = urlparse(url).hostname or ''

    if host and is_local_host(host):
        emit('allow', f'Local host ({host}) auto-approved')
        return

    reason = (
        f"Navigating to non-local host '{host or url}'. Approving this ALSO lets "
        'evaluate_script, click, fill, and other Chrome tools run automatically on '
        'this site with no further prompts. Prompt injection from external page '
        'content can escalate to remote code execution (RCE) -- only approve hosts '
        'you trust. This gate fires only on explicit navigation; it cannot '
        're-prompt if an approved page later redirects or a link leads to another '
        'external host.'
    )
    emit('ask', reason)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    if tool_name.endswith(('navigate_page', 'new_page')):
        gate_navigation(tool_input)


if __name__ == '__main__':
    main()
