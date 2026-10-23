#!/usr/bin/env python3
"""
Allowlist-based curl safety check for PreToolUse hook.

Reads the line through bash_ast, so quoting, escapes, and redirects are resolved the way bash
resolves them, then checks every curl argument against an explicit allowlist of known-safe flags.
Anything not on the allowlist falls through to normal permission handling (existing allow/deny
rules or a user prompt). Nothing is explicitly blocked or denied here, which is also why a line
bash_ast can't parse just falls through.

The line has to be one plain curl command and nothing else: no wrapper, no assignment, no
substitution, and no second command. A trailing `| head`, `| tail`, or `| wc` is the one pipe
that survives, because bash_ast drops it before reporting the line.

GET requests are auto-approved for any domain.
Requests with a body or non-safe HTTP method are auto-approved only for
*.test and localhost (local dev environments).
"""
import json
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import bash_ast
except ImportError:
    bash_ast = None


def is_safe_url(s):
    return s.startswith('http://') or s.startswith('https://')


def is_local_url(url):
    """Returns True for localhost (any port) and *.test domains.

    Uses urlparse().hostname so userinfo cannot spoof the host: curl connects
    to the host after any `user:pass@`, so http://localhost:x@evil.com/ must be
    read as evil.com, not localhost.
    """
    host = urlparse(url).hostname or ''
    return host in ('localhost', '127.0.0.1') or host.endswith('.test')


# Long flags that take no argument.
LONG_NO_ARG = {
    '--silent', '--show-error', '--verbose', '--insecure', '--location',
    '--head', '--include', '--ipv4', '--ipv6', '--compressed', '--fail',
    '--fail-with-body', '--get', '--http1.0', '--http1.1', '--http2',
    '--http2-prior-knowledge', '--http3', '--tlsv1', '--tlsv1.0',
    '--tlsv1.1', '--tlsv1.2', '--tlsv1.3', '--ssl-reqd', '--no-buffer',
    '--no-progress-meter', '--anyauth', '--basic',
    '--digest', '--tcp-nodelay', '--no-keepalive', '--parallel',
    '--progress-bar',
}

# Long flags that take one argument.
# Value is None (any value OK), 'safe_output' (/dev/null or /tmp/),
# 'stdout_or_null' (- or /dev/null only), 'url' (must be http/https),
# 'no_file_ref' (block @filename at start), 'no_at' (block @ anywhere).
LONG_WITH_ARG = {
    '--write-out': None, '--header': None, '--user-agent': None,
    '--output': 'safe_output',
    '--max-time': None, '--connect-timeout': None,
    '--retry': None, '--retry-delay': None, '--retry-max-time': None,
    '--referer': None, '--cookie': None,
    '--noproxy': None,
    '--dns-servers': None, '--interface': None,
    '--user': None, '--limit-rate': None,
    '--cacert': None, '--capath': None, '--cert': None, '--key': None,
    '--url': 'url',
    '--dump-header': 'stdout_or_null',
    '--request': None,
    '--data': 'no_file_ref', '--data-raw': None,
    '--data-binary': 'no_file_ref', '--data-ascii': 'no_file_ref',
    '--data-urlencode': 'no_at',
    '--json': None,
    '--form': 'no_at', '--form-string': None,
}

# Short flags that take no argument (single chars).
SHORT_NO_ARG = set('sSvkLIi46fGNZ')

# Short flags that take one argument, mapped to their long-form key for constraint lookup.
SHORT_WITH_ARG = {
    'w': '--write-out', 'H': '--header', 'A': '--user-agent',
    'o': '--output', 'm': '--max-time', 'e': '--referer',
    'b': '--cookie', 'u': '--user', 'E': '--cert',
    'D': '--dump-header',
    'X': '--request',
    'd': '--data',
    'F': '--form',
}

# HTTP methods that don't modify server state.
SAFE_HTTP_METHODS = {'GET', 'HEAD', 'OPTIONS'}

# Flags that send a request body (implies possible state mutation).
BODY_LONG_FLAGS = {
    '--data', '--data-raw', '--data-binary', '--data-ascii',
    '--data-urlencode', '--json', '--form', '--form-string',
}

# Redirect operators that may appear alongside the curl command, as long as each one is benign:
# `2>&1`, `2>/dev/null`, `>/dev/null`, `&>/dev/null`, and the like. Nothing may write a real file
# or feed curl a file on stdin.
SAFE_REDIRECT_OPS = {'>', '>>', '>|', '&>', '&>>', '>&'}


def value_ok(flag_key, value):
    constraint = LONG_WITH_ARG.get(flag_key)
    if constraint == 'safe_output':
        return value == '/dev/null' or value.startswith('/tmp/') or value.startswith('/private/tmp/')
    if constraint == 'stdout_or_null':
        return value in ('-', '/dev/null')
    if constraint == 'url':
        return is_safe_url(value)
    if constraint == 'no_file_ref':
        return not value.startswith('@')
    if constraint == 'no_at':
        return '@' not in value
    # Cookie from file leaks local cookie data.
    if flag_key == '--cookie' and value.startswith('@'):
        return False
    return True


def check_curl_segment(tokens):
    """
    Validate curl tokens (after the leading 'curl').
    Returns (ok, needs_local, urls):
      ok          - all flags are on the allowlist with valid values
      needs_local - True when a body flag or non-safe HTTP method is present
      urls        - list of URL tokens found in the command
    """
    i = 0
    end_of_flags = False
    needs_local = False
    urls = []

    while i < len(tokens):
        token = tokens[i]

        # After '--', remaining tokens must still be http/https URLs.
        if end_of_flags:
            if not is_safe_url(token):
                return False, False, []
            urls.append(token)
            i += 1
            continue

        if is_safe_url(token):
            urls.append(token)
            i += 1
            continue

        if token == '--':
            end_of_flags = True
            i += 1
            continue

        # Long flag: --flag=value
        if token.startswith('--') and '=' in token:
            flag, value = token.split('=', 1)
            if flag in LONG_WITH_ARG and value_ok(flag, value):
                if flag == '--request' and value.upper() not in SAFE_HTTP_METHODS:
                    needs_local = True
                if flag in BODY_LONG_FLAGS:
                    needs_local = True
                if flag == '--url':
                    urls.append(value)
                i += 1
                continue
            return False, False, []

        # Long flag: --flag [value]
        if token.startswith('--'):
            if token in LONG_NO_ARG:
                i += 1
                continue
            if token in LONG_WITH_ARG:
                if i + 1 >= len(tokens):
                    return False, False, []
                value = tokens[i + 1]
                if not value_ok(token, value):
                    return False, False, []
                if token == '--request' and value.upper() not in SAFE_HTTP_METHODS:
                    needs_local = True
                if token in BODY_LONG_FLAGS:
                    needs_local = True
                if token == '--url':
                    urls.append(value)
                i += 2
                continue
            return False, False, []

        # Short flag(s): -s, -sSL, -sSo /dev/null, -sSo/dev/null
        # curl allows combining short flags; a with-arg flag consumes the
        # rest of the combined token as its value, or the next token if
        # it's the last char.
        if token.startswith('-') and len(token) >= 2:
            chars = token[1:]
            j = 0
            extra = 0
            ok = True
            while j < len(chars):
                c = chars[j]
                if c in SHORT_NO_ARG:
                    j += 1
                elif c in SHORT_WITH_ARG:
                    long_key = SHORT_WITH_ARG[c]
                    remaining = chars[j + 1:]
                    if remaining:
                        value = remaining
                    elif i + 1 < len(tokens):
                        value = tokens[i + 1]
                        extra = 1
                    else:
                        ok = False
                        break
                    if not value_ok(long_key, value):
                        ok = False
                        break
                    if c == 'X' and value.upper() not in SAFE_HTTP_METHODS:
                        needs_local = True
                    if long_key in BODY_LONG_FLAGS:
                        needs_local = True
                    j = len(chars)  # consumed rest of combined token
                else:
                    ok = False
                    break
            if not ok:
                return False, False, []
            i += 1 + extra
            continue

        # Unknown token: not a flag, not an http/https URL, not a redirect.
        return False, False, []

    return True, needs_local, urls


def redirect_ok(redirect):
    if redirect.op not in SAFE_REDIRECT_OPS:
        return False
    # `>&/dev/null` is bash's spelling of `&>/dev/null`, which `Redirect.benign` reads as a dup.
    if redirect.op == '>&' and redirect.target is not None and redirect.target.literal:
        return redirect.benign or redirect.target.value == '/dev/null'
    return redirect.benign


def redirects_ok(redirects):
    return all(redirect_ok(redirect) for redirect in redirects)


def plain_curl(parsed):
    """The curl command's arguments when the line is one plain curl command, else None."""
    if parsed.chain or len(parsed.commands) != 1:
        return None
    command = parsed.commands[0]
    if command.nested or command.wrappers or command.assigns or not command.literal:
        return None
    if not command.words or command.words[0].value != 'curl':
        return None
    if not redirects_ok(command.redirects):
        return None
    return command.argv[1:]


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')
    if not command or bash_ast is None:
        sys.exit(0)

    try:
        parsed = bash_ast.parse(command)
    except bash_ast.ParseError:
        sys.exit(0)

    tokens = plain_curl(parsed)
    if tokens is None:
        sys.exit(0)

    ok, needs_local, urls = check_curl_segment(tokens)
    if not ok:
        sys.exit(0)

    if needs_local and (not urls or not all(is_local_url(u) for u in urls)):
        sys.exit(0)

    reason = 'Local-domain curl auto-approved' if needs_local else 'Safe curl GET auto-approved'
    print(f'{{"hookSpecificOutput": {{"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "{reason}"}}}}')


if __name__ == '__main__':
    main()
