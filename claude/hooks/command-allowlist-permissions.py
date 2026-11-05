#!/usr/bin/env python3
"""
Auto-approves CLI subcommands that appear on a per-command allowlist, and forces a prompt for
every other invocation of a covered command. Lines that never run a covered command exit
silently, so `settings.json` rules apply to them normally. A few shapes are denied outright
rather than prompted: a VIP target named any way other than a single leading `@org.env` token,
a covered binary at a path outside `BINARY_ALLOWED_PATHS`, and a line that runs a covered command
alongside another one with `;`, `&`, `|`, a newline, or a compound command, where splitting it
into one call per command is a fix the caller can always apply. Add a new CLI by adding an entry
to COMMANDS; nothing else needs to change.

Reading the line is `bash_ast`'s job, which asks shfmt for the syntax tree and reports every
command the line can run, wherever it's nested, with wrappers like `env` and `bash -c` peeled
off. This hook only applies policy to what that reports. A pipeline ending in `head`, `tail`, or
`wc` is judged as the command feeding it, and a redirect to `/dev/null` or a file descriptor
doesn't count against a command.

Most entries are prefix matches. `WP_VALIDATED` holds the ones where the arguments after the
subcommand decide whether it's safe, which a prefix can't express.

This hook is the SOLE permission authority for the commands it covers, because a `settings.json`
`ask` rule would override its `allow`. See the "Command allowlist hooks" section of
`claude/hooks/README.md` for which rules were removed to make that true, and what to restore if
this hook is ever dropped.

Won't work for WP-CLI if `mcp__local-wp__wp_cli` is in `permissions.allow`. Keep it out of there.

The `mcp__local-wp__wp_cli` path is kept even while Local's Agent Tools add-on is disabled, so
re-enabling the add-on doesn't expose its WP-CLI tool without this allowlist in front of it. Keep
it, and its `settings.json` matcher, unless the add-on is removed for good.
"""
import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import bash_ast
except ImportError as _import_error:
    # A traceback would exit non-zero, which Claude Code reads as "no opinion", dropping every
    # command this hook covers to the auto-mode classifier. Prompting instead fails closed, the
    # same way the catch-all at the bottom of this file does.
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'ask',
            'permissionDecisionReason': (
                f'bash_ast failed to load, so this hook cannot vouch for the '
                f'command: {_import_error}'
            ),
        }
    }))
    sys.exit(0)

ALLOW = 'allow'
ASK = 'ask'
DENY = 'deny'

# Tools that reach a binary without a shell in between, so there's no shell line to parse and their
# arguments are split as a plain argv instead. Local WP's `localwp-agent-tools` addon splits its
# `args` string with its own parser and passes the resulting array to Node's `execFile`, which
# takes an argv directly -- see `lib/tools/wpcli.js` in that addon. Parens, `;`, and `$()` are
# inert there, and treating them as shell blocked every SQL query with a function call in it.
# Anything added here must be verified the same way: an argv-taking call with no shell, checked in
# the code that runs.
SHELL_FREE_TOOLS = frozenset({'mcp__local-wp__wp_cli'})

# VIP environments where reads are safe to auto-approve. Writes never are on any VIP environment,
# since every one is remote, which is why the `vip` delegate gets only `WP_READ_ALLOWED`.
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
    '--quiet',
    '--skip-packages',
    '--skip-plugins',
    '--skip-themes',
    '--url',
    '--user',
})

# WP-CLI globals that load or run arbitrary code, or retarget the command at another machine
# (`--ssh` and `--http` are both remote transports). `--path` belongs here too, because WP-CLI
# runs the `wp-config.php` it finds there, and that can be a file anyone with write access to the
# project planted. No subcommand is safe enough to outweigh one of these.
WP_DISQUALIFYING_GLOBAL_FLAGS = frozenset({
    '--context',
    '--exec',
    '--http',
    '--path',
    '--require',
    '--ssh',
})

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

# WP-CLI subcommands that only read, so they're allowed against a local site and against a VIP
# environment on `VIP_SAFE_ENVIRONMENTS`. Production always prompts.
WP_READ_ALLOWED = [
    '--info',
    '--version',
    'akismet status',
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
    'core version',
    'cron event list',
    'cron schedule list',
    'db check',
    'db prefix',
    'db size',
    'db tables',
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
    'option get',
    'option list',
    'option pluck',
    'package list',
    'plugin active-on-sites',
    'plugin get',
    'plugin is-active',
    'plugin is-installed',
    'plugin list',
    'post get',
    'post list',
    'post meta get',
    'post meta list',
    'post meta pluck',
    'post term list',
    'post-type get',
    'post-type list',
    'publix petition-load-test count',
    'publix petition-load-test time-count',
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
    'transient get',
    'user get',
    'user list',
    'user meta get',
    'widget list',
]

# WP-CLI reads that are allowed only against a local site. `user meta list` dumps every meta row at
# once, including session tokens, application password hashes, and 2FA secrets, so on a VIP
# environment it prompts.
WP_LOCAL_READ_ALLOWED = [
    'user meta list',
]

# WP-CLI subcommands that change the site. They're allowed only against a local site, through
# `wp` or `localwp`, because a local database is disposable. Against any VIP environment, staging
# and preprod included, they prompt.
WP_LOCAL_WRITE_ALLOWED = [
    'cache flush',
    'core update',
    'core update-db',
    'elasticpress index',
    'option add',
    'option delete',
    'option patch update',
    'option update',
    'plugin update',
    'post create',
    'post meta update',
    'post update',
    'publix petition-load-test seed',
    'rewrite flush',
    'theme update',
    'transient delete update_plugins',
    'transient delete update_themes',
    'vip-search index',
]

WP_LOCAL_ALLOWED = WP_READ_ALLOWED + WP_LOCAL_READ_ALLOWED + WP_LOCAL_WRITE_ALLOWED

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

# Read-only `gh` and `glab` subcommands, each mapped to the flags it may carry. A flag off its list
# prompts, which keeps out `--web` (it opens a browser), `--show-token`, `--watch`, and whatever a
# newer release adds. `-R`/`--repo` is checked separately, since it can sit anywhere on the line.
GH_OUTPUT_FLAGS = frozenset({'-q', '--jq', '--json', '-t', '--template'})
GH_SEARCH_FLAGS = GH_OUTPUT_FLAGS | frozenset({
    '-B', '-H', '-L', '--app', '--archived', '--assignee', '--author', '--author-date',
    '--author-email', '--author-name', '--base', '--checks', '--closed', '--commenter',
    '--comments', '--committer', '--committer-date', '--committer-email', '--committer-name',
    '--created', '--draft', '--extension', '--filename', '--followers', '--forks',
    '--good-first-issues', '--hash', '--head', '--help-wanted-issues', '--include-forks',
    '--include-prs', '--interactions', '--involves', '--label', '--language', '--license',
    '--limit', '--locked', '--match', '--mentions', '--merge', '--merged', '--merged-at',
    '--milestone', '--no-assignee', '--no-label', '--no-milestone', '--no-project',
    '--number-topics', '--order', '--owner', '--parent', '--project', '--reactions', '--review',
    '--review-requested', '--reviewed-by', '--size', '--sort', '--stars', '--state',
    '--team-mentions', '--topic', '--tree', '--updated', '--visibility',
})
GH_READ_ALLOWED = {
    'auth status': frozenset({
        '-a', '-h', '--active', '--hostname', '--jq', '--json', '--template',
    }),
    'issue list': GH_OUTPUT_FLAGS | frozenset({
        '-a', '-A', '-l', '-L', '-m', '-S', '-s', '--app', '--assignee', '--author', '--label',
        '--limit', '--mention', '--milestone', '--search', '--state',
    }),
    'issue status': GH_OUTPUT_FLAGS,
    'issue view': GH_OUTPUT_FLAGS | frozenset({'-c', '--comments'}),
    'label list': GH_OUTPUT_FLAGS | frozenset({
        '-L', '-S', '--limit', '--order', '--search', '--sort',
    }),
    'pr checks': GH_OUTPUT_FLAGS | frozenset({'--fail-fast', '--required'}),
    'pr diff': frozenset({'--color', '--name-only', '--patch'}),
    'pr list': GH_OUTPUT_FLAGS | frozenset({
        '-a', '-A', '-B', '-d', '-H', '-l', '-L', '-S', '-s', '--app', '--assignee', '--author',
        '--base', '--draft', '--head', '--label', '--limit', '--search', '--state',
    }),
    'pr status': GH_OUTPUT_FLAGS | frozenset({'-c', '--conflict-status'}),
    'pr view': GH_OUTPUT_FLAGS | frozenset({'-c', '--comments'}),
    'release list': GH_OUTPUT_FLAGS | frozenset({
        '-L', '-O', '--exclude-drafts', '--exclude-pre-releases', '--limit', '--order',
    }),
    'release view': GH_OUTPUT_FLAGS,
    'repo list': GH_OUTPUT_FLAGS | frozenset({
        '-l', '-L', '--archived', '--fork', '--language', '--limit', '--no-archived', '--source',
        '--topic', '--visibility',
    }),
    'repo view': GH_OUTPUT_FLAGS | frozenset({'-b', '--branch'}),
    'run list': GH_OUTPUT_FLAGS | frozenset({
        '-a', '-b', '-c', '-e', '-L', '-s', '-u', '-w', '--all', '--branch', '--commit',
        '--created', '--event', '--limit', '--status', '--user', '--workflow',
    }),
    'run view': GH_OUTPUT_FLAGS | frozenset({
        '-a', '-j', '-v', '--attempt', '--exit-status', '--job', '--log', '--log-failed',
        '--verbose',
    }),
    'search code': GH_SEARCH_FLAGS,
    'search commits': GH_SEARCH_FLAGS,
    'search issues': GH_SEARCH_FLAGS,
    'search prs': GH_SEARCH_FLAGS,
    'search repos': GH_SEARCH_FLAGS,
    'workflow list': GH_OUTPUT_FLAGS | frozenset({'-a', '-L', '--all', '--limit'}),
    'workflow view': frozenset({'-r', '-y', '--ref', '--yaml'}),
}

GLAB_PAGE_FLAGS = frozenset({'-F', '-p', '-P', '--output', '--page', '--per-page'})
GLAB_READ_ALLOWED = {
    'auth status': frozenset({'--hostname'}),
    # `ci status` is left out because it offers to retry or cancel the pipeline, and `ci get`'s
    # `--with-variables` because it prints the pipeline's variables.
    'ci get': frozenset({
        '-b', '-d', '-F', '-p', '--branch', '--output', '--pipeline-id', '--with-job-details',
    }),
    'ci list': GLAB_PAGE_FLAGS | frozenset({
        '-a', '-b', '-n', '-o', '-r', '-s', '-u', '-y', '--name', '--orderBy', '--ref', '--scope',
        '--sha', '--sort', '--source', '--status', '--updated-after', '--updated-before',
        '--username', '--yaml-errors',
    }),
    'issue list': GLAB_PAGE_FLAGS | frozenset({
        '-a', '-A', '-c', '-C', '-e', '-g', '-i', '-l', '-m', '-O', '-t', '--all', '--assignee',
        '--author', '--closed', '--confidential', '--epic', '--group', '--in', '--issue-type',
        '--iteration', '--label', '--milestone', '--not-assignee', '--not-author', '--not-label',
        '--order', '--output-format', '--search', '--sort',
    }),
    'issue view': GLAB_PAGE_FLAGS | frozenset({'-c', '-s', '--comments', '--system-logs'}),
    'label list': GLAB_PAGE_FLAGS | frozenset({'-g', '--group'}),
    'mr diff': frozenset({'--color', '--raw'}),
    'mr list': GLAB_PAGE_FLAGS | frozenset({
        '-a', '-A', '-c', '-d', '-g', '-l', '-m', '-M', '-o', '-r', '-s', '-S', '-t', '--all',
        '--assignee', '--author', '--closed', '--draft', '--group', '--label', '--merged',
        '--milestone', '--not-draft', '--not-label', '--order', '--reviewer', '--search', '--sort',
        '--source-branch', '--target-branch',
    }),
    'mr view': GLAB_PAGE_FLAGS | frozenset({'-c', '-s', '--comments', '--system-logs'}),
    'release list': frozenset({'-p', '-P', '--page', '--per-page'}),
    'release view': frozenset(),
    'repo view': frozenset({'-b', '-F', '--branch', '--output'}),
}

# `gh api` and `glab api` flags that take a value, and the ones that don't. `-F`/`--field` and
# `--input` are left out because they can send a local file's contents, `--hostname` because it
# can send the request to any host, and `--verbose` because it prints the request headers.
GH_API_VALUE_FLAGS = frozenset({
    '-f', '-H', '-p', '-q', '-t', '-X', '--cache', '--header', '--jq', '--method', '--preview',
    '--raw-field', '--template',
})
GH_API_SWITCHES = frozenset({'-i', '--include', '--paginate', '--silent', '--slurp', '--help'})
GLAB_API_VALUE_FLAGS = frozenset({
    '-f', '-H', '-X', '--header', '--method', '--raw-field',
})
GLAB_API_SWITCHES = frozenset({'-h', '-i', '--help', '--include', '--paginate', '--silent'})

# A REST path, optionally with a query string and `{owner}`-style placeholders. A full URL or
# anything else that might reach a host other than the forge's prompts.
FORGE_API_ENDPOINT = re.compile(r'/?[\w.{}/?=&%,+~-]+')

# glab's `:id`-style placeholders, which fill in the current project the way gh's `{owner}` does.
FORGE_API_PLACEHOLDER = re.compile(r'(^|/):\w+(?=/|\?|$)')

FORGE_REPO_FLAGS = frozenset({'-R', '--repo'})

# What `-R`/`--repo` may name. gh reads `HOST/OWNER/REPO` and glab reads a URL or `git@host:`, so
# anything beyond a bare path could send the request, and the token for that host, elsewhere.
# glab is held to `GROUP/NAMESPACE/REPO`, since a longer path may be read with a host in front.
FORGE_REPOSITORY = {
    'gh': re.compile(r'[\w.-]+/[\w.-]+'),
    'glab': re.compile(r'[\w-]+(?:/[\w.-]+){1,2}'),
}

# A `repo view` operand with no slash, like a repository in the default owner. Anything else there
# has to pass `FORGE_REPOSITORY`.
FORGE_BARE_NAME = re.compile(r'[\w.-]+')

# An operand that starts like a protocol-relative URL or a `git@host:` remote. Both CLIs are
# expected to ignore those, but the hook shouldn't depend on it.
FORGE_REMOTE_OPERAND = re.compile(r'//|[\w.-]+@[\w.-]+:')

# The `repo view` flags that take a value, so the token after one isn't held to the repository
# check above.
FORGE_REPO_VIEW_VALUE_FLAGS = frozenset(
    {'-b', '-F', '-q', '-t', '--branch', '--jq', '--json', '--output', '--template'}
)

# Where Local's "Install Local CLI" preference puts its launcher. It resolves here only so that
# `LOCALWP_CANONICAL_SPELLING` can deny it with a reason that names the fix.
LOCALWP_BINARY = os.path.expanduser('~/Library/Application Support/Local/bin/localwp')

# `localwp` only works when it's spelled exactly this way, because `sandbox.excludedCommands`
# matches the literal `localwp *`. Any other spelling runs sandboxed and can't reach Local's
# socket, so it's denied with a pointer to this one instead of failing with `connect EPERM`.
LOCALWP_CANONICAL_SPELLING = re.compile(r'localwp( |$)')

# An unquoted `--key=` at the start of a word, with nothing in the key that bash could expand. The
# key must be lowercase, like every flag the hook disqualifies, so `nocaseglob` can't widen a
# harmless-looking `--Path=*` into a real `--path=`.
WP_ASSOC_ARG_KEY = re.compile(r'--[a-z0-9_-]+=')

# The exact binary spellings this hook will vouch for. Resolving by basename alone would treat
# any executable named `wp` at any path as WP-CLI, so an unlisted path is denied instead --
# the deny reason names this constant so the block is visible in the session.
BINARY_ALLOWED_PATHS = {
    'wp': 'wp',
    'vip': 'vip',
    'localwp': 'localwp',
    'gh': 'gh',
    'glab': 'glab',
    '/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/posix/wp': 'wp',
    LOCALWP_BINARY: 'localwp',
    '/opt/homebrew/bin/gh': 'gh',
    '/opt/homebrew/bin/glab': 'glab',
}

# Programs that run their arguments, or a file they name, in a way `bash_ast` can't follow: on
# another host (`ssh`), in a container (`docker exec`), through a shell it doesn't reparse (`csh`,
# `su -c`, `script`), or by sourcing a file. A quoted `'wp db reset'` or `'/opt/homebrew/bin/w?'`
# there runs as a command rather than staying data. `bash -c`, `eval`, `env -S`, `watch`, and
# `sudo -s` aren't listed because `bash_ast` reparses their strings into real commands; the shells
# themselves are, because `bash ./wp` runs a file named after a covered command.
OPAQUE_LAUNCHERS = frozenset({
    '.', 'csh', 'docker', 'expect', 'kubectl', 'parallel', 'podman', 'screen', 'script', 'source',
    'ssh', 'su', 'tcsh', 'tmux',
}) | bash_ast.SHELLS

# Programs known to treat their arguments as data, never as a program to run. Any other program
# with a bare covered name among its arguments (`parallel wp db reset`, `npx wp ...`) might exec
# it, so the hook asks rather than assuming it won't. `command` reaches this list only as
# `command -v`/`-V`, because `bash_ast` peels every other form.
DATA_CONSUMERS = frozenset({
    'cat', 'cd', 'command', 'echo', 'find', 'git', 'grep', 'head', 'ls', 'man', 'printf', 'rg',
    'tail',
    'type', 'wc', 'whereis', 'which',
})

# Options that turn a data consumer into something that runs a program, like `rg --pre wp`.
# Each maps to (short option letters, long options). A short letter counts anywhere in a cluster,
# so `man -aP wp` is caught, and a long option counts bare or with `=value`.
DATA_CONSUMER_RUNNING_OPTIONS = {
    'rg': ('', ('--pre',)),
    'man': ('PH', ('--pager', '--html')),
}


def runs_a_program_option(command):
    """True when a data consumer has an option that runs a program, or one that might."""
    letters, long_options = DATA_CONSUMER_RUNNING_OPTIONS.get(command.name, ('', ()))
    if not letters and not long_options:
        return False
    for word in command.words[1:]:
        if word.value is None:
            # An expansion could become the option itself.
            return True
        value = word.value
        if value.startswith('--'):
            if value.split('=', 1)[0] in long_options:
                return True
        elif value.startswith('-') and any(letter in value[1:] for letter in letters):
            return True
    return False


def option_value_texts(command):
    """Every argument's text, plus each option's value cut free of the option it's attached to.

    `man -Pwp\\ db\\ reset` glues the value to `-P`, where the letter before `wp` would hide it from
    a word-boundary match, so the value is also checked on its own.
    """
    letters, _long_options = DATA_CONSUMER_RUNNING_OPTIONS.get(command.name, ('', ()))
    texts = []
    for word in command.words[1:]:
        texts.append(word.raw)
        value = word.value
        if value is None:
            continue
        texts.append(value)
        if value.startswith('--') and '=' in value:
            texts.append(value.split('=', 1)[1])
        elif value.startswith('-'):
            position = next(
                (index for index, letter in enumerate(value[1:], start=1) if letter in letters),
                None,
            )
            if position is not None:
                texts.append(value[position + 1:])
    return texts


def is_data_consumer(command):
    """True when the program only reads its arguments, with no option that runs one of them."""
    return command.name in DATA_CONSUMERS and not runs_a_program_option(command)

COMMANDS = {
    'wp': {
        'allowed': WP_LOCAL_ALLOWED,
        'normalizer': 'wp',
    },
    'vip': {
        'allowed': VIP_NATIVE_ALLOWED,
        'normalizer': 'vip',
        # After VIP's target and global flags are consumed, a `wp` subcommand is plain WP-CLI, so
        # it reuses that allowlist rather than duplicating it. Only the reads, because every VIP
        # environment is remote.
        'delegates': {'wp': WP_READ_ALLOWED},
    },
    'localwp': {
        # Local's own reads only -- `start`, `stop`, and `new` change which sites exist or run.
        'allowed': ['info', 'list'],
        'normalizer': 'localwp',
        'delegates': {'cli': WP_LOCAL_ALLOWED},
    },
    'gh': {
        'allowed': GH_READ_ALLOWED,
        'normalizer': 'gh',
        'help_flags': frozenset({'--help'}),
        'api_value_flags': GH_API_VALUE_FLAGS,
        'api_switches': GH_API_SWITCHES,
    },
    'glab': {
        'allowed': GLAB_READ_ALLOWED,
        'normalizer': 'glab',
        'help_flags': frozenset({'-h', '--help'}),
        'api_value_flags': GLAB_API_VALUE_FLAGS,
        'api_switches': GLAB_API_SWITCHES,
    },
}


# Matches a covered command name as its own shell word inside an `OPAQUE_LAUNCHERS` argument, which
# a shell this hook can't see will parse again. The name has to end where a word bash is about to
# run can end -- whitespace, a metacharacter, a quote, or a `$`/`\` that the shell resolves before
# running it -- so `/bin/wp`, `wp option`, `x&&wp`, and `wp$X` all read as mentions, while
# `wp-content`, `wp/v2/media`, and `wp:featuredmedia` are just text.
COVERED_COMMAND_MENTION = re.compile(
    r'(?<![\w-])(?:' + '|'.join(re.escape(name) for name in COMMANDS) + r')(?=[\s;&|()<>"\'`$\\]|$)'
)


# Characters bash removes, or can expand to nothing, while it builds a word, so `w\p`, `"w"p`,
# `w$''p`, `w$()p`, and `` w``p `` all run `wp` once a launcher hands them to a shell again.
WORD_NOISE = re.compile(r'[\'"\\$`()]')

LINE_CONTINUATION = re.compile(r'\\\n')

GLOB_CHARACTERS = re.compile(r'[?*\[]')

EXPANSION = re.compile(r'[$`]')

# What separates words once `WORD_NOISE` is gone. Brace expansion's `{`, `,`, and `}` count too,
# because `{wp,}` runs `wp`.
WORD_BOUNDARY = re.compile(r'[\s;&|<>{},]+')

# A brace group with no brace inside it, which `could_expand_to_covered_name` widens to `*`.
INNERMOST_BRACE_GROUP = re.compile(r'\{[^{}]*\}')


def contains_in_order(letters, word):
    """Return whether every character of `letters` appears in `word`, in order."""
    remaining = iter(word)
    return all(letter in remaining for letter in letters)


def bracket_expression_end(pattern, start):
    """Return the index of the `]` closing the bracket expression opened at `start`, or None."""
    index = start + 1
    if pattern[index:index + 1] in ('!', '^'):
        index += 1
    # A `]` straight after the opening is a member, not the close.
    if pattern[index:index + 1] == ']':
        index += 1
    while index < len(pattern):
        if pattern[index:index + 2] in ('[:', '[=', '[.'):
            close = pattern.find(pattern[index + 1] + ']', index + 2)
            if close == -1:
                return None
            index = close + 2
        elif pattern[index] == ']':
            return index
        else:
            index += 1
    return None


def widen_bracket_expressions(pattern):
    """Return `pattern` with each bracket expression replaced by `?`.

    `fnmatch` reads `[^x]` as a literal `^` and doesn't know `[:alpha:]`, `[=x=]`, or `[.x.]`,
    while bash negates or expands them, so a pattern like `w[[:alpha:]]` would match `wp` in bash
    and not in `fnmatch`. A bracket expression matches one character, so `?` matches whatever
    bash would. A `[` with no close becomes `*`, which matches at least as much.
    """
    widened = []
    index = 0
    while index < len(pattern):
        if pattern[index] != '[':
            widened.append(pattern[index])
            index += 1
            continue
        end = bracket_expression_end(pattern, index)
        if end is None:
            widened.append('*')
            index += 1
        else:
            widened.append('?')
            index = end + 1
    return ''.join(widened)


def is_wp_assoc_arg_glob(word):
    """True when the word's only expansion is a glob in the value of a WP-CLI assoc arg.

    `option list --search=foo*` is the documented spelling, and bash can only turn it into more
    `--search=` words, or drop it under `nullglob`. Either way the key the allowlist judges is
    unchanged, and WP-CLI keeps the last of a repeated assoc arg. Under `nocaseglob` the key's
    case can change too, which is why `WP_ASSOC_ARG_KEY` accepts only lowercase keys.
    """
    return (
        word.value is not None
        and word.glob
        and not word.brace
        and WP_ASSOC_ARG_KEY.match(word.raw) is not None
    )


def wp_cli_argv_start(base_command, argv):
    """Index of the first word WP-CLI itself parses, or past the end when it parses none.

    Local's and VIP-CLI's own subcommands use their own option parsers, so only the argv they hand
    to WP-CLI gets the assoc arg glob exemption.
    """
    if None in argv:
        return len(argv)
    if base_command == 'wp':
        return 1
    if base_command == 'localwp' and argv[1:2] == ['cli'] and argv[3:4] == ['--']:
        return 4
    if base_command == 'vip':
        subcommand_tokens, _environment, _violation = normalize_vip(argv[1:])
        if subcommand_tokens and subcommand_tokens[0] == 'wp':
            return len(argv) - len(subcommand_tokens) + 1
    return len(argv)


def is_glob_for_covered_command(word):
    """Return whether `word` is a glob, like `/usr/bin/w?`, that could expand to a covered name."""
    if not GLOB_CHARACTERS.search(word):
        return False
    name = widen_bracket_expressions(word.rsplit('/', 1)[-1].lower())
    return any(fnmatch.fnmatchcase(command, name) for command in COMMANDS)


def could_expand_to_covered_name(word):
    """Return whether a program word with an unquoted glob or brace could become a covered name.

    A brace group can build a name from pieces (`w{x,p}`, `w{o..q}`, `{wp,}`) that no word on the
    line spells out, so each group is widened to `*` rather than expanded. That over-matches, but
    a brace in a program name is rare enough that a prompt costs little.
    """
    if not (word.glob or word.brace):
        return False
    text = word.value if word.value is not None else word.raw
    if word.brace:
        widened = INNERMOST_BRACE_GROUP.sub('*', text)
        while widened != text:
            text, widened = widened, INNERMOST_BRACE_GROUP.sub('*', widened)
    name = widen_bracket_expressions(text.rsplit('/', 1)[-1].lower())
    return any(fnmatch.fnmatchcase(command, name) for command in COMMANDS)


def mentions_covered_command(raw):
    """Return whether shell text another program will parse again might run a covered command.

    This is only used for `OPAQUE_LAUNCHERS` arguments, where `bash_ast` can't see the second
    parse, so it errs toward a match. Quotes, backslashes, and line continuations inside a name
    hide it from the regex while the shell still runs it, so the regex is tried again with them
    removed. A brace group counts, because one can build a name from pieces, and so does an
    expansion in a word holding a covered name's letters in order (`w${X}p`, `${X:-w}p`).
    """
    if COVERED_COMMAND_MENTION.search(raw):
        return True

    collapsed = WORD_NOISE.sub('', LINE_CONTINUATION.sub('', raw))
    if COVERED_COMMAND_MENTION.search(collapsed):
        return True

    for word in WORD_BOUNDARY.split(collapsed):
        if word.rsplit('/', 1)[-1] in COMMANDS or is_glob_for_covered_command(word):
            return True

    if '{' in collapsed and '}' in collapsed and (',' in collapsed or '..' in collapsed):
        return True

    return bool(EXPANSION.search(raw)) and any(contains_in_order(name, raw) for name in COMMANDS)


def no_opinion():
    """Exit without printing a decision, so `settings.json` rules apply normally.

    The hook runs on every Bash line rather than behind `if` filters, because a filter can only
    match the spellings it lists, and `command wp`, a single-quoted path, or a backslash-escaped
    one would skip it. Answering `ask` for lines that never run a covered command would turn
    every one of them into a prompt; staying silent hands them back to the permission system.
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


def matched_prefix(tokens, allowed):
    """Return the allowlist entry whose tokens lead `tokens`, or None.

    Compares token by token so `post lists` doesn't ride in on `post list`.
    """
    for prefix in allowed:
        prefix_tokens = prefix.split()
        if tokens[:len(prefix_tokens)] == prefix_tokens:
            return prefix
    return None


def strip_sql_literals(sql):
    """Blank out MySQL string literals, or return None if the SQL can't be read one way for sure.

    Handles `'...'` and `"..."`, where a doubled quote stands for itself. Backtick-quoted
    identifiers are skipped over so a quote inside one opens nothing, but their text is kept,
    since an identifier like `` `load_file` `` still names something the check looks for.

    Any backslash returns None. Inside a literal, whether it escapes the next character depends
    on the server's `NO_BACKSLASH_ESCAPES` mode, so `'a\\''; DELETE ...'` has two readings. Outside
    one, the mysql client treats `\\g` as the end of a statement, `\\.` as sourcing a file, and
    `\\!` as a shell command. A comment returns None too, because a quote inside a comment
    doesn't open a literal.
    """
    if '\\' in sql:
        return None
    out = []
    index = 0
    while index < len(sql):
        character = sql[index]
        if character == '#' or sql.startswith(('--', '/*'), index):
            # A quote inside a comment opens nothing, so stripping past one would read a real
            # `;` after it as part of a literal. Comments have no place in a quick read anyway.
            return None
        if character not in ('\'', '"', '`'):
            out.append(character)
            index += 1
            continue
        quote = character
        start = index
        index += 1
        while True:
            if index >= len(sql):
                return None
            if sql[index] == quote:
                if sql[index + 1:index + 2] == quote:
                    index += 2
                    continue
                index += 1
                break
            index += 1
        out.append(sql[start:index] if quote == '`' else ' ')
    return ''.join(out)


def validate_db_query(tokens, raw):
    """Decide a `wp db query` invocation, where the SQL and the flags are what make it safe.

    `tokens` starts at `db`; `raw` is the source text. Exactly one positional argument is
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

    # String literals can't end a statement or name a keyword, so they're blanked out first,
    # which keeps `LIKE '%a;b%'` or `'&#039;'` from reading as a second statement.
    code = strip_sql_literals(statements[0])
    if code is None:
        return ASK, (
            'wp db query SQL has a comment, an unterminated string literal, or a backslash, any '
            'of which can make the SQL run differently than it reads'
        )

    # On the Bash path `raw` is None, because the parser hands over exactly the string bash
    # passes. On the shell-free path this hook's `shlex` parse and the Local WP addon's own
    # splitter disagree over backslashes, so the source text is searched too, unstripped, which
    # only makes the check stricter. The `;` pattern is the only thing catching a second
    # statement, since no shell runs at all on that path.
    texts = [code] if raw is None else [code, raw]
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if any(pattern.search(text) for text in texts):
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
        # WP-CLI honors `--exec`, `--require`, `--path`, `--ssh`, and `--http` wherever they sit,
        # not just ahead of the subcommand, so a prefix match has to rule them out across the
        # whole line rather than trusting `normalize_wp` to have caught them among the leading
        # flags.
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
    if VIP_CONFIRMATION_FLAGS.intersection(token.partition('=')[0] for token in tokens):
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


def decide_localwp(tokens, config, raw):
    """Decide a Local CLI invocation, which is only auto-approved as a wrapper around WP-CLI.

    `localwp cli <site> -- <args>` forwards everything after the first `--` to WP-CLI as an argv,
    with no shell in between, so those arguments get the same allowlist as `wp` itself. Any other
    `cli` shape asks, including one with options before the `--`.
    """
    if not tokens or tokens[0] != 'cli':
        prefix = matched_prefix(tokens, config['allowed'])
        if prefix:
            return ALLOW, f'"localwp {prefix}" is allowlisted'
        return ASK, 'localwp command is not allowlisted'

    if len(tokens) < 3 or tokens[1].startswith('-') or tokens[2] != '--':
        return ASK, 'only "localwp cli <site> -- <wp-cli command>" is allowlisted for localwp cli'

    site = tokens[1]
    proxied_tokens, disqualifying_flag = normalize_wp(tokens[3:])
    if disqualifying_flag:
        return ASK, f'"{disqualifying_flag}" can run arbitrary code or retarget the command'

    outcome = match_wp_allowlist(proxied_tokens, config['delegates']['cli'], raw)
    if outcome:
        decision, reason = outcome
        if decision == ALLOW:
            reason = f'{reason}, through localwp on site "{site}"'
        return decision, reason
    return ASK, 'proxied WP-CLI command is not allowlisted'


def strip_repo_flags(name, tokens):
    """Drop `-R`/`--repo` and its value, which only pick the repository and can sit anywhere.

    Returns (kept_tokens, problem). The value has to be a plain repository path, because gh takes
    `HOST/OWNER/REPO` and glab takes a URL, either of which sends the request to another host.
    It also can't start with a dash: when `-R` is itself the value of an earlier flag, as in
    `--branch -R --web`, the word after it is a live flag that has to be checked. For the same
    reason, a repository flag straight after a bare flag asks, since dropping it would pair that
    flag with the next word instead.
    """
    kept = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == '--':
            kept.extend(tokens[index:])
            break
        is_repo_flag = token in FORGE_REPO_FLAGS or token.startswith(('--repo=', '-R'))
        previous = tokens[index - 1] if index else ''
        if is_repo_flag and previous.startswith('-') and '=' not in previous:
            return None, f'"{token}" may be the value of "{previous}"'
        if token in FORGE_REPO_FLAGS:
            value = tokens[index + 1] if index + 1 < len(tokens) else ''
            index += 2
        elif token.startswith('--repo='):
            value = token.partition('=')[2]
            index += 1
        elif token.startswith('-R') and len(token) > 2:
            value = token[2:]
            index += 1
        else:
            kept.append(token)
            index += 1
            continue
        if not FORGE_REPOSITORY[name].fullmatch(value):
            return None, f'"{value}" is not a plain repository path for {name} to read'
    return kept, None


def split_flag(token):
    """Split `--name=value` or `-Xvalue` into (flag, value), with None when nothing's attached."""
    if token.startswith('--'):
        flag, separator, value = token.partition('=')
        return flag, value if separator else None
    return token[:2], token[2:] or None


def validate_forge_api(name, tokens, config):
    """Decide `gh api` or `glab api`, which only pass as a GET to a REST path.

    `-f` makes the request a POST unless `-X GET` is also given, in which case the fields become
    query parameters. GraphQL always goes out as a POST, so it prompts even for a query.
    """
    method = None
    has_fields = False
    endpoints = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token == '--':
            endpoints.extend(tokens[index:])
            break
        if not token.startswith('-') or token == '-':
            endpoints.append(token)
            continue

        flag, value = split_flag(token)
        if flag in config['api_switches']:
            if value is not None:
                return ASK, f'"{token}" is not a form "{name} api" is allowlisted with'
            continue
        if flag not in config['api_value_flags']:
            return ASK, f'"{flag}" is not on the read-only flag list for "{name} api"'
        if value is None:
            if index >= len(tokens):
                return ASK, f'"{flag}" has no value'
            value = tokens[index]
            index += 1

        if flag in ('-X', '--method'):
            method = value
        elif flag in ('-H', '--header') and not value.lower().startswith('accept:'):
            return ASK, f'"{name} api" only allows an Accept header'
        elif flag in ('-f', '--raw-field'):
            has_fields = True

    if method not in (None, 'GET'):
        return ASK, f'"{name} api" is only allowlisted for GET requests'
    if has_fields and method != 'GET':
        return ASK, f'fields make "{name} api" send a POST unless "-X GET" is given'
    if len(endpoints) != 1:
        return ASK, f'"{name} api" needs exactly one endpoint'
    endpoint = endpoints[0]
    if endpoint.strip('/').lower() == 'graphql':
        return ASK, f'"{name} api graphql" sends a POST, and a query can\'t be told from a mutation'
    path = FORGE_API_PLACEHOLDER.sub(r'\1placeholder', endpoint)
    if '//' in path or not FORGE_API_ENDPOINT.fullmatch(path):
        return ASK, f'"{endpoint}" is not a plain REST path'
    return ALLOW, f'"{name} api" is a GET to a REST path'


def decide_forge(name, tokens, config):
    """Decide a `gh` or `glab` invocation against its read-only subcommands and their flags."""
    if tokens in (['--version'], ['version']):
        return ALLOW, f'"{name} {tokens[0]}" only prints the version'
    if tokens[:1] == ['api']:
        return validate_forge_api(name, tokens[1:], config)

    tokens, problem = strip_repo_flags(name, tokens)
    if problem:
        return ASK, problem
    path = matched_prefix(tokens, config['allowed'])
    if path is None:
        return ASK, f'{name} command is not allowlisted'

    # Short flags are compared whole rather than split like `split_flag` does, because these
    # lists don't record which flags take a value, and `-cw` is `-c -w` to pflag.
    allowed_flags = config['allowed'][path] | config['help_flags']
    operands_only = False
    previous = ''
    for token in tokens[len(path.split()):]:
        # pflag reads a `--` straight after a bare flag as that flag's value, as in
        # `--search -- --web`, so it only ends the flags when no flag might be waiting for one.
        might_be_a_value = previous.startswith('-') and '=' not in previous
        is_repo_view_value = (
            path == 'repo view' and not operands_only and previous in FORGE_REPO_VIEW_VALUE_FLAGS
        )
        previous = token
        if is_repo_view_value:
            # pflag takes the next word as the value even when it looks like a flag, so the word
            # after this one is checked as an operand again.
            previous = ''
            if '://' in token or FORGE_REMOTE_OPERAND.match(token):
                return ASK, f'"{token}" may name another host'
            continue
        if token == '--' and not operands_only and not might_be_a_value:
            operands_only = True
            continue
        if not operands_only and token.startswith('-') and token != '-':
            flag = token.partition('=')[0] if token.startswith('--') else token
            if flag not in allowed_flags:
                return ASK, f'"{flag}" is not on the read-only flag list for "{name} {path}"'
        elif '://' in token or FORGE_REMOTE_OPERAND.match(token) or (
            path == 'repo view'
            and not (FORGE_BARE_NAME.fullmatch(token) or FORGE_REPOSITORY[name].fullmatch(token))
        ):
            # A URL operand, or a `repo view` repository with a host or `git@host:` in front,
            # points the read elsewhere.
            return ASK, f'"{token}" may name another host'
    return ALLOW, f'"{name} {path}" is allowlisted'


NORMALIZERS = {
    'wp': decide_wp,
    'vip': decide_vip,
    'localwp': decide_localwp,
    'gh': lambda tokens, config, raw: decide_forge('gh', tokens, config),
    'glab': lambda tokens, config, raw: decide_forge('glab', tokens, config),
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


def chain_denial(description):
    return DENY, (
        f'{description}, so a prefix match cannot vouch for this command. Send each command as '
        'its own tool call (running-commands.md). A trailing `| head`, `| tail`, or `| wc` is the '
        'only pipeline this hook accepts; do not reword the line to get past this.'
    )


def decide_covered(command, raw_line):
    """Decide one parsed command whose program is a covered name."""
    spelling = command.words[0].value
    base_command = BINARY_ALLOWED_PATHS.get(spelling)
    if base_command is None:
        return DENY, (
            f'"{spelling}" is not in BINARY_ALLOWED_PATHS in command-allowlist-permissions.py, '
            'so this hook cannot vouch for the binary behind it'
        )

    if base_command == 'localwp' and not (
        command.words[0].raw == 'localwp'
        and not command.wrappers
        and not command.nested
        and LOCALWP_CANONICAL_SPELLING.match(raw_line)
    ):
        return DENY, (
            'localwp only reaches Local when it is spelled as a bare, unquoted `localwp` at the '
            'start of the line, because that is what `sandbox.excludedCommands` matches. Rewrite '
            'the command that way rather than finding another spelling.'
        )

    if command.opaque:
        return ASK, f'{command.opaque}, so a prefix match cannot vouch for this command'
    if command.nested:
        return ASK, (
            f'{base_command} runs inside a substitution, compound command, or command string, '
            'so a prefix match cannot vouch for it. Send one bare command per call.'
        )
    # `command` only skips aliases and functions. Anything else -- `env`, `sudo`, `nice` -- changes
    # how the program runs, and an assignment like `WP_CLI_CONFIG_PATH=` can load arbitrary code.
    other_wrappers = [wrapper for wrapper in command.wrappers if wrapper != 'command']
    if other_wrappers or command.assigns:
        return ASK, (
            f'{base_command} runs behind `{other_wrappers[0]}`' if other_wrappers
            else f'{base_command} runs with an environment assignment'
        ) + ', which this hook cannot vouch for'
    if command.dynamic_args:
        return ASK, f'{base_command} receives arguments at run time that the line does not show'
    wp_cli_start = wp_cli_argv_start(base_command, command.argv)
    if not all(
        word.literal or (index >= wp_cli_start and is_wp_assoc_arg_glob(word))
        for index, word in enumerate(command.words)
    ):
        return ASK, (
            f'an argument to {base_command} expands at run time, so a prefix match cannot vouch '
            'for this command. Send one bare command per call (running-commands.md) rather than '
            'rewording to get past this hook.'
        )
    if any(not redirect.benign for redirect in command.redirects):
        return ASK, (
            'a redirect writes to a real file, so a prefix match cannot vouch for this command. '
            'Drop the redirect rather than rewording to get past this hook.'
        )

    # Every word is literal by now, or a glob confined to an assoc arg's value, so the argv is
    # what the program receives as far as any check here can tell, and the `db query` check needs
    # no source text.
    return decide(base_command, command.argv[1:], None)


def judge_command(command, raw_line):
    """Return (decision, reason, names_covered) for one parsed command, or None for no opinion.

    `names_covered` is True when the command runs, or could run, a covered program, as opposed to
    one this hook only can't read. It decides whether a chained line is refused or prompted.
    """
    if not command.words:
        # An opaque command with no words is something bash_ast saw run but couldn't read, like
        # an array subscript that expands again; anything else wordless only redirects.
        if command.opaque:
            return ASK, f'{command.opaque}, so it might run a covered command', False
        return None
    program = command.words[0]

    # An environment value that names a covered program can be run by the command, like
    # `PAGER='wp db reset' man ls`.
    for name, value in command.assigns:
        if value is not None and mentions_covered_command(value.raw):
            return ASK, (
                f'`{name}=` names a covered command, and `{command.name or program.raw}` may run it'
            ), True

    if program.names_a_program and command.name in COMMANDS:
        return (*decide_covered(command, raw_line), True)

    if could_expand_to_covered_name(program):
        # A bare glob at the head of the line is the same mistake as an unlisted path, so it gets
        # the same refusal. Anything wrapped, nested, or built by a brace group prompts instead.
        if program.glob and not program.brace and not command.wrappers and not command.nested:
            return DENY, (
                f'"{program.raw}" could expand to a covered command, and no glob is in '
                'BINARY_ALLOWED_PATHS in command-allowlist-permissions.py'
            ), True
        return ASK, f'"{program.raw}" could expand to a covered command', True

    if command.opaque:
        return ASK, f'{command.opaque}, so it might run a covered command', False

    if command.name in OPAQUE_LAUNCHERS and any(
        mentions_covered_command(word.raw) for word in command.words[1:]
    ):
        return (
            ASK,
            'a covered command sits behind a launcher that runs it out of this hook\'s sight',
            True,
        )

    # `man -P` hands its value to a shell, so a covered name anywhere in the arguments counts.
    if runs_a_program_option(command) and any(
        mentions_covered_command(text) for text in option_value_texts(command)
    ):
        return ASK, (
            f'`{command.name}` has an option that runs a program, and a covered command is among '
            'its arguments'
        ), True

    # An option's attached value names a program as readily as a separate word does: `--pre=wp`.
    candidates = [
        value
        for word in command.words[1:] if word.literal
        for value in (word.value, word.value.split('=', 1)[-1])
    ]
    if not is_data_consumer(command) and any(
        os.path.basename(value).lower() in COMMANDS or value in BINARY_ALLOWED_PATHS
        for value in candidates
    ):
        return ASK, (
            f'`{command.name}` has a covered command among its arguments and may run it, which '
            'this hook cannot vouch for'
        ), True

    return None


def decide_bash_line(raw_line, cwd=None):
    try:
        parsed = bash_ast.parse(raw_line)
    except bash_ast.ParseError as error:
        return ASK, f'{error}, so this hook cannot tell whether it runs a covered command'

    judgements = [
        judgement for judgement in (judge_command(command, raw_line) for command in parsed.commands)
        if judgement is not None
    ]
    if not judgements:
        return None

    if parsed.chain and any(names_covered for _, _, names_covered in judgements):
        return chain_denial(parsed.chain)

    for wanted in (DENY, ASK):
        for decision, reason, _ in judgements:
            if decision == wanted:
                return decision, reason

    if len(parsed.commands) > 1:
        return ASK, 'the line runs more than the allowlisted command'

    decision, reason = judgements[0][0], judgements[0][1]
    remote_config = cwd and wp_cli_remote_config(cwd)
    if decision == ALLOW and parsed.commands[0].name in ('wp', 'localwp') and remote_config:
        return ASK, (
            f'`{remote_config}` has an `ssh:`, `http:`, or `inherit:` key that can point WP-CLI '
            'at a remote host, so this command may not run against a local site'
        )
    return decision, reason


# Where WP-CLI looks for a config file, besides the `WP_CLI_CONFIG_PATH` override. Project files
# are found by walking up from the working directory.
WP_CLI_PROJECT_CONFIGS = ('wp-cli.local.yml', 'wp-cli.yml')
WP_CLI_GLOBAL_CONFIG = os.path.expanduser('~/.wp-cli/config.yml')

# An `ssh:` or `http:` key sends commands to that host, and `inherit:` loads another config that
# might. This is matched anywhere in the file, in block or flow style, rather than parsed as
# YAML: telling a top-level key from one under an `@alias` reliably needs a full parser, and
# guessing wrong would let a remote command through, so a config with any of them prompts.
WP_CLI_REMOTE_KEY = re.compile(
    r'(?:^[ \t-]*|[{,][ \t]*)["\']?(?:ssh|http|inherit)["\']?[ \t]*:', re.MULTILINE,
)


def wp_cli_remote_config(cwd):
    """The first WP-CLI config file that sends every command to a remote host, or None."""
    candidates = [os.environ.get('WP_CLI_CONFIG_PATH') or WP_CLI_GLOBAL_CONFIG]
    directory = os.path.abspath(cwd)
    while True:
        candidates.extend(os.path.join(directory, name) for name in WP_CLI_PROJECT_CONFIGS)
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    for path in candidates:
        try:
            with open(path, encoding='utf-8', errors='replace') as config:
                if WP_CLI_REMOTE_KEY.search(config.read()):
                    return path
        except OSError:
            continue
    return None


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get('tool_input', {})
    shell_free = payload.get('tool_name') in SHELL_FREE_TOOLS

    # The Local WP MCP server passes the WP-CLI arguments alone; the Bash tool passes the whole
    # command line, binary included.
    raw_arguments = tool_input.get('args')
    raw_command = tool_input.get('command')

    if raw_arguments:
        if not shell_free:
            respond(ASK, 'this tool passes bare arguments but is not in SHELL_FREE_TOOLS')
        try:
            tokens = shlex.split(raw_arguments)
        except ValueError:
            respond(ASK, 'command could not be parsed into arguments')
        respond(*decide('wp', tokens, raw_arguments))

    if not raw_command:
        if raw_arguments is not None:
            respond(ASK, 'no command found in the tool input')
        no_opinion()

    outcome = decide_bash_line(raw_command, payload.get('cwd') or os.getcwd())
    if outcome is None:
        no_opinion()
    respond(*outcome)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:
        # Failing closed matters more than a useful error, because this hook is the only thing
        # standing between these commands and the auto-mode classifier.
        respond(ASK, f'permission hook errored, so it cannot vouch for this command: {error}')
