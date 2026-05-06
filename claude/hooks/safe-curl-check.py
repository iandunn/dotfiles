#!/usr/bin/env python3
"""
Allowlist-based curl safety check for PreToolUse hook.

Uses shlex.split() for reliable tokenization (handles quotes, escapes,
combined short flags), then checks every token against an explicit
allowlist of known-safe flags. Anything not on the allowlist falls
through to normal permission handling (existing allow/deny rules or
a user prompt). Nothing is explicitly blocked or denied here.
"""
import json
import shlex
import sys


def is_safe_url(s):
    return s.startswith('http://') or s.startswith('https://')


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
# Value is None (any value OK), '/dev/null' (must equal that),
# 'stdout_or_null' (- or /dev/null only), or 'url' (must be http/https).
LONG_WITH_ARG = {
    '--write-out': None, '--header': None, '--user-agent': None,
    '--output': '/dev/null',
    '--max-time': None, '--connect-timeout': None,
    '--retry': None, '--retry-delay': None, '--retry-max-time': None,
    '--referer': None, '--cookie': None,
    '--noproxy': None,
    '--dns-servers': None, '--interface': None,
    '--user': None, '--limit-rate': None,
    '--cacert': None, '--capath': None, '--cert': None, '--key': None,
    '--url': 'url',
    '--dump-header': 'stdout_or_null',
}

# Short flags that take no argument (single chars).
SHORT_NO_ARG = set('sSvkLIi46fGNZ')

# Short flags that take one argument, mapped to their long-form key for constraint lookup.
SHORT_WITH_ARG = {
    'w': '--write-out', 'H': '--header', 'A': '--user-agent',
    'o': '--output', 'm': '--max-time', 'e': '--referer',
    'b': '--cookie', 'u': '--user', 'E': '--cert',
    'D': '--dump-header',
}

# Shell redirect tokens that may appear alongside the curl command.
SAFE_REDIRECTS = {'2>&1', '2>/dev/null', '>/dev/null', '1>/dev/null', '>&/dev/null'}

# Read-only text-processing commands allowed after a pipe.
SAFE_PIPE_CMDS = {
    'head', 'tail', 'grep', 'egrep', 'fgrep', 'cat',
    'wc', 'sort', 'uniq', 'cut', 'tr', 'jq',
}


def value_ok(flag_key, value):
    constraint = LONG_WITH_ARG.get(flag_key)
    if constraint == '/dev/null':
        return value == '/dev/null'
    if constraint == 'stdout_or_null':
        return value in ('-', '/dev/null')
    if constraint == 'url':
        return is_safe_url(value)
    # Cookie from file leaks local cookie data.
    if flag_key == '--cookie' and value.startswith('@'):
        return False
    return True


def check_curl_segment(tokens):
    """Validate curl tokens (after the leading 'curl'). Returns True if safe."""
    i = 0
    end_of_flags = False

    while i < len(tokens):
        token = tokens[i]

        if token in SAFE_REDIRECTS:
            i += 1
            continue

        # After '--', remaining tokens must still be http/https URLs.
        if end_of_flags:
            if not is_safe_url(token):
                return False
            i += 1
            continue

        if is_safe_url(token):
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
                i += 1
                continue
            return False

        # Long flag: --flag [value]
        if token.startswith('--'):
            if token in LONG_NO_ARG:
                i += 1
                continue
            if token in LONG_WITH_ARG:
                if i + 1 >= len(tokens):
                    return False
                if not value_ok(token, tokens[i + 1]):
                    return False
                i += 2
                continue
            return False

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
                    j = len(chars)  # consumed rest of combined token
                else:
                    ok = False
                    break
            if not ok:
                return False
            i += 1 + extra
            continue

        # Unknown token: not a flag, not an http/https URL, not a redirect.
        return False

    return True


def check_pipe_segment(tokens):
    """Validate a post-pipe segment. Only read-only text-processing commands are allowed."""
    if not tokens:
        return True
    return tokens[0] in SAFE_PIPE_CMDS


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')

    try:
        tokens = shlex.split(command)
    except ValueError:
        sys.exit(0)

    if not tokens or tokens[0] != 'curl':
        sys.exit(0)

    # Split token list on '|' into pipe segments.
    segments = []
    current = []
    for token in tokens:
        if token == '|':
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)

    curl_segment = segments[0]
    if not curl_segment or curl_segment[0] != 'curl':
        sys.exit(0)

    if not check_curl_segment(curl_segment[1:]):
        sys.exit(0)

    for segment in segments[1:]:
        if not check_pipe_segment(segment):
            sys.exit(0)

    print('{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "Read-only curl auto-approved"}}')


if __name__ == '__main__':
    main()
