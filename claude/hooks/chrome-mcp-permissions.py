#!/usr/bin/env python3
"""
Permission gate for Chrome DevTools MCP tools (PreToolUse hook).

main() dispatches on the tool name so additional gates can be added over time.

Currently implemented:
  - Non-local navigation gate (navigate_page / new_page): navigations to a
    non-local host return "ask" with a warning that approving also lets
    evaluate_script/click/fill/etc. run automatically on that site, where
    prompt injection from external page content can escalate to remote code
    execution. A high-usage session never suppresses it, since security takes
    precedence over a token-usage nicety. A single PreToolUse hook invocation
    can only return one decision, so on a call that is BOTH a non-local
    navigation AND this session's first not-yet-checked usage gate, only the
    host-trust prompt is shown; the usage check is left unresolved (its marker
    is not written) so it fires on the next safe opportunity instead of being
    silently dropped.

    Two settings lists let a host through silently, each for its own server
    only. `chromeDevtools.sites` covers the `chrome-devtools` server, including
    the plugin's copy of it, and `blockedSiteBrowser.sites` covers the
    `blocked-site-browser` server. Each is read from ~/.claude/settings.json and
    from a trusted project's .claude/settings.json and .claude/settings.local.json,
    committed or not. The global list applies to every project, and a project's
    lists add to it. A listed host also covers its `www.` twin, so `homedepot.com`
    and `www.homedepot.com` are the same site.

    Reading uncommitted project files adds no exposure: anything that can write
    them can already grant itself any permission or hook through them. A host on `chromeDevtools.sites` gets
    evaluate_script, fill, and the rest, so it belongs there only when that's
    acceptable, like a QA environment the project tests against.

    For `blocked-site-browser` the hook is an allowlist that fails closed: it
    allows only the read-only calls and arguments in
    BLOCKED_SITE_ALLOWED_ARGUMENTS, plus a `take_snapshot` file written into the
    working directory's `.claude/tmp/`, and prompts for every other call, and a
    crash prompts too. Its settings also deny evaluate_script, fill, and the
    other input and file-writing tools, as a second layer.

    The last exception is a project listed in PRE_AUTHORIZED_SITE_MATRICES:
    while cwd is inside one, the hosts named by that project's own site matrix
    are allowed silently. That exists for repos whose test loop IS driving live
    external sites -- a browser extension exercised against a fixed list of
    real pages -- where the prompt fires on every navigation and approving is
    the only possible answer. Every host outside the matrix still asks. This is
    the highest-exposure kind of allowance rather than the lowest, since those
    same sessions run evaluate_script against the pages they open.

    Matching is by host, not by exact URL, because approving one page on a host
    already grants every other page on it (see LIMITATION below) -- so exact-URL
    matching would add spurious prompts without adding a real boundary.

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
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

SESSION_USAGE_THRESHOLD = 80
USAGE_COMMAND_TIMEOUT_SECONDS = 30
SESSION_GATE_MARKER_DIR = os.path.join(tempfile.gettempdir(), 'claude-chrome-mcp-usage-gate')

# Project root -> the JSON site matrix inside it, shaped `{"sites": [{"url": ...}]}`.
# That matrix is the single source of truth for which hosts the project may open
# without a prompt, so adding a site to it is the only step needed.
PRE_AUTHORIZED_SITE_MATRICES = {
    '~/local-sites/misc/app/public/browser-extensions/slash-to-search': ('test/sites.json', None),
}

BLOCKED_SITE_TOOL_PREFIX = 'mcp__blocked-site-browser__'
BLOCKED_SITE_SETTINGS_KEY = 'blockedSiteBrowser'
CHROME_DEVTOOLS_SETTINGS_KEY = 'chromeDevtools'

# Named exactly, so another server whose name happens to end in `chrome-devtools` doesn't get
# the list.
CHROME_DEVTOOLS_TOOL_PREFIXES = ('mcp__chrome-devtools__', 'mcp__plugin_chrome-devtools-mcp_chrome-devtools__')
PROJECT_SETTINGS_FILE = '.claude/settings.json'
PROJECT_LOCAL_SETTINGS_FILE = '.claude/settings.local.json'

# The only `blocked-site-browser` calls this hook allows, and the only arguments each
# may carry. Every other tool or argument prompts, so a new tool or argument in a later
# `@latest` release, like a file path to save to or an `initScript`, can't slip through.
# The one exception is `take_snapshot`'s `filePath`, which passes only when it points into
# scratch (see is_scratch_file_path).
BLOCKED_SITE_ALLOWED_ARGUMENTS = {
    'navigate_page': {'url', 'type', 'timeout', 'pageId', 'ignoreCache', 'handleBeforeUnload'},
    'new_page': {'url', 'timeout', 'background'},
    'take_snapshot': {'pageId', 'verbose'},
    'list_pages': set(),
    'select_page': {'pageId', 'bringToFront'},
    'close_page': {'pageId'},
    'wait_for': {'pageId', 'text', 'timeout', 'visible'},
    'press_key': {'pageId', 'key', 'includeSnapshot'},
}

# Chrome reads a backslash as a slash and drops tabs and newlines, but urlparse keeps
# them in the authority, so `https://evil.com\@www.homedepot.com/` parses as Home Depot
# while Chrome opens evil.com. An unmatched bracket makes urlparse raise instead.
AMBIGUOUS_URL_CHARACTERS = ('\\', '\t', '\r', '\n', ' ', '[', ']')


def is_local_host(host):
    """Returns True for localhost, 127.0.0.1, and *.localhost / *.test hosts."""
    host = host.lower()
    return (
        host in ('localhost', '127.0.0.1')
        or host.endswith('.localhost')
        or host.endswith('.test')
    )


def pre_authorized_hosts(cwd, tool_name):
    """Returns the hosts the current project has pre-authorized for external
    navigation, read fresh from its site matrix on every call. Empty for any cwd
    outside a listed project root, and empty -- so the gate still prompts -- if the
    matrix is missing or unparseable."""
    cwd = os.path.realpath(cwd)

    for project_root, (matrix_path, tool_prefix) in PRE_AUTHORIZED_SITE_MATRICES.items():
        root = os.path.realpath(os.path.expanduser(project_root))

        # Comparing against root plus a separator keeps a sibling directory whose
        # name merely starts with the root's from counting as being inside it.
        if cwd != root and not cwd.startswith(root + os.sep):
            continue

        # A matrix tied to one server pre-authorizes nothing for the others.
        if tool_prefix and not tool_name.startswith(tool_prefix):
            return set()

        try:
            with open(os.path.join(root, matrix_path)) as matrix_file:
                sites = json.load(matrix_file)['sites']
            return {host for host in (urlparse(site['url']).hostname for site in sites) if host}
        except (OSError, ValueError, KeyError, TypeError):
            return set()

    return set()


def site_host(site):
    """Returns the host of one `sites` entry, which can be a URL, a bare
    host like `www.lowes.com`, or a `{"url": ...}` object. None for anything else."""
    if isinstance(site, dict):
        site = site.get('url')
    if not isinstance(site, str) or any(c in site for c in AMBIGUOUS_URL_CHARACTERS):
        return None
    if '://' not in site:
        site = 'https://' + site
    try:
        return urlparse(site).hostname
    except ValueError:
        return None


def listed_sites(settings_text, settings_key):
    """Returns the hosts in a settings file's `<settings_key>.sites` list. Empty if
    the text is unparseable or has no list, so a broken file adds no hosts rather
    than blocking the others. A bad entry skips only itself."""
    try:
        sites = json.loads(settings_text)[settings_key]['sites']
    except (ValueError, KeyError, TypeError):
        return set()

    if not isinstance(sites, list):
        return set()

    return {host for host in map(site_host, sites) if host}


def listed_sites_in(settings_path, settings_key):
    try:
        with open(settings_path) as settings_file:
            return listed_sites(settings_file.read(), settings_key)
    except OSError:
        return set()


def is_trusted_project(project_dir):
    """Returns True when Claude Code's trust dialog was accepted for project_dir itself."""
    try:
        with open(os.path.expanduser('~/.claude.json')) as config_file:
            projects = json.load(config_file)['projects']
    except (OSError, ValueError, KeyError, TypeError):
        return False

    if not isinstance(projects, dict):
        return False

    # The config keys a project by the path it was opened from, which can differ
    # from the resolved path when it was opened through a symlink. Trust isn't
    # inherited from a parent folder, so a worktree or other folder inside a trusted
    # project doesn't get to add sites from its own settings.
    for directory in {os.path.abspath(project_dir), os.path.realpath(project_dir)}:
        entry = projects.get(directory)
        if isinstance(entry, dict) and entry.get('hasTrustDialogAccepted') is True:
            return True

    return False


def trusted_project_dir():
    """Returns CLAUDE_PROJECT_DIR when its trust dialog has been accepted, else None. The
    hook's cwd isn't used, because it follows the shell's `cd`, so a session could
    otherwise write a list into any directory and move there."""
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR')

    if project_dir and is_trusted_project(project_dir):
        return project_dir

    return None


def same_site_hosts(host):
    """Returns host and its `www.` twin, because search results often link the bare apex of a
    listed `www.` site, which then redirects. No other subdomain counts as the same site."""
    if host.startswith('www.'):
        apex = host[len('www.'):]
        return {host, apex} if '.' in apex and not apex.startswith('www.') else {host}

    return {host, 'www.' + host}


def is_listed_host(host, settings_key):
    """Returns True when host is on the global `<settings_key>.sites` list or on either of
    the trusted project's, read fresh on every call."""
    hosts = same_site_hosts(host)

    if hosts & listed_sites_in(os.path.expanduser('~/.claude/settings.json'), settings_key):
        return True

    project_dir = trusted_project_dir()

    if not project_dir:
        return False

    return any(
        hosts & listed_sites_in(os.path.join(project_dir, name), settings_key)
        for name in (PROJECT_SETTINGS_FILE, PROJECT_LOCAL_SETTINGS_FILE)
    )


def settings_key_for(tool_name):
    """Returns the settings key whose `sites` list pre-authorizes hosts for tool_name's
    server, so a host listed for one server never opens in the other."""
    if tool_name.startswith(BLOCKED_SITE_TOOL_PREFIX):
        return BLOCKED_SITE_SETTINGS_KEY

    if tool_name.startswith(CHROME_DEVTOOLS_TOOL_PREFIXES):
        return CHROME_DEVTOOLS_SETTINGS_KEY

    return None


def file_command_permissions():
    hooks_dir = os.path.dirname(os.path.realpath(__file__))
    module_path = os.path.join(hooks_dir, 'file-command-permissions.py')
    spec = importlib.util.spec_from_file_location('file_command_permissions', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_scratch_file_path(file_path, cwd):
    """Returns True when a `take_snapshot` file can only land in the working directory's own
    `.claude/tmp/`, judged by the rule `file-command-permissions.py` applies to a `>` redirect.

    The checks before that rule close the gaps between how it reads a path and how the MCP
    server writes one. The server resolves a relative path against its own directory, collapses
    `..` as text where the rule follows symlinks, and swaps any extension for `.txt` before it
    writes, so a path that doesn't already end in `.txt` would have its links checked on a name
    that never gets written. The session scratchpad isn't accepted, because the server only
    writes inside its client roots and its own temp directory.

    A link planted between this check and the server's write still redirects the file, the same
    race the redirect rule accepts, because no hook can see what happens after it decides."""
    if not isinstance(file_path, str) or not os.path.isabs(file_path):
        return False

    if any(component in ('.', '..') for component in file_path.split(os.sep)):
        return False

    if os.path.splitext(os.path.basename(file_path))[1] != '.txt':
        return False

    return file_command_permissions().is_scratch_destination(file_path, cwd, include_agent_temp=False)


def emit(decision, reason):
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': decision,
            'permissionDecisionReason': reason,
        }
    }))


def gate_navigation(tool_input, session_id, cwd, tool_name):
    url = tool_input.get('url')

    # navigate_page with type back/forward/reload has no URL and stays within
    # already-visited history; nothing new to gate on the host front, but it
    # still counts as a "safe" call for the session usage gate.
    if not url:
        if not gate_session_usage(session_id):
            emit('allow', 'Navigation stays within current/visited pages')
        return

    # about:blank loads no external content, so it carries none of the
    # prompt-injection risk that gates real hosts; treat it as a safe call.
    if url.strip().lower() == 'about:blank':
        if not gate_session_usage(session_id):
            emit('allow', 'about:blank auto-approved')
        return

    if not isinstance(url, str) or any(c in url for c in AMBIGUOUS_URL_CHARACTERS):
        emit('ask', f"'{url}' isn't a plain http or https URL, so its host can't be checked reliably.")
        return

    parsed_url = urlparse(url)

    if parsed_url.scheme not in ('http', 'https'):
        emit('ask', f"'{url}' isn't a plain http or https URL, so its host can't be checked reliably.")
        return

    host = parsed_url.hostname or ''

    if host and is_local_host(host):
        if not gate_session_usage(session_id):
            emit('allow', f'Local host ({host}) auto-approved')
        return

    if host and host in pre_authorized_hosts(cwd, tool_name):
        if not gate_session_usage(session_id):
            emit('allow', f"{host} is in this project's pre-authorized site matrix")
        return

    settings_key = settings_key_for(tool_name)

    if host and settings_key and is_listed_host(host, settings_key):
        if not gate_session_usage(session_id):
            emit('allow', f'{host} is in a {settings_key}.sites list')
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
        emit('ask', "chrome-mcp-permissions.py couldn't read the tool call, so it could not check it.")
        return

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})
    session_id = data.get('session_id', '')
    cwd = data.get('cwd') or os.getcwd()

    if tool_name.startswith(BLOCKED_SITE_TOOL_PREFIX):
        gate_blocked_site_tool(tool_name, tool_input, session_id, cwd)
        return

    if tool_name.endswith(('navigate_page', 'new_page')):
        gate_navigation(tool_input, session_id, cwd, tool_name)
        return

    if is_chrome_devtools_tool(tool_name):
        gate_session_usage(session_id)


def gate_blocked_site_tool(tool_name, tool_input, session_id, cwd):
    """Allows only the calls in BLOCKED_SITE_ALLOWED_ARGUMENTS, with navigation still
    limited to listed hosts, and prompts for everything else."""
    tool = tool_name[len(BLOCKED_SITE_TOOL_PREFIX):]
    allowed_arguments = BLOCKED_SITE_ALLOWED_ARGUMENTS.get(tool)

    if allowed_arguments is None or not isinstance(tool_input, dict):
        emit('ask', f"{tool_name} isn't on this hook's read-only allowlist.")
        return

    extra_arguments = set(tool_input) - allowed_arguments
    if (tool == 'take_snapshot' and 'filePath' in extra_arguments
            and is_scratch_file_path(tool_input['filePath'], cwd)):
        extra_arguments.discard('filePath')

    if extra_arguments:
        emit('ask', f"{tool_name} with {', '.join(sorted(extra_arguments))} isn't on this hook's read-only allowlist.")
        return

    if tool in ('navigate_page', 'new_page'):
        gate_navigation(tool_input, session_id, cwd, tool_name)
        return

    if not gate_session_usage(session_id):
        emit('allow', f'{tool_name} is on the read-only allowlist')


if __name__ == '__main__':
    # A crash would leave the call to the normal permission flow with no host check,
    # so any error prompts instead.
    try:
        main()
    except Exception as error:
        emit('ask', f'chrome-mcp-permissions.py failed, so it could not check this call: {error!r}')
