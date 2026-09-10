#!/usr/bin/env python3
"""
Auto-approves CLI subcommands that appear on a per-command allowlist, and forces a prompt for
every other invocation of a covered command. Lines that never mention a covered command exit
silently, so `settings.json` rules apply to them normally. A few shapes are denied outright
rather than prompted: a VIP target named any way other than a single leading `@org.env` token,
a covered binary at a path outside `BINARY_ALLOWED_PATHS`, and a line that chains a second
command with `;`, `&`, `|`, or a newline, where splitting it into one call per command is a fix
the caller can always apply. Add a new CLI by adding an entry to COMMANDS; nothing else needs to
change.

The scanning behind that last one lives in `shell_line_shapes`, shared with
`file-command-permissions.py` so the two cannot disagree about how bash reads a line. It also
supplies the one exemption: a redirect to `/dev/null` or a file descriptor.

Most entries are prefix matches. `WP_VALIDATED` holds the ones where the arguments after the
subcommand decide whether it's safe, which a prefix can't express.

This hook is the SOLE permission authority for the commands it covers, because a `settings.json`
`ask` rule would override its `allow`. See the "Command allowlist hooks" section of
`claude/CLAUDE.md` for which rules were removed to make that true, and what to restore if this
hook is ever dropped.

Won't work for WP-CLI if `mcp__local-wp__wp_cli` is in `permissions.allow`. Keep it out of there.
"""
import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import shell_line_shapes
except ImportError as _import_error:
    # A traceback would exit non-zero, which Claude Code reads as "no opinion", dropping every
    # command this hook covers to the auto-mode classifier. Prompting instead fails closed, the
    # same way the catch-all at the bottom of this file does.
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'ask',
            'permissionDecisionReason': (
                f'shell_line_shapes failed to load, so this hook cannot vouch for the '
                f'command: {_import_error}'
            ),
        }
    }))
    sys.exit(0)

ALLOW = 'allow'
ASK = 'ask'
DENY = 'deny'

BENIGN_REDIRECT = shell_line_shapes.BENIGN_REDIRECT

STRIP_REDIRECT = shell_line_shapes.STRIP_REDIRECT

# Tools that reach a binary without a shell in between, so the metacharacter guard has nothing to
# defend and is skipped for them. Local WP's `localwp-agent-tools` addon splits its `args` string
# with its own parser and passes the resulting array to Node's `execFile`, which takes an argv
# directly -- see `lib/tools/wpcli.js` in that addon. Parens, `;`, and `$()` are inert there, and
# leaving the guard on blocked every SQL query with a function call in it. Anything added here
# must be verified the same way: an argv-taking call with no shell, checked in the code that runs.
SHELL_FREE_TOOLS = frozenset({'mcp__local-wp__wp_cli'})

# VIP environments whose data is disposable enough to auto-approve reads and writes against.
# Deliberately conservative: production is absent by design, and so is every environment not
# listed, because an unrecognized target is not a safe one.
VIP_SAFE_ENVIRONMENTS = frozenset({'develop', 'staging', 'staging.wpvip-publix-staging', 'preprod'})

# Flags that suppress VIP's own confirmation prompt. Their entire purpose is removing a
# safety check, so their presence disqualifies a command however safe its subcommand looks.
VIP_CONFIRMATION_FLAGS = frozenset({'-y', '--yes'})

# The one accepted way to name a VIP target is a single `@org.env` token before the subcommand.
# These flags are the other ways, and they're denied outright: allowing two spellings on one line
# would mean guessing which one VIP honors, and a wrong guess aims an auto-approved command at
# production. `claude/rules/running-commands.md` records the canonical format.
VIP_FORBIDDEN_TARGET_FLAGS = frozenset({'-a', '--app', '-e', '--env'})

# VIP global flags that don't affect targeting, consumed while looking for the real subcommand.
VIP_CONSUMABLE_FLAGS = frozenset({'-d', '--debug'})

# Flags that stand in for a subcommand rather than modifying one, so the walk stops on them and
# hands them to the allowlist.
VIP_TERMINAL_FLAGS = frozenset({'-h', '--help', '-v', '--version'})

# WP-CLI global flags may precede the subcommand, and the Local WP MCP server puts `--url=` there,
# so they're stepped over to reach the subcommand the allowlist is written against.
WP_SKIPPABLE_GLOBAL_FLAGS = frozenset({
    '--allow-root',
    '--blog',
    '--color',
    '--debug',
    '--no-color',
    '--path',
    '--quiet',
    '--skip-packages',
    '--skip-plugins',
    '--skip-themes',
    '--url',
    '--user',
})

# WP-CLI globals that load or run arbitrary code, or retarget the command at another machine
# (`--ssh` and `--http` are both remote transports). No subcommand is safe enough to outweigh
# one of these.
WP_DISQUALIFYING_GLOBAL_FLAGS = frozenset({'--context', '--exec', '--http', '--require', '--ssh'})

# Flags the allowlist itself covers, so the global-flag walk must hand them over instead of
# stepping past them.
WP_TERMINAL_FLAGS = frozenset({'--info', '--version'})

# The statements `wp db query` may run without a prompt. Anchoring at the first keyword means a
# leading comment fails too, so `/*x*/ DELETE ...` can't hide behind one. A parenthesized query
# or a CTE fails as well; both are read-only in practice, but recognizing them would mean parsing
# SQL rather than matching its opening word.
READ_ONLY_SQL_START = re.compile(r'\s*(?:select|show|describe|desc|explain)\b', re.IGNORECASE)

# What turns a nominally read-only statement into something else. `INTO` catches
# `SELECT ... INTO OUTFILE`, which writes a file wherever the database user can reach;
# `LOAD_FILE` reads one back into the output. `ANALYZE` matters because `EXPLAIN ANALYZE` runs the
# statement it's given rather than just planning it, and MySQL 8 accepts a `DELETE` there. A `;`
# would let a second statement ride along, because mysql runs every statement in the string it's
# handed.
FORBIDDEN_SQL_PATTERNS = (
    re.compile(r';'),
    re.compile(r'\binto\b', re.IGNORECASE),
    re.compile(r'\bload_file\b', re.IGNORECASE),
    re.compile(r'\banalyze\b', re.IGNORECASE),
)

# The flags `wp db query` may carry. WP-CLI hands assoc args it doesn't recognize to mysql, so an
# unlisted flag could smuggle in a second statement (`--execute=`) or a config file that runs one
# (`--init-command=`, `--defaults-file=`). The list is closed for that reason, and holds mysql's
# output formatting flags plus WP-CLI's own globals, which are safe after the subcommand as well
# as before it.
WP_DB_QUERY_ALLOWED_FLAGS = WP_SKIPPABLE_GLOBAL_FLAGS | frozenset({
    '--batch',
    '--column-names',
    '--html',
    '--silent',
    '--skip-column-names',
    '--table',
    '--vertical',
    '--xml',
})

WP_ALLOWED = [
    '--info',
    '--version',
    'akismet status',
    'cache flush',
    'cache get',
    'cache stats',
    'cap list',
    'cli info',
    'cli version',
    'comment count',
    'comment get',
    'comment list',
    'config get',
    'config list',
    'core check-update',
    'core update',
    'core update-db',
    'core version',
    'cron event list',
    'cron schedule list',
    'db check',
    'db size',
    'db tables',
    'elasticpress index',
    'elasticpress list-features',
    'elasticpress stats',
    'elasticpress status',
    'embed provider list',
    'help',
    'jetpack module list',
    'jetpack status',
    'language is-installed',
    'language list',
    'maintenance-mode status',
    'media image-size',
    'menu list',
    'menu location list',
    'network meta get',
    'network meta list',
    'network meta pluck',
    'option add',
    'option delete',
    'option get',
    'option list',
    'option update',
    'package list',
    'plugin active-on-sites',
    'plugin get',
    'plugin is-active',
    'plugin is-installed',
    'plugin list',
    'plugin update',
    'post create',
    'post get',
    'post list',
    'post meta get',
    'post meta list',
    'post term list',
    'post-type get',
    'post-type list',
    'rewrite flush',
    'rewrite list',
    'role get',
    'role list',
    'sidebar list',
    'site list',
    'site option get',
    'site option list',
    'site url',
    'taxonomy get',
    'taxonomy list',
    'term get',
    'term list',
    'term meta get',
    'theme get',
    'theme is-active',
    'theme is-installed',
    'theme list',
    'theme update',
    'transient delete update_plugins',
    'transient delete update_themes',
    'transient get',
    'user get',
    'user list',
    'user meta get',
    'vip-search index',
    'widget list',
]

# VIP-CLI's own subcommands, as opposed to the WP-CLI it proxies. Reads only -- `db`, `backup`,
# `export`, `import`, and `sync` move real data around and belong behind a prompt.
VIP_NATIVE_ALLOWED = [
    '-h',
    '-v',
    '--help',
    '--version',
    'app list',
    'config envvar list',
    'config software get',
    'help',
    'logs',
    'slowlogs',
    'whoami',
]

# The exact binary spellings this hook will vouch for. Resolving by basename alone would treat
# any executable named `wp` at any path as WP-CLI, so an unlisted path is denied instead --
# the deny reason names this constant so the block is visible in the session.
BINARY_ALLOWED_PATHS = {
    'wp': 'wp',
    'vip': 'vip',
    '/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/posix/wp': 'wp',
}

COMMANDS = {
    'wp': {
        'allowed': WP_ALLOWED,
        'normalizer': 'wp',
    },
    'vip': {
        'allowed': VIP_NATIVE_ALLOWED,
        'normalizer': 'vip',
        # After VIP's target and global flags are consumed, a `wp` subcommand is plain WP-CLI, so
        # it reuses that allowlist rather than duplicating it.
        'delegates': {'wp': WP_ALLOWED},
    },
}


# Matches a covered command name as its own shell word. The name has to end where a word bash is
# about to run can end -- whitespace, a metacharacter, a quote, or a `$`/`\` that the shell
# resolves before running it -- so `/bin/wp`, `wp option`, `x&&wp`, `wp$X`, and a fully quoted
# `"/Applications/.../wp" post list` all read as mentions, while `wp-content`, `wp/v2/media`, and
# `wp:featuredmedia` are just text. A name reached through a path separator still counts, because
# `/bin/wp` needs it to.
COVERED_COMMAND_MENTION = re.compile(
    r'(?<![\w-])(?:' + '|'.join(re.escape(name) for name in COMMANDS) + r')(?=[\s;&|()<>"\'`$\\]|$)'
)


def no_opinion():
    """Exit without printing a decision, so `settings.json` rules apply normally.

    The `if` filters that scope this hook to `wp`/`vip` lines fail open on shell lines Claude
    Code can't decompose -- redirects, `$` expansion, `for` loops -- so the hook also runs on
    `jq`, `curl` loops, and anything else compound. Answering `ask` for those turned every such
    line into a prompt; staying silent hands them back to the permission system untouched.
    """
    sys.exit(0)


def respond(decision, reason):
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': decision,
            'permissionDecisionReason': reason,
        }
    }))
    sys.exit(0)


def shell_metacharacter_decision(raw):
    """Return (decision, reason) when bash might run more than the matched prefix, or None.

    A chaining operator is refused outright rather than prompted, because the agent that wrote
    it always has a mechanical fix: send each command as its own tool call. Everything else --
    an expansion, a redirect to a real file, a subshell, a line that can't be read to the end --
    still prompts, because there's no rewrite to point the agent at.
    """
    finding = shell_line_shapes.first_operator(raw)
    if finding is None:
        return None

    kind, description = finding
    if kind == shell_line_shapes.CHAIN:
        return DENY, (
            f'{description}, so a prefix match cannot vouch for this command. Send each command '
            'as its own tool call (running-commands.md); do not reword the line to get past this.'
        )
    return ASK, (
        f'{description}, so a prefix match cannot vouch for this command. Send one bare command '
        'per call (running-commands.md); split a chain or drop a redirect rather than rewording '
        'to get past this hook.'
    )


def matched_prefix(tokens, allowed):
    """Return the allowlist entry whose tokens lead `tokens`, or None.

    Compares token by token so `post lists` doesn't ride in on `post list`.
    """
    for prefix in allowed:
        prefix_tokens = prefix.split()
        if tokens[:len(prefix_tokens)] == prefix_tokens:
            return prefix
    return None


def validate_db_query(tokens, raw):
    """Decide a `wp db query` invocation, where the SQL and the flags are what make it safe.

    `tokens` starts at `db`; `raw` is the whole command line. Exactly one positional argument is
    required: with no SQL at all, `wp db query` reads a statement from stdin, and with more than
    one there's no single thing to check.
    """
    arguments = tokens[2:]
    flags = [argument for argument in arguments if argument.startswith('-')]
    statements = [argument for argument in arguments if not argument.startswith('-')]

    if len(statements) != 1:
        return ASK, 'wp db query needs exactly one SQL argument for this hook to check'

    for flag in flags:
        if flag.partition('=')[0] not in WP_DB_QUERY_ALLOWED_FLAGS:
            return ASK, f'"{flag}" is not an allowlisted wp db query flag'

    if not READ_ONLY_SQL_START.match(statements[0]):
        return ASK, 'wp db query SQL does not start with a read-only statement'

    # Searched against the whole command line rather than the parsed statement, because this
    # hook's `shlex` parse and the Local WP addon's own argument splitter disagree over
    # backslashes, and a raw-string search can't be fooled by that disagreement. The `;` pattern
    # is the only thing catching a second statement, since a quoted `;` clears the metacharacter
    # guard on the Bash path and no guard runs at all on a shell-free one.
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if pattern.search(raw):
            return ASK, f'wp db query matches "{pattern.pattern}", so it may not be read-only'

    return ALLOW, '"wp db query" is allowlisted for read-only SQL'


# Allowlist entries a prefix match can't express, keyed the same way so `matched_prefix` finds
# them. Consulted before the prefix lists, and shared by the VIP delegate path.
WP_VALIDATED = {
    'db query': validate_db_query,
}


def match_wp_allowlist(subcommand_tokens, allowed, raw):
    """Return a (decision, reason) pair for WP-CLI subcommand tokens, or None if nothing matched."""
    validated = matched_prefix(subcommand_tokens, WP_VALIDATED)
    if validated:
        return WP_VALIDATED[validated](subcommand_tokens, raw)

    prefix = matched_prefix(subcommand_tokens, allowed)
    if prefix:
        # WP-CLI honors `--exec`, `--require`, `--ssh`, and `--http` wherever they sit, not just
        # ahead of the subcommand, so a prefix match has to rule them out across the whole line
        # rather than trusting `normalize_wp` to have caught them among the leading flags.
        for token in subcommand_tokens:
            flag = token.partition('=')[0]
            if flag in WP_DISQUALIFYING_GLOBAL_FLAGS:
                return ASK, f'"{flag}" can run arbitrary code or retarget the command'
        return ALLOW, f'"wp {prefix}" is allowlisted'
    return None


def normalize_vip(tokens):
    """Split a VIP invocation into (subcommand_tokens, environment, violation).

    VIP's real subcommand sits behind an optional target and global flags, and the `--` before it
    is optional in practice: `vip @app.staging wp post list` and `vip @app.staging -- wp post list`
    are both common. Walking the tokens is the only way to find the subcommand in every shape.

    The target must be a single `@org.env` token before the subcommand. Any other targeting
    spelling -- an `-e`/`-a` flag, a second `@` token, an `@` token after the subcommand -- sets
    `violation` and the command is denied, because two target spellings on one line would leave
    the hook guessing which one VIP honors.

    Returns `None` for the subcommand when the invocation isn't a shape this can parse.
    """
    at_tokens = [token for token in tokens if token.startswith('@')]
    if len(at_tokens) > 1:
        return None, None, 'more than one @ target on the line'

    for token in tokens:
        if token.partition('=')[0] in VIP_FORBIDDEN_TARGET_FLAGS:
            return None, None, f'target named with "{token}" instead of a single @org.env token'

    environment = None
    target_consumed = False
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token == '--':
            index += 1
            break

        if token in VIP_CONFIRMATION_FLAGS or token in VIP_CONSUMABLE_FLAGS:
            index += 1
            continue

        if token in VIP_TERMINAL_FLAGS:
            break

        if token.startswith('@'):
            _, separator, environment_part = token[1:].partition('.')
            environment = environment_part if separator else None
            target_consumed = True
            index += 1
            continue

        if token.startswith('-'):
            return None, environment, None

        break

    if at_tokens and not target_consumed:
        # The lone @ token sits after the subcommand, where this walk can't vouch for how VIP
        # interprets it.
        return None, None, 'the @ target must come before the subcommand'

    return tokens[index:], environment, None


def normalize_wp(tokens):
    """Step over leading WP-CLI global flags. Returns (subcommand_tokens, disqualifying_flag)."""
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if token in WP_TERMINAL_FLAGS or not token.startswith('--'):
            break

        flag = token.partition('=')[0]
        if flag in WP_DISQUALIFYING_GLOBAL_FLAGS:
            return tokens[index:], flag
        if flag not in WP_SKIPPABLE_GLOBAL_FLAGS:
            break

        index += 1

    return tokens[index:], None


def decide_wp(tokens, config, raw):
    subcommand_tokens, disqualifying_flag = normalize_wp(tokens)

    if disqualifying_flag:
        return ASK, f'"{disqualifying_flag}" can run arbitrary code or retarget the command'

    outcome = match_wp_allowlist(subcommand_tokens, config['allowed'], raw)
    if outcome:
        return outcome
    return ASK, 'wp command is not allowlisted'


def decide_vip(tokens, config, raw):
    """Decide a VIP invocation, gating on the environment before the subcommand allowlist."""
    subcommand_tokens, environment, violation = normalize_vip(tokens)

    if violation:
        return DENY, f'{violation} -- name VIP targets with a single leading @org.env token'

    if subcommand_tokens is None or not subcommand_tokens:
        return ASK, 'VIP command is not a shape this hook recognizes'

    # Checked across the whole line rather than just the leading flags, because a confirmation
    # flag disqualifies the command wherever it sits.
    if VIP_CONFIRMATION_FLAGS.intersection(tokens):
        return ASK, 'VIP command suppresses its own confirmation prompt'

    if environment is not None and environment not in VIP_SAFE_ENVIRONMENTS:
        return ASK, f'VIP environment "{environment}" is not on the safe list'

    delegate = config.get('delegates', {}).get(subcommand_tokens[0])
    if delegate is not None:
        # A delegated command reaches a real environment, so an unnamed target can't be assumed
        # to be a local one.
        if environment is None:
            return ASK, 'VIP command targets no explicit environment'

        proxied_tokens, disqualifying_flag = normalize_wp(subcommand_tokens[1:])
        if disqualifying_flag:
            return ASK, f'"{disqualifying_flag}" can run arbitrary code or retarget the command'

        outcome = match_wp_allowlist(proxied_tokens, delegate, raw)
        if outcome:
            decision, reason = outcome
            if decision == ALLOW:
                reason = f'{reason}, on VIP environment "{environment}"'
            return decision, reason
        return ASK, 'proxied WP-CLI command is not allowlisted'

    prefix = matched_prefix(subcommand_tokens, config['allowed'])
    if prefix:
        return ALLOW, f'VIP command "{prefix}" is allowlisted'
    return ASK, 'VIP command is not allowlisted'


NORMALIZERS = {
    'wp': decide_wp,
    'vip': decide_vip,
}


def decide(base_command, tokens, raw):
    config = COMMANDS[base_command]

    normalizer = NORMALIZERS.get(config.get('normalizer'))
    if normalizer:
        return normalizer(tokens, config, raw)

    prefix = matched_prefix(tokens, config['allowed'])
    if prefix:
        return ALLOW, f'"{base_command} {prefix}" is allowlisted'
    return ASK, f'{base_command} command is not allowlisted'


def resolve_base_command(tokens):
    """Return (base_command, remaining_tokens, denial_reason), stripping a `command` prefix.

    Only the exact spellings in `BINARY_ALLOWED_PATHS` resolve. A different path to a binary
    whose basename matches a covered command is denied rather than trusted -- anything on disk
    can be named `wp`.
    """
    if tokens and tokens[0] == 'command':
        tokens = tokens[1:]
    if not tokens:
        return None, [], None

    spelling = tokens[0]
    base_command = BINARY_ALLOWED_PATHS.get(spelling)
    if base_command:
        return base_command, tokens[1:], None

    if Path(spelling).name in COMMANDS:
        return None, tokens[1:], (
            f'"{spelling}" is not in BINARY_ALLOWED_PATHS in command-allowlist-permissions.py, '
            'so this hook cannot vouch for the binary behind it'
        )

    return None, tokens[1:], None


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get('tool_input', {})
    shell_free = payload.get('tool_name') in SHELL_FREE_TOOLS

    # The Local WP MCP server passes the WP-CLI arguments alone; the Bash tool passes the whole
    # command line, binary included.
    raw_arguments = tool_input.get('args')
    raw_command = tool_input.get('command')
    raw = raw_arguments if raw_arguments else raw_command
    if not raw:
        if raw_arguments is not None:
            respond(ASK, 'no command found in the tool input')
        no_opinion()

    # This must run before the metacharacter guard: a compound line that never mentions a covered
    # command isn't this hook's to judge, but one that does mention `wp`/`vip` must still hit the
    # guard, or a rider like `wp option get x && wp db reset` slips past on the safe prefix.
    if not raw_arguments and not COVERED_COMMAND_MENTION.search(raw):
        no_opinion()

    if not shell_free:
        metacharacter_decision = shell_metacharacter_decision(raw)
        if metacharacter_decision:
            respond(*metacharacter_decision)

    # On the shell path the guard has already confirmed every redirect targets `/dev/null` or an
    # fd, so dropping them leaves the argv `wp` actually receives. The MCP path has no shell, so
    # its `args` are passed verbatim and nothing is stripped.
    command_for_tokens = raw if raw_arguments else STRIP_REDIRECT.sub(' ', raw)

    try:
        tokens = shlex.split(command_for_tokens)
    except ValueError:
        respond(ASK, 'command could not be parsed into arguments')

    if raw_arguments:
        base_command = 'wp'
    else:
        base_command, tokens, denial_reason = resolve_base_command(tokens)
        if denial_reason:
            respond(DENY, denial_reason)

    if base_command is None:
        # A covered command sitting behind a launcher (`env wp db reset`, `VAR=1 vip ...`) is
        # still an execution this hook can't vouch for, so it gets a prompt. A covered name
        # inside a larger token (`grep 'wp option' notes.txt`) is just data.
        if any(token in BINARY_ALLOWED_PATHS for token in tokens):
            respond(ASK, 'a covered command sits behind a launcher this hook cannot vouch for')
        no_opinion()

    respond(*decide(base_command, tokens, raw))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:
        # Failing closed matters more than a useful error, because this hook is the only thing
        # standing between these commands and the auto-mode classifier.
        respond(ASK, f'permission hook errored, so it cannot vouch for this command: {error}')
