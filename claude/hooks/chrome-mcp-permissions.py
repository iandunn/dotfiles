#!/usr/bin/env python3
"""
Permission gate for Chrome DevTools MCP tools (PreToolUse hook).

main() dispatches on the tool name so additional gates can be added over time.

Currently implemented:
  - Non-local navigation gate (navigate_page / new_page): navigations to a
    non-local host ALWAYS return "ask" with a warning that approving also lets
    evaluate_script/click/fill/etc. run automatically on that site, where
    prompt injection from external page content can escalate to remote code
    execution. This is unconditional -- a high-usage session never suppresses
    it, since security takes precedence over a token-usage nicety. A single
    PreToolUse hook invocation can only return one decision, so on a call that
    is BOTH a non-local navigation AND this session's first not-yet-checked
    usage gate, only the host-trust prompt is shown; the usage check is left
    unresolved (its marker is not written) so it fires on the next safe
    opportunity instead of being silently dropped.

    LIMITATION: this gate only sees explicit navigate_page/new_page calls. The
    MCP launches Chrome over a puppeteer pipe (browser.ts: `pipe: true`), not a
    TCP debug port, so there is no CDP HTTP endpoint to query for the live URL.
    The action tools (click, fill, evaluate_script) carry no URL in their input
    either. Therefore the hook CANNOT detect when an already-approved page
    redirects via JavaScript, or when a click on a link leads to a different
    external host -- those will not re-trigger this prompt.

  - Session usage gate (first "safe" chrome-devtools call of the session):
    fetches the live 5-hour rate-limit utilization straight from Anthropic's
    usage API (the same endpoint ccstatusline itself falls back to). "Safe"
    means: a local-host navigation, back/forward/reload, or any
    non-navigation tool -- i.e. any call that didn't already need a
    host-trust prompt. On the first such call seen for a given session_id,
    if usage is above the threshold, returns "ask" instead of falling
    through to settings.json's allow list; every subsequent safe call in
    that session is allowed silently. This is a one-time "are you sure you
    want to keep using Chrome MCP" check, not a per-click gate. CLAUDE.md's
    "don't use the Chrome MCP above 60% session usage" rule cannot be
    self-enforced by the model -- it is never given a usage number during a
    turn -- so this hook is the only place that can act on it.

    This used to read ccstatusline's usage cache
    (~/.cache/ccstatusline/usage.json), but that file is only ever populated
    as a one-off fallback during a session's very first render, before
    Claude Code's statusline stdin has rate_limits data yet. Once any
    session has that live data, ccstatusline never touches the cache file
    again, so it goes stale forever and no longer reflects real usage --
    which is why this hook now shells out to `claude -p "/usage"` and parses
    its output instead. That's slower (several seconds), but it only runs
    once per session and avoids touching OAuth credentials directly. If the
    command fails, times out, or its output doesn't parse, fails open
    (allow) rather than blocking on absent data.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

SESSION_USAGE_THRESHOLD = 60
USAGE_COMMAND_TIMEOUT_SECONDS = 30
SESSION_GATE_MARKER_DIR = os.path.join(tempfile.gettempdir(), 'claude-chrome-mcp-usage-gate')


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


def gate_navigation(tool_input, session_id):
    url = tool_input.get('url')

    # navigate_page with type back/forward/reload has no URL and stays within
    # already-visited history; nothing new to gate on the host front, but it
    # still counts as a "safe" call for the session usage gate.
    if not url:
        if not gate_session_usage(session_id):
            emit('allow', 'Navigation stays within current/visited pages')
        return

    host = urlparse(url).hostname or ''

    if host and is_local_host(host):
        if not gate_session_usage(session_id):
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


def is_chrome_devtools_tool(tool_name):
    return 'chrome-devtools__' in tool_name


def fetch_live_session_usage():
    """Returns the current 5-hour rate-limit usage (0-100) by shelling out to
    `claude -p "/usage"` and parsing its "Current session: NN% used" line, or
    None on any failure -- callers should fail open on None rather than block
    on absent data."""
    try:
        result = subprocess.run(
            ['claude', '-p', '/usage'],
            capture_output=True, text=True, timeout=USAGE_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    match = re.search(r'Current session:\s*(\d+(?:\.\d+)?)%\s*used', result.stdout)
    return float(match.group(1)) if match else None


def gate_session_usage(session_id):
    """Returns True if it emitted a decision (caller should stop); False to
    fall through to the next gate. Only acts on the first chrome-devtools
    call seen for a given session_id -- every later call in that session
    returns False (silently allowed) so the check doesn't repeat per click."""
    marker_path = os.path.join(SESSION_GATE_MARKER_DIR, f'{session_id or "unknown"}.marker')

    if os.path.exists(marker_path):
        return False

    try:
        os.makedirs(SESSION_GATE_MARKER_DIR, exist_ok=True)
        with open(marker_path, 'w') as f:
            f.write('gated')
    except OSError:
        pass

    usage = fetch_live_session_usage()

    if not isinstance(usage, (int, float)) or usage <= SESSION_USAGE_THRESHOLD:
        return False

    reason = (
        f'Session usage is {usage}%. Chrome MCP uses a lot of tokens, do you want to continue?'
    )
    emit('ask', reason)
    return True


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})
    session_id = data.get('session_id', '')

    if tool_name.endswith(('navigate_page', 'new_page')):
        gate_navigation(tool_input, session_id)
        return

    if is_chrome_devtools_tool(tool_name):
        gate_session_usage(session_id)


if __name__ == '__main__':
    main()
