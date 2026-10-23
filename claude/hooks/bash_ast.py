"""Bash parsing shared by the permission hooks, built on `shfmt --to-json` from mvdan/sh.

Every Bash hook has to answer the same questions before it can apply its own policy: which
commands does this line run, with which arguments, and does it chain more than one of them? Hand
-written quote scanners kept disagreeing with bash about heredocs, `$'...'` strings, comments, and
commands nested inside `if` or `$(...)`, and each disagreement was a way past a gate. A real
parser removes that whole class of bug, so this module asks shfmt for the syntax tree and turns it
into the one shape the hooks need: a flat list of every command the line can run.

What stays in the hooks is policy. This module reports what bash will do and decides nothing.

Callers must fail closed on `ParseError`, which covers shfmt being missing, timing out, or
rejecting the line, because a line this module can't read is a line no hook can vouch for.

The filename uses underscores because this is an imported module rather than a hook the settings
file names; the hooks themselves keep the hyphens.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field

# Hooks run with whatever PATH Claude Code inherited, which may not include Homebrew.
SHFMT_FALLBACK_PATHS = ('/opt/homebrew/bin/shfmt', '/usr/local/bin/shfmt')

SHFMT_TIMEOUT_SECONDS = 5

# A `bash -c` whose string holds another `bash -c` is legal, but there's no honest reason to nest
# them deeper than this, and a cap keeps a pathological line from running past the hook's timeout.
MAX_REPARSE_DEPTH = 4

GLOB_CHARS = frozenset('*?[')

# Commands that read standard input and write standard output and can do nothing else. A pipeline
# ending in one of these runs no code the command before it didn't already run, which is what
# makes `git log | head -20` as safe as `git log`. Nothing that can write a file (`tee`,
# `sort -o`), run a program (`xargs`, `awk`, `sed`), or block (`tail -f`) belongs here.
OUTPUT_LIMITING_FILTERS = frozenset({'head', 'tail', 'wc'})

# Flags those three accept that only change how much they print. `-f`/`--follow` is deliberately
# absent: `tail -f` never exits, which would hang the tool call.
OUTPUT_LIMITING_SHORT_FLAGS = frozenset({'-n', '-c', '-l', '-w', '-m', '-q', '-v'})
OUTPUT_LIMITING_LONG_FLAGS = frozenset({
    '--lines', '--bytes', '--chars', '--words', '--max-line-length',
    '--quiet', '--silent', '--verbose', '--total',
})

# A count, either as `-20` or as the value of a preceding `-n`. A bare number is also how a
# filename made of digits would look; that's allowed because these three commands can only read a
# file and print it, which is no more than the pipeline already does.
OUTPUT_LIMITING_COUNT = re.compile(r'^-?[0-9]+$')

# Shells that run a command string given with `-c`, or read commands from stdin when given no
# script. A shell whose first operand is a script path is an ordinary command, because the hooks
# can't see inside the script either way and `settings.json` allows specific scripts by path.
SHELLS = frozenset({'bash', 'sh', 'zsh', 'dash', 'ksh', 'mksh', 'fish'})

@dataclass(frozen=True)
class OptionSpec:
    """The getopt rules for one wrapper, so its options are never mistaken for the wrapped command.

    `short_flags` are letters that take no value, and `short_values` letters that take one, either
    attached (`-n5`) or as the next word. `short_optional` letters swallow the rest of their
    cluster as an optional value but never the next word, like `xargs -i{}`. `long_flags` and
    `long_values` work the same way for `--name` and `--name=value`/`--name value`. `word_flags`
    and `word_values` are whole single-dash words, like `arch -arm64` and `arch -arch x`.
    `numeric` accepts `-<digits>`, like `nice -5`. Anything else that looks like an option makes
    the command opaque, because guessing wrong would hide the program that really runs.
    """
    short_flags: str = ''
    short_values: str = ''
    short_optional: str = ''
    long_flags: frozenset = frozenset()
    long_values: frozenset = frozenset()
    word_flags: frozenset = frozenset()
    word_values: frozenset = frozenset()
    numeric: bool = False


# Wrappers that run the command after their own options unchanged.
TRANSPARENT_WRAPPERS = {
    'builtin': OptionSpec(),
    'nohup': OptionSpec(),
    'exec': OptionSpec(short_flags='cl', short_values='a'),
    'time': OptionSpec(short_flags='ahlpv', short_values='o'),
    'nice': OptionSpec(short_values='n', long_values=frozenset({'--adjustment'}), numeric=True),
    'caffeinate': OptionSpec(short_flags='dimsu', short_values='tw'),
    'stdbuf': OptionSpec(
        short_values='ioe', long_values=frozenset({'--input', '--output', '--error'}),
    ),
    'doas': OptionSpec(short_flags='n', short_values='uC'),
    'sudo': OptionSpec(
        short_flags='AbEHknPS',
        short_values='ughpCTrtUDR',
        long_flags=frozenset({
            '--askpass', '--background', '--preserve-env', '--set-home', '--non-interactive',
            '--reset-timestamp', '--stdin',
        }),
        long_values=frozenset({
            '--user', '--group', '--host', '--prompt', '--close-from', '--command-timeout',
            '--role', '--type', '--other-user', '--chdir', '--chroot',
        }),
    ),
    'arch': OptionSpec(
        word_flags=frozenset({'-x86_64', '-arm64', '-arm64e', '-i386', '-32', '-64', '-c'}),
        word_values=frozenset({'-arch', '-d', '-e'}),
    ),
}

ENV_OPTIONS = OptionSpec(
    short_flags='i0v',
    short_values='uCP',
    long_flags=frozenset({'--ignore-environment', '--null', '--debug'}),
    long_values=frozenset({'--unset', '--chdir'}),
)

# `chroot NEWROOT command`: the first operand is the new root, not the program.
CHROOT_OPTIONS = OptionSpec(
    long_flags=frozenset({'--skip-chdir'}),
    long_values=frozenset({'--userspec', '--groups'}),
)

# `timeout DURATION command`: the first operand is the duration, not the program.
TIMEOUT_OPTIONS = OptionSpec(
    short_flags='v',
    short_values='sk',
    long_flags=frozenset({'--preserve-status', '--foreground', '--verbose'}),
    long_values=frozenset({'--signal', '--kill-after'}),
)

XARGS_OPTIONS = OptionSpec(
    short_flags='0rtpxo',
    short_values='ILnPsdEaJRS',
    short_optional='ile',
    long_flags=frozenset({
        '--null', '--no-run-if-empty', '--verbose', '--interactive', '--exit', '--open-tty',
    }),
    long_values=frozenset({
        '--max-args', '--max-procs', '--delimiter', '--arg-file', '--max-chars', '--replace',
        '--max-lines', '--eof', '--process-slot-var',
    }),
)

WATCH_OPTIONS = OptionSpec(
    short_flags='bcCeghpstwx',
    short_values='nq',
    short_optional='d',
    long_flags=frozenset({
        '--beep', '--color', '--no-color', '--differences', '--errexit', '--chgexit',
        '--no-title', '--precise', '--exec', '--no-wrap', '--no-linewrap',
    }),
    long_values=frozenset({'--interval', '--equexit'}),
)

# Shell options that take the next word as a value. The value is never the command string.
SHELL_VALUE_OPTIONS = frozenset({'-o', '+o', '-O', '+O', '--rcfile', '--init-file'})

# Recorded in `Command.wrappers` when a `git-<name>` program is judged as `git <name>`, so a hook
# can tell the program that runs isn't git itself.
GIT_EXEC_PATH_WRAPPER = 'git-<name> program'

# Builtins that evaluate a string argument as arithmetic or as an array reference, which expands
# a subscript in it. A `TestClause` or `DeclClause` holding a quoted subscript is parsed as a
# subscript by shfmt only when it's unquoted, so these are checked by their resolved text instead.
ARITHMETIC_BUILTINS = frozenset({
    'let', 'unset', 'read', 'printf', 'test', '[', 'declare', 'typeset', 'local', 'export',
    'readonly',
})

# Clauses that evaluate their words' text as arithmetic: `[[ x -eq y ]]`, `declare -i`, `let`.
STRING_ARITHMETIC_KINDS = frozenset({'TestClause', 'DeclClause', 'LetClause'})

# A subscript in a builtin's resolved argument that holds an expansion, like `a[$(cmd)]`.
QUOTED_SUBSCRIPT = re.compile(r'\[[^\]]*[$`]')

# Shells whose code bash's grammar reads correctly. `sh` and `dash` are POSIX shells, a subset.
BASH_GRAMMAR_SHELLS = frozenset({'bash', 'sh', 'dash'})

# Script operands that make a shell, `source`, or `.` read commands from stdin.
STDIN_SCRIPT_PATHS = frozenset({'-', '/dev/stdin', '/dev/fd/0', '/proc/self/fd/0'})

# Single-letter shell options that take no value, the union of what bash, sh, zsh, dash, and
# ksh accept. `o` and `O` take a value and are handled apart.
SHELL_SHORT_FLAGS = frozenset('abcefhiklmnprstuvxBCDEHLPT')

# Long shell options that take no value.
SHELL_LONG_FLAGS = frozenset({
    '--norc', '--noprofile', '--login', '--posix', '--restricted', '--verbose', '--noediting',
    '--no-rcs', '--no-globalrcs', '--interactive', '--private', '--no-config', '--debugger',
})

# `find` actions that run a command, which ends at a `;` or `+` argument.
FIND_EXEC_ACTIONS = frozenset({'-exec', '-execdir', '-ok', '-okdir'})

# git global options that take the next word as their value.
GIT_GLOBAL_VALUE_OPTIONS = frozenset({
    '-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env', '--super-prefix',
    '--attr-source',
})

# git global options that never take a separate value. `--exec-path` takes one only attached, as
# `--exec-path=x`.
GIT_GLOBAL_FLAGS = frozenset({
    '--exec-path', '-p', '-P', '--paginate', '--no-pager', '--bare', '--literal-pathspecs',
    '--glob-pathspecs', '--noglob-pathspecs', '--icase-pathspecs', '--no-replace-objects',
    '--no-optional-locks', '--no-lazy-fetch', '--no-advice', '--html-path', '--man-path', '--info-path', '--version',
    '--help',
})

# git subcommand options whose value git runs through a shell. This is best effort rather than
# complete: a missing entry can't produce an allow, because `file-command-permissions.py` only
# auto-approves git commands whose every option is on its own safe list, so the cost of a gap is
# that the auto-mode classifier decides instead of a hook denying the hidden command.
GIT_SHELL_VALUE_OPTIONS = {
    'rebase': frozenset({'-x', '--exec'}),
    'difftool': frozenset({'-x', '--extcmd'}),
    'filter-branch': frozenset({
        '--tree-filter', '--index-filter', '--msg-filter', '--env-filter', '--commit-filter',
        '--parent-filter', '--tag-name-filter', '--setup',
    }),
    'fetch': frozenset({'--upload-pack'}),
    'pull': frozenset({'--upload-pack'}),
    'ls-remote': frozenset({'--upload-pack', '--exec'}),
    'clone': frozenset({'-u', '--upload-pack'}),
    'push': frozenset({'--receive-pack', '--exec'}),
    'archive': frozenset({'--exec'}),
    'send-email': frozenset({'--to-cmd', '--cc-cmd', '--sendmail-cmd', '--header-cmd'}),
    'grep': frozenset({'-O', '--open-files-in-pager'}),
    'fetch-pack': frozenset({'--upload-pack', '--exec'}),
    'send-pack': frozenset({'--receive-pack', '--exec'}),
}

# git subcommand options that set config, which can name a program to run (`core.sshCommand`,
# `core.fsmonitor`, `credential.helper`, ...). There's no honest way to enumerate every key that
# runs something, so a command using one of these can't be read.
GIT_CONFIG_SETTING_OPTIONS = {
    # A template directory can carry hooks that run during the clone itself.
    'clone': frozenset({'-c', '--config', '--template'}),
    'init': frozenset({'--template'}),
}

# Options whose value is optional, so it only counts when attached (`-Ocmd`, `--opt=cmd`). A bare
# one doesn't take the next word, which stays an ordinary argument.
GIT_OPTIONAL_VALUE_OPTIONS = frozenset({'grep -O', 'grep --open-files-in-pager'})

# Code points beyond this aren't characters, and `chr()` refuses them.
MAX_CODE_POINT = 0x10FFFF

ENV_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')

# Source-text kinds of compound command, named the way an error message should name them.
COMPOUND_KINDS = {
    'Subshell': 'a `( ... )` subshell',
    'Block': 'a `{ ... }` group',
    'IfClause': 'an `if` statement',
    'WhileClause': 'a `while`/`until` loop',
    'ForClause': 'a `for` loop',
    'CaseClause': 'a `case` statement',
    'FuncDecl': 'a function definition',
    'CoprocClause': 'a `coproc`',
}


class ParseError(Exception):
    """The line could not be parsed, so no hook can vouch for it."""


@dataclass
class Word:
    """One shell word, with its quoting resolved the way bash resolves it.

    `value` is the text the command receives, or None when any part of the word expands at run
    time (a `$var`, `$(...)`, `$((...))`, or extglob). `glob` and `brace` flag unquoted characters
    that let bash turn this one word into other words; `value` keeps them as written. `tilde` flags
    an unquoted leading `~`, which bash replaces with a home directory. `raw` is the source text.
    """
    value: str | None
    raw: str
    glob: bool = False
    brace: bool = False
    tilde: bool = False

    @property
    def literal(self):
        """True when the command receives exactly `value`, with nothing expanded."""
        return self.value is not None and not (self.glob or self.brace or self.tilde)

    @property
    def names_a_program(self):
        """True when this word, in command position, names one program a hook can identify.

        A leading `~` only swaps in a home directory, which leaves the basename alone.
        """
        return self.value is not None and not (self.glob or self.brace)


@dataclass
class Redirect:
    """One redirection. `fd` is the explicit descriptor number, or None when bash uses its
    default."""
    op: str
    fd: str | None
    target: Word | None
    heredoc: Word | None = None

    @property
    def is_output(self):
        return self.op in ('>', '>>', '>|', '&>', '&>>', '<>')

    @property
    def benign(self):
        """True when this redirect can't write a real file: `/dev/null`, or an fd duplication."""
        if self.target is None:
            return False
        if self.op in ('>&', '<&'):
            return self.target.value is not None and (
                self.target.value == '-' or self.target.value.isdigit()
            )
        if self.op in ('<<', '<<-', '<<<'):
            return True
        if self.op == '<':
            return True
        return self.target.literal and self.target.value == '/dev/null'


@dataclass
class Command:
    """One simple command the line can run, with any wrappers around it already peeled off.

    `words[0]` is the program. `wrappers` lists what was peeled, outermost first, like `['env',
    'bash -c']`. `nested` is True when the command sits inside a substitution, a compound command,
    or a reparsed string rather than at the top of the line. `dynamic_args` is True when a wrapper
    like `xargs` or `find -exec` appends arguments at run time that the line doesn't show.
    `opaque` holds a reason when the program that runs can't be read from the line at all, like
    `bash -c "$script"` or a command name built from a variable; `words` is then whatever was
    left. `raw` is the source text of the whole statement, wrappers included.
    """
    words: list
    raw: str
    assigns: list = field(default_factory=list)
    redirects: list = field(default_factory=list)
    wrappers: list = field(default_factory=list)
    nested: bool = False
    dynamic_args: bool = False
    opaque: str | None = None

    @property
    def name(self):
        """The program's basename, lowercased, or None when it isn't a literal word.

        Lowercased because macOS filesystems are case-insensitive, so `Git` runs git.
        """
        if not self.words or not self.words[0].names_a_program:
            return None
        return os.path.basename(self.words[0].value).lower() or None

    @property
    def argv(self):
        """Every word's value, with None standing in for a word that expands at run time."""
        return [word.value for word in self.words]

    @property
    def literal(self):
        """True when every word is literal, so `argv` is exactly what the program receives."""
        return self.opaque is None and not self.dynamic_args and all(
            word.literal for word in self.words
        )


@dataclass
class Parsed:
    """Everything a hook needs from one Bash tool call.

    `commands` holds every simple command anywhere in the line, in source order. `chain` describes
    the first construct that runs more than one command -- `;`, `&&`, `||`, `|`, `&`, a newline,
    or a compound command -- or is None. A pipeline ending in `head`, `tail`, or `wc` doesn't
    count, and the filter is dropped from `commands`, so the line is judged as the command that
    feeds it.
    """
    commands: list
    chain: str | None


def find_shfmt():
    return shutil.which('shfmt') or next(
        (path for path in SHFMT_FALLBACK_PATHS if os.access(path, os.X_OK)), None
    )


def syntax_tree(text):
    shfmt = find_shfmt()
    if shfmt is None:
        raise ParseError('shfmt is not installed, so this line cannot be parsed')
    try:
        result = subprocess.run(
            [shfmt, '--to-json', '-ln', 'bash'],
            input=text.encode(), capture_output=True, timeout=SHFMT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ParseError(f'shfmt failed to run: {error}') from error
    if result.returncode != 0:
        detail = result.stderr.decode(errors='replace').strip() or 'unknown error'
        raise ParseError(f'bash cannot parse this line: {detail}')
    try:
        return json.loads(result.stdout)
    except ValueError as error:
        raise ParseError(f'shfmt returned unreadable output: {error}') from error


def decode_ansi_c(text):
    """Resolve the escapes bash honors inside `$'...'`."""
    simple = {
        'a': '\a', 'b': '\b', 'e': '\x1b', 'E': '\x1b', 'f': '\f', 'n': '\n', 'r': '\r',
        't': '\t', 'v': '\v', '\\': '\\', "'": "'", '"': '"', '?': '?',
    }
    out = []
    index = 0
    while index < len(text):
        character = text[index]
        if character != '\\' or index + 1 == len(text):
            out.append(character)
            index += 1
            continue
        escape = text[index + 1]
        if escape in simple:
            out.append(simple[escape])
            index += 2
        elif escape in '01234567':
            digits = re.match(r'[0-7]{1,3}', text[index + 1:]).group()
            out.append(chr(int(digits, 8) & 0xFF))
            index += 1 + len(digits)
        elif escape in 'xuU':
            limit = {'x': 2, 'u': 4, 'U': 8}[escape]
            digits = re.match(r'[0-9A-Fa-f]{0,%d}' % limit, text[index + 2:]).group()
            if digits and int(digits, 16) <= MAX_CODE_POINT:
                out.append(chr(int(digits, 16)))
                index += 2 + len(digits)
            else:
                out.append(text[index:index + 2])
                index += 2
        elif escape == 'c' and index + 2 < len(text):
            out.append(chr(ord(text[index + 2]) & 0x1F))
            index += 3
        else:
            out.append(text[index:index + 2])
            index += 2
    # Bash ends a `$'...'` string at its first NUL, so `$'--hard\0x'` passes `--hard`.
    return ''.join(out).split('\x00', 1)[0]


def unescape_unquoted(text):
    """Resolve backslashes in unquoted text, returning (value, glob, brace).

    A backslash quotes the next character, and a backslash-newline disappears entirely. Glob and
    brace characters only count when no backslash quoted them.
    """
    out = []
    glob = brace_open = False
    index = 0
    while index < len(text):
        character = text[index]
        if character == '\\' and index + 1 < len(text):
            if text[index + 1] != '\n':
                out.append(text[index + 1])
            index += 2
            continue
        if character in GLOB_CHARS:
            glob = True
        if character == '{':
            brace_open = True
        out.append(character)
        index += 1
    return ''.join(out), glob, brace_open


# Stands in for a quoted or expanding part when scanning a word for brace groups. Quoted text can't
# hold the `,` or `}` that makes a group, but it does sit inside one, as in `{'a',b}`.
QUOTED_PLACEHOLDER = '\x00'


def has_brace_group(text):
    """True if unquoted `text` holds a `{...}` that bash would expand.

    Bash only expands a group holding a top-level `,` or a `..`, so `stash@{0}` and
    `@{u}..HEAD` stay literal. A backslash-escaped brace never opens or closes one.
    """
    starts = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == '\\':
            index += 2
            continue
        if character == '{':
            starts.append(index)
        elif character == '}' and starts:
            start = starts.pop()
            inner = text[start + 1:index]
            if '..' in inner or ',' in strip_nested_groups(inner):
                return True
        index += 1
    return False


def strip_nested_groups(text):
    """Drop nested `{...}` from `text`, so only its own top-level commas remain."""
    depth = 0
    kept = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == '\\':
            # An escaped brace neither opens nor closes a group, and an escaped comma isn't one.
            if depth == 0:
                kept.append(text[index:index + 2])
            index += 2
            continue
        if character == '{':
            depth += 1
        elif character == '}' and depth:
            depth -= 1
        elif depth == 0:
            kept.append(character)
        index += 1
    return ''.join(kept)


def sudo_escape(value):
    """Escape a word the way `sudo -s` does before handing it to `$SHELL -c`.

    sudo backslash-escapes every character except letters, digits, `_`, `-`, and `$`. Leaving `$`
    alone means `sudo -s echo '$(cmd)'` really runs `cmd`, so the rebuilt text has to keep it
    live for the reparse to see that expansion.
    """
    return ''.join(
        character if character.isalnum() or character in '_-$' else '\\' + character
        for character in value
    )


def unescape_heredoc(text):
    """Resolve backslashes in an unquoted heredoc body, where a `"` isn't special."""
    out = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == '\\' and index + 1 < len(text) and text[index + 1] in '$`\\\n':
            if text[index + 1] != '\n':
                out.append(text[index + 1])
            index += 2
            continue
        out.append(character)
        index += 1
    return ''.join(out)


def unescape_double_quoted(text):
    """Resolve backslashes inside double quotes, where only `$`, backtick, `"`, `\\`, and newline
    are escaped."""
    out = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == '\\' and index + 1 < len(text) and text[index + 1] in '$`"\\\n':
            if text[index + 1] != '\n':
                out.append(text[index + 1])
            index += 2
            continue
        out.append(character)
        index += 1
    return ''.join(out)


class LineParser:
    """Walks one shfmt tree, collecting commands and the first chaining construct."""

    def __init__(self, text, depth=0, nested=False, wrappers=None):
        self.text = text
        self.source = text.encode()
        self.depth = depth
        self.base_nested = nested
        self.base_wrappers = list(wrappers or [])
        self.commands = []
        self.chain = None

    def slice(self, node):
        return self.source[node['Pos']['Offset']:node['End']['Offset']].decode(errors='replace')

    def note_chain(self, description):
        if self.chain is None:
            self.chain = description

    # Words --------------------------------------------------------------------------------------

    def word(self, node):
        if node is None:
            return None
        value_parts = []
        glob = brace_open = tilde = False
        literal = True
        brace_text = []
        for position, part in enumerate(node.get('Parts', [])):
            kind = part.get('Type')
            if kind == 'Lit':
                raw = part.get('Value', '')
                if position == 0 and raw.startswith('~'):
                    tilde = True
                value, part_glob, part_brace = unescape_unquoted(raw)
                glob = glob or part_glob
                brace_open = brace_open or part_brace
                value_parts.append(value)
                brace_text.append(raw)
            elif kind == 'SglQuoted':
                raw = part.get('Value', '')
                value_parts.append(decode_ansi_c(raw) if part.get('Dollar') else raw)
                brace_text.append(QUOTED_PLACEHOLDER)
            elif kind == 'DblQuoted':
                for inner in part.get('Parts', []):
                    if inner.get('Type') == 'Lit':
                        value_parts.append(unescape_double_quoted(inner.get('Value', '')))
                    else:
                        literal = False
                brace_text.append(QUOTED_PLACEHOLDER)
            else:
                literal = False
                brace_text.append(QUOTED_PLACEHOLDER)
        brace = brace_open and has_brace_group(''.join(brace_text))
        return Word(
            value=''.join(value_parts) if literal else None,
            raw=self.slice(node),
            glob=glob,
            brace=brace,
            tilde=tilde,
        )

    def redirect(self, node):
        fd = node.get('N', {}).get('Value') if node.get('N') else None
        delimiter = node.get('Word')
        return Redirect(
            op=node.get('Op', ''),
            fd=fd,
            target=self.word(delimiter),
            heredoc=self.heredoc_body(node.get('Hdoc'), self.delimiter_is_quoted(delimiter)),
        )

    @staticmethod
    def delimiter_is_quoted(node):
        """True when any part of a heredoc delimiter is quoted, which makes the body literal."""
        for part in (node or {}).get('Parts', []):
            if part.get('Type') != 'Lit' or '\\' in part.get('Value', ''):
                return True
        return False

    def heredoc_body(self, node, quoted):
        """Resolve a heredoc body the way bash reads it.

        A quoted delimiter leaves the body exactly as written. Otherwise the body behaves like
        double-quoted text: only `\\$`, a backslash-backtick, `\\\\`, and backslash-newline are
        escapes, and any expansion makes it non-literal. Unescaping it as unquoted words would
        turn `\\'` into a quote that bash never sees.
        """
        if node is None:
            return None
        pieces = []
        literal = True
        for part in node.get('Parts', []):
            if part.get('Type') != 'Lit':
                literal = False
                continue
            raw = part.get('Value', '')
            pieces.append(raw if quoted else unescape_heredoc(raw))
        return Word(value=''.join(pieces) if literal else None, raw=self.slice(node))

    # Walking ------------------------------------------------------------------------------------

    def walk_statements(self, statements, nested, top_level=False):
        if len(statements) > 1:
            self.note_chain('a second command after `;`, `&`, or a newline')
        for index, statement in enumerate(statements):
            self.walk_statement(statement, nested, top_level=top_level and len(statements) == 1)

    def walk_statement(self, statement, nested, top_level=False):
        if statement.get('Background'):
            self.note_chain('`&` runs a command in the background alongside another')
        command = statement.get('Cmd')
        redirects = [self.redirect(node) for node in statement.get('Redirs', []) or []]

        if command is None:
            # A bare redirect, like `> file`, which truncates or creates a file and runs nothing.
            self.commands.append(Command(
                words=[], raw=self.slice(statement), redirects=redirects,
                wrappers=list(self.base_wrappers), nested=nested or self.base_nested,
            ))
            return

        kind = command.get('Type')
        if kind == 'CallExpr':
            self.call(command, statement, redirects, nested)
        elif kind == 'BinaryCmd':
            if top_level and command.get('Op') == '|' and self.is_output_limiting(command['Y']):
                self.walk_statement(command['X'], nested, top_level=True)
            else:
                self.note_chain(f"`{command.get('Op')}` chains a second command")
                self.walk_statement(command['X'], nested)
                self.walk_statement(command['Y'], nested)
        elif kind == 'TimeClause':
            if command.get('Stmt'):
                self.walk_statement(command['Stmt'], nested, top_level=top_level)
        else:
            if kind in COMPOUND_KINDS:
                self.note_chain(f'{COMPOUND_KINDS[kind]} can run more than one command')
            self.walk_children(command, nested=True)
            for redirect_node in statement.get('Redirs', []) or []:
                self.walk_children(redirect_node, nested=True)
            if redirects:
                # `export x=1 > file`, `[[ ... ]] > file`, and `{ ...; } > file` write a file too,
                # so report the redirect the same way a bare `> file` is reported.
                self.commands.append(Command(
                    words=[], raw=self.slice(statement), redirects=redirects,
                    wrappers=list(self.base_wrappers), nested=nested or self.base_nested,
                ))

    def flag_subscript_expansion(self, text):
        """Report an array subscript or slice whose text could hold a substitution.

        Bash evaluates a subscript as arithmetic, and that expands it again, even text that was
        quoted, so `${a['x[$(cmd)]']}` and `(( a['$(cmd)'] ))` both run `cmd`. The command never
        reaches the syntax tree as one, so the subscript is reported as an opaque command.
        """
        if '$' in text or '`' in text:
            self.commands.append(Command(
                words=[], raw=text, wrappers=list(self.base_wrappers), nested=True,
                opaque='an array subscript is expanded again at run time, so this hook cannot '
                       'see what it runs',
            ))

    def flag_word_subscripts(self, node):
        """Check every word under `node` whose resolved text holds a subscript with an expansion."""
        if isinstance(node, list):
            for item in node:
                self.flag_word_subscripts(item)
            return
        if not isinstance(node, dict):
            return
        if 'Parts' in node and 'Pos' in node:
            word = self.word(node)
            if word.value is not None and QUOTED_SUBSCRIPT.search(word.value):
                self.flag_subscript_expansion(word.value)
                return
        for key, value in node.items():
            if key not in ('Pos', 'End'):
                self.flag_word_subscripts(value)

    def flag_node_subscripts(self, node):
        """Check the `Index` and `Slice` parts of a parameter expansion or an assignment."""
        for key in ('Index', 'Slice'):
            part = node.get(key)
            if not isinstance(part, dict):
                continue
            pieces = [part] if 'Pos' in part else [
                value for value in part.values() if isinstance(value, dict) and 'Pos' in value
            ]
            for piece in pieces:
                self.flag_subscript_expansion(self.slice(piece))

    def walk_children(self, node, nested):
        """Find statements anywhere below `node`: substitutions, compound bodies, test clauses."""
        if isinstance(node, list):
            for item in node:
                self.walk_children(item, nested)
            return
        if not isinstance(node, dict):
            return
        if 'Position' in node and 'Type' not in node:
            self.walk_statement(node, nested)
            return
        kind = node.get('Type')
        if kind in ('CmdSubst', 'ProcSubst'):
            self.walk_statements(node.get('Stmts', []), nested=True)
            return
        if 'Index' in node or 'Slice' in node:
            self.flag_node_subscripts(node)
        if kind in STRING_ARITHMETIC_KINDS:
            self.flag_word_subscripts(node)
        for key, value in node.items():
            if key not in ('Pos', 'End'):
                self.walk_children(value, nested)

    def is_output_limiting(self, statement):
        command = statement.get('Cmd') or {}
        if command.get('Type') != 'CallExpr' or command.get('Assigns'):
            return False
        # The filter is dropped from the command list, so anything in its redirects would go unseen.
        # Only output to `/dev/null` and fd duplication pass; any input redirect, heredoc, or
        # here-string could carry a substitution that runs a command.
        for node in statement.get('Redirs', []) or []:
            redirect = self.redirect(node)
            reads_dev_null = (
                redirect.op == '<' and redirect.target is not None and redirect.target.literal
                and redirect.target.value == '/dev/null'
            )
            if not redirect.benign or (
                redirect.op in ('<', '<<', '<<-', '<<<', '<>') and not reads_dev_null
            ):
                return False
        words = [self.word(arg) for arg in command.get('Args', [])]
        if not words or not all(word.literal for word in words):
            return False
        values = [word.value for word in words]
        if values[0] == 'command':
            values = values[1:]
        if not values or values[0] not in OUTPUT_LIMITING_FILTERS:
            return False
        for value in values[1:]:
            if OUTPUT_LIMITING_COUNT.match(value) or value in OUTPUT_LIMITING_SHORT_FLAGS:
                continue
            if value.split('=', 1)[0] in OUTPUT_LIMITING_LONG_FLAGS:
                continue
            return False
        return True

    def call(self, node, statement, redirects, nested):
        # Substitutions inside the words and assignments run first, so collect those commands too.
        for child_key in ('Assigns', 'Args'):
            self.walk_children(node.get(child_key, []), nested=True)
        for redirect_node in statement.get('Redirs', []) or []:
            self.walk_children(redirect_node, nested=True)

        assigns = []
        for assign in node.get('Assigns', []) or []:
            name = (assign.get('Name') or {}).get('Value', '')
            assigns.append((name, self.word(assign.get('Value'))))
        command = Command(
            words=[self.word(arg) for arg in node.get('Args', []) or []],
            raw=self.slice(statement),
            assigns=assigns,
            redirects=redirects,
            wrappers=list(self.base_wrappers),
            nested=nested or self.base_nested,
        )
        self.unwrap(command)

    # Wrappers -----------------------------------------------------------------------------------

    def emit(self, command):
        self.commands.append(command)

    def reparse(self, command, text, wrapper):
        """Parse a string a wrapper hands to a shell, and adopt the commands inside it."""
        if self.depth >= MAX_REPARSE_DEPTH:
            command.opaque = f'`{wrapper}` nests more shells than this hook will follow'
            self.emit(command)
            return
        inner = LineParser(
            text, depth=self.depth + 1, nested=True,
            wrappers=command.wrappers + [wrapper],
        )
        try:
            inner.walk_statements(syntax_tree(text).get('Stmts', []), nested=True, top_level=True)
        except ParseError as error:
            command.opaque = f'`{wrapper}` runs a string bash cannot parse: {error}'
            self.emit(command)
            return
        if inner.chain:
            self.note_chain(f'{inner.chain}, inside `{wrapper}`')
        for inner_command in inner.commands:
            inner_command.assigns = command.assigns + inner_command.assigns
            inner_command.redirects = command.redirects + inner_command.redirects
            self.emit(inner_command)

    def unwrap(self, command):
        """Peel wrappers off `command` until the program that really runs is at `words[0]`."""
        while True:
            if command.opaque or not command.words:
                self.emit(command)
                return
            head = command.words[0]
            if not head.names_a_program:
                command.opaque = (
                    'the program name expands at run time, so this hook cannot tell what runs'
                )
                self.emit(command)
                return
            name = command.name

            if name == 'command':
                rest = command.words[1:]
                describes_only = False
                while rest and (rest[0].value is None or (
                    rest[0].value.startswith('-') and rest[0].value != '-'
                )):
                    value = rest[0].value
                    if value is None:
                        command.opaque = (
                            'an option to `command` expands at run time, so this hook cannot tell '
                            'what runs'
                        )
                        self.emit(command)
                        return
                    rest = rest[1:]
                    if value == '--':
                        break
                    letters = set(value[1:])
                    if letters - set('pvV'):
                        command.opaque = f'`command` has an option this hook does not know, `{value}`'
                        self.emit(command)
                        return
                    describes_only = describes_only or bool(letters & {'v', 'V'})
                if describes_only:
                    # `command -v` only reports what a name would run.
                    self.emit(command)
                    return
                self.peel(command, 'command', rest)
                continue

            if name in TRANSPARENT_WRAPPERS:
                if name in ('sudo', 'doas') and self.runs_through_shell(command):
                    return
                rest = self.skip_options(command.words[1:], TRANSPARENT_WRAPPERS[name], name)
                if rest is None:
                    return
                if not rest:
                    self.emit(command)
                    return
                self.peel(command, name, rest)
                continue

            if name == 'env':
                if self.unwrap_env(command):
                    return
                continue

            if name in ('timeout', 'chroot'):
                spec = TIMEOUT_OPTIONS if name == 'timeout' else CHROOT_OPTIONS
                rest = self.skip_options(command.words[1:], spec, name)
                if rest is None:
                    return
                if len(rest) < 2:
                    self.emit(command)
                    return
                self.peel(command, name, rest[1:])
                continue

            if name == 'xargs':
                rest = self.skip_options(command.words[1:], XARGS_OPTIONS, name)
                if rest is None:
                    return
                if not rest:
                    self.emit(command)
                    return
                command.dynamic_args = True
                self.peel(command, 'xargs', rest)
                continue

            if name == 'find':
                self.unwrap_find(command)
                return

            if name == 'eval':
                self.unwrap_string(command, command.words[1:], 'eval')
                return

            if name == 'watch':
                rest = self.skip_options(command.words[1:], WATCH_OPTIONS, name)
                if rest is None:
                    return
                if not rest:
                    self.emit(command)
                    return
                options = command.words[1:len(command.words) - len(rest)]
                if any(self.watch_option_execs(word.value) for word in options):
                    # `watch -x` runs its arguments as an argv rather than through `sh -c`.
                    self.peel(command, 'watch -x', rest)
                    continue
                self.unwrap_string(command, rest, 'watch')
                return

            if name in SHELLS:
                self.unwrap_shell(command)
                return

            if name in ('source', '.'):
                self.unwrap_source(command)
                return

            if name == 'trap':
                self.unwrap_trap(command)
                return

            if re.fullmatch(r'git-[a-z][a-z0-9-]*', name):
                # git runs `git-<name>` executables from its exec path as subcommands, and running
                # one directly does the same thing, so judge it as `git <name>`.
                subcommand = Word(value=name[len('git-'):], raw=head.raw)
                command.words = [Word(value='git', raw=head.raw), subcommand] + command.words[1:]
                command.wrappers = command.wrappers + [GIT_EXEC_PATH_WRAPPER]

            if command.name == 'git':
                self.unwrap_git_runners(command)

            # Only bash's own builtins evaluate subscripts; `env printf` runs the external binary.
            builtin = set(command.wrappers) <= {'command', 'builtin'}
            if builtin and command.name in ARITHMETIC_BUILTINS:
                for word in command.words[1:]:
                    if word.value is not None and QUOTED_SUBSCRIPT.search(word.value):
                        self.flag_subscript_expansion(word.value)
                        break

            self.emit(command)
            return

    def peel(self, command, wrapper, rest):
        command.words = rest
        command.wrappers = command.wrappers + [wrapper]

    def skip_options(self, words, spec, wrapper):
        """Drop leading options from a wrapper's arguments, returning what follows, or None.

        None means an option couldn't be read -- it expands at run time, or `spec` doesn't know
        it -- and the command has already been emitted as opaque.
        """
        index = 0
        while index < len(words):
            word = words[index]
            if word.value is None or word.glob or word.brace:
                return self.opaque_wrapper(words, wrapper)
            value = word.value
            if value == '--':
                return words[index + 1:]
            if not value.startswith('-') or value == '-':
                return words[index:]
            consumed = self.option_length(value, words[index + 1:], spec)
            if consumed is None:
                return self.opaque_wrapper(
                    words, wrapper, f'`{wrapper}` has an option this hook does not know, `{value}`',
                )
            if not self.option_value_is_readable(words, index, consumed):
                return self.opaque_wrapper(words, wrapper)
            index += consumed
        return []

    @staticmethod
    def cluster_has_flag(value, spec, letters):
        """True when a short cluster sets one of `letters` before any letter that takes a value."""
        for letter in value[1:]:
            if letter in letters:
                return True
            if letter in spec.short_values or letter in spec.short_optional:
                return False
        return False

    @staticmethod
    def option_value_is_readable(words, index, consumed):
        """False when an option's separate value could expand into more than one word.

        `env -u w{x,}p db` brace-expands to `env -u wxp wp db`, so a value that globs, braces, or
        expands can shift which word is the program.
        """
        if consumed < 2 or index + 1 >= len(words):
            return True
        value = words[index + 1]
        return value.value is not None and not (value.glob or value.brace)

    @staticmethod
    def option_length(value, following, spec):
        """How many words the option `value` uses, counting itself, or None if `spec` doesn't
        know it."""
        if value in spec.word_flags:
            return 1
        if value in spec.word_values:
            return 2
        if value.startswith('--'):
            name = value.split('=', 1)[0]
            if name in spec.long_flags:
                return 1
            if name in spec.long_values:
                return 1 if '=' in value else 2
            return None
        if spec.numeric and value[1:].isdigit():
            return 1
        for position, letter in enumerate(value[1:], start=1):
            if letter in spec.short_optional:
                return 1
            if letter in spec.short_values:
                attached = position + 1 < len(value)
                return 1 if attached else 2
            if letter not in spec.short_flags:
                return None
        return 1

    def opaque_wrapper(self, words, wrapper, reason=None):
        self.emit(Command(
            words=words, raw='', wrappers=self.base_wrappers + [wrapper],
            nested=self.base_nested,
            opaque=reason or (
                f'an argument to `{wrapper}` expands at run time, '
                'so this hook cannot tell what it runs'
            ),
        ))
        return None

    def runs_through_shell(self, command):
        """Handle `sudo -s`/`-i` and `doas -s`, which run their command through a shell.

        Returns True when the command was emitted here.
        """
        name = command.name
        shell_letters = 'si' if name == 'sudo' else 's'
        spec = TRANSPARENT_WRAPPERS[name]
        spec = OptionSpec(
            short_flags=spec.short_flags + shell_letters,
            short_values=spec.short_values,
            long_flags=spec.long_flags | {'--shell', '--login'},
            long_values=spec.long_values,
        )
        # Only sudo's own options count; `sudo git commit -s` signs a commit.
        words = command.words[1:]
        index = 0
        uses_shell = False
        while index < len(words):
            value = words[index].value
            if value is None or value == '--' or not value.startswith('-') or value == '-':
                break
            consumed = self.option_length(value, words[index + 1:], spec)
            if consumed is None:
                return False
            if value in ('--shell', '--login') or (
                not value.startswith('--') and self.cluster_has_flag(value, spec, shell_letters)
            ):
                uses_shell = True
            index += consumed
        if not uses_shell:
            return False
        rest = self.skip_options(command.words[1:], spec, name)
        if rest is None:
            return True
        if not rest or name == 'doas':
            command.opaque = (
                f'`{name} -s` starts a shell that reads commands this hook cannot see'
            )
            self.emit(command)
            return True
        self.unwrap_string(command, rest, f'{name} -s', quote=True)
        return True

    def unwrap_env(self, command):
        """Peel `env` and its assignments. Returns True when the command was emitted."""
        words = command.words[1:]
        index = 0
        while index < len(words):
            word = words[index]
            if word.value is None or word.glob or word.brace:
                self.opaque_wrapper(words[index:], 'env')
                return True
            value = word.value
            if value == '--':
                index += 1
                break
            if value in ('-S', '--split-string') or value.startswith(('-S', '--split-string=')):
                if value in ('-S', '--split-string'):
                    split = words[index + 1:index + 2]
                    after = words[index + 2:]
                else:
                    split = [Word(
                        value=value.split('=', 1)[1] if '=' in value else value[2:],
                        raw=word.raw,
                    )]
                    after = words[index + 1:]
                command.wrappers = command.wrappers + ['env']
                self.unwrap_string(command, split + after, 'env -S')
                return True
            if ENV_ASSIGNMENT.match(value):
                name, assigned = value.split('=', 1)
                command.assigns = command.assigns + [(name, Word(value=assigned, raw=word.raw))]
                index += 1
                continue
            if value == '-':
                # A lone `-` means `-i`.
                index += 1
                continue
            if value.startswith('-'):
                consumed = self.option_length(value, words[index + 1:], ENV_OPTIONS)
                if consumed is None:
                    self.opaque_wrapper(
                        words, 'env', f'`env` has an option this hook does not know, `{value}`',
                    )
                    return True
                if not self.option_value_is_readable(words, index, consumed):
                    self.opaque_wrapper(words, 'env')
                    return True
                index += consumed
                continue
            break
        rest = words[index:]
        while rest and rest[0].literal and ENV_ASSIGNMENT.match(rest[0].value):
            name, assigned = rest[0].value.split('=', 1)
            command.assigns = command.assigns + [(name, Word(value=assigned, raw=rest[0].raw))]
            rest = rest[1:]
        if not rest:
            self.emit(command)
            return True
        self.peel(command, 'env', rest)
        return False

    @staticmethod
    def watch_option_execs(value):
        """True when this `watch` option word turns on `-x`, walking a cluster the way getopt
        does."""
        if value == '--exec' or (len(value) > 3 and '--exec'.startswith(value.split('=', 1)[0])):
            return True
        if not value.startswith('-') or value.startswith('--'):
            return False
        for letter in value[1:]:
            if letter == 'x':
                return True
            if letter in WATCH_OPTIONS.short_values or letter in WATCH_OPTIONS.short_optional:
                # The rest of the cluster is this option's value.
                return False
        return False

    def unwrap_git_runners(self, command):
        """Emit the commands git subcommands like `bisect run` and `rebase -x` run for you.

        The git command itself is still emitted by the caller, so the hooks judge both.
        """
        words = command.words
        index = 1
        while index < len(words) and words[index].value and words[index].value.startswith('-'):
            option = words[index].value.split('=', 1)[0]
            if option in GIT_GLOBAL_VALUE_OPTIONS:
                index += 1 if '=' in words[index].value else 2
            elif option in GIT_GLOBAL_FLAGS:
                index += 1
            else:
                # Guessing how many words an unknown global takes could misplace the subcommand.
                self.emit(self.detached(command, 'git', opaque=(
                    f'`git {option}` is a global option this hook does not know'
                )))
                return
        if index >= len(words) or not words[index].literal:
            return
        subcommand = words[index].value
        rest = words[index + 1:]
        wrapper = f'git {subcommand}'

        if subcommand == 'bisect' and rest[:1] and rest[0].value == 'run':
            inner = Command(
                words=rest[1:], raw=command.raw, wrappers=command.wrappers + ['git bisect run'],
                nested=True,
            )
            self.unwrap(inner)
            return

        if subcommand == 'submodule':
            while rest and rest[0].value in ('-q', '--quiet', '--cached'):
                rest = rest[1:]
            if rest and rest[0].value is None:
                self.emit(self.detached(command, wrapper, opaque=(
                    'the `git submodule` action expands at run time and could be `foreach`'
                )))
                return
            if rest and rest[0].value == 'foreach':
                script = rest[1:]
                while script and script[0].value in ('--recursive', '-q', '--quiet'):
                    script = script[1:]
                self.unwrap_string(
                    self.detached(command, 'git submodule foreach'),
                    script,
                    'git submodule foreach',
                )
            return

        # Options whose value git hands to a shell.
        config_options = GIT_CONFIG_SETTING_OPTIONS.get(subcommand, frozenset())
        config_letters = {option[1] for option in config_options if not option.startswith('--')}
        for word in rest:
            name = (word.value or '').split('=', 1)[0]
            long_match = name.startswith('--') and len(name) > 2 and any(
                option.startswith(name) for option in config_options if option.startswith('--')
            )
            # Any short cluster holding the letter counts, which errs toward a prompt when an
            # earlier letter in the cluster actually takes it as a value.
            short_match = (
                name.startswith('-') and not name.startswith('--')
                and bool(config_letters & set(name[1:]))
            )
            if long_match or short_match:
                self.emit(self.detached(command, wrapper, opaque=(
                    f'`{wrapper} {name}` sets config or templates, which can make git run a '
                    'program'
                )))
                return

        shell_value_options = GIT_SHELL_VALUE_OPTIONS.get(subcommand, frozenset())
        short_letters = {option[1] for option in shell_value_options if not option.startswith('--')}
        position = 0
        while position < len(rest):
            word = rest[position]
            value = word.value or ''
            name = value.split('=', 1)[0]
            matched = name in shell_value_options or (
                name.startswith('--') and len(name) > 2
                and any(
                    option.startswith(name)
                    for option in shell_value_options
                    if option.startswith('--')
                )
            )
            # In a short cluster like `-ix'cmd'`, the script starts right after the letter.
            cluster_letter = None
            if value.startswith('-') and not value.startswith('--'):
                cluster_letter = next(
                    (
                        offset
                        for offset, letter in enumerate(value[1:], start=1)
                        if letter in short_letters
                    ),
                    None,
                )
            if cluster_letter is not None and cluster_letter + 1 < len(value):
                script = [Word(value=value[cluster_letter + 1:], raw=word.raw)]
                self.unwrap_string(
                    self.detached(command, wrapper),
                    script,
                    f'{wrapper} -{value[cluster_letter]}',
                )
                position += 1
                continue
            if cluster_letter is not None:
                matched = True
                name = f'-{value[cluster_letter]}'
            if matched:
                canonical = next(
                    (option for option in shell_value_options if option.startswith(name)), name,
                )
                optional = f'{subcommand} {canonical}' in GIT_OPTIONAL_VALUE_OPTIONS
                if optional and '=' not in value:
                    position += 1
                    continue
                if '=' in value and value.startswith('--'):
                    script = [Word(value=value.split('=', 1)[1], raw=word.raw)]
                    position += 1
                else:
                    script = rest[position + 1:position + 2]
                    position += 2
                self.unwrap_string(self.detached(command, wrapper), script, f'{wrapper} {name}')
                continue
            if word.value is None and shell_value_options:
                self.emit(self.detached(command, wrapper, opaque=(
                    f'an argument to `{wrapper}` expands at run time and could name a command '
                    'for git to run'
                )))
                return
            position += 1

    def detached(self, command, wrapper, opaque=None):
        """A fresh nested command to hang what `wrapper` runs on, leaving `command` untouched."""
        return Command(
            words=[], raw=command.raw, wrappers=command.wrappers + [wrapper], nested=True,
            opaque=opaque,
        )

    def unwrap_find(self, command):
        """Emit `find` itself, plus each command its `-exec`-style actions run."""
        words = command.words
        index = 1
        while index < len(words):
            word = words[index]
            if word.literal and word.value in FIND_EXEC_ACTIONS:
                end = index + 1
                while end < len(words) and not (
                    words[end].literal and words[end].value in (';', '+')
                ):
                    end += 1
                inner = Command(
                    words=words[index + 1:end], raw=command.raw, assigns=list(command.assigns),
                    wrappers=command.wrappers + [f'find {word.value}'], nested=command.nested,
                    dynamic_args=True,
                )
                self.unwrap(inner)
                index = end + 1
                continue
            index += 1
        self.emit(command)

    def unwrap_string(self, command, words, wrapper, quote=False):
        """Reparse words a wrapper joins into a command string, or mark the command opaque.

        `eval` and `watch` join their words with plain spaces, so quoting inside them is
        reparsed. `quote` is for wrappers like `sudo -s` that escape each word first.
        """
        if not words or not all(word.literal for word in words):
            command.opaque = (
                f'`{wrapper}` runs a command string that expands at run time, so this hook '
                'cannot read it'
            )
            self.emit(command)
            return
        join_word = sudo_escape if quote else (lambda value: value)
        text = ' '.join(join_word(word.value) for word in words)
        self.reparse(command, text, wrapper)

    def unwrap_shell(self, command):
        """Treat `bash -c '...'` and `bash` reading stdin as wrappers; leave `bash script.sh`
        alone."""
        name = command.name
        words = command.words[1:]
        index = 0
        runs_string = False
        reads_stdin = False
        while index < len(words):
            word = words[index]
            # A leading `~` can only expand to a home directory, never to an option, so a script
            # path like `~/bin/x.sh` is still readable here.
            if word.value is None or word.glob or word.brace:
                self.opaque_wrapper(words, name)
                return
            value = word.value
            if value == '--':
                index += 1
                break
            if value in SHELL_VALUE_OPTIONS:
                if not self.option_value_is_readable(words, index, 2):
                    self.opaque_wrapper(words, name)
                    return
                index += 2
                continue
            if value == '--command':
                # fish's long spelling of `-c`.
                runs_string = True
                index += 1
                continue
            if value.startswith('--'):
                if value.split('=', 1)[0] not in SHELL_LONG_FLAGS:
                    self.opaque_wrapper(
                        words, name, f'`{name}` has an option this hook does not know, `{value}`',
                    )
                    return
                index += 1
                continue
            if value[:1] in ('-', '+') and len(value) > 1:
                letters = value[1:]
                if 'C' in letters and name == 'fish':
                    # fish's `-C` runs its value as code before anything else.
                    self.opaque_wrapper(words, name, '`fish -C` runs code this hook cannot read')
                    return
                unknown = set(letters) - SHELL_SHORT_FLAGS - set('oO')
                if unknown:
                    self.opaque_wrapper(
                        words, name, f'`{name}` has an option this hook does not know, `{value}`',
                    )
                    return
                if 'c' in letters:
                    runs_string = True
                if 's' in letters or 'i' in letters:
                    reads_stdin = True
                # `-o`/`-O` take a value: the rest of the cluster, or the next word when last.
                takes_value = next((letter for letter in letters if letter in 'oO'), None)
                if (
                    takes_value
                    and letters.endswith(takes_value)
                    and letters.count(takes_value) == 1
                ):
                    if not self.option_value_is_readable(words, index, 2):
                        self.opaque_wrapper(words, name)
                        return
                    index += 2
                    continue
                if takes_value:
                    self.opaque_wrapper(
                        words,
                        name,
                        f'`{name}` has an option cluster this hook cannot read, `{value}`',
                    )
                    return
                index += 1
                continue
            break
        rest = words[index:]

        reads_commands = runs_string or reads_stdin or not rest or rest[0].value in STDIN_SCRIPT_PATHS
        if reads_commands and name not in BASH_GRAMMAR_SHELLS:
            # zsh, fish, and ksh parse differently enough that reading their code with bash's
            # grammar could miss what runs.
            command.opaque = f'`{name}` runs code in a grammar this hook does not parse'
            self.emit(command)
            return

        if runs_string:
            if not rest:
                command.opaque = f'`{name} -c` has no command string to read'
                self.emit(command)
                return
            self.unwrap_string(command, rest[:1], f'{name} -c')
            return

        if rest and rest[0].value in STDIN_SCRIPT_PATHS:
            reads_stdin = True

        if rest and not reads_stdin:
            # A script path. The hooks can't see inside it, and settings.json allows specific ones.
            self.emit(command)
            return

        self.reparse_stdin(command, name)

    def unwrap_trap(self, command):
        """`trap 'string' SIGNAL` runs the string later, like `eval`, when the signal or exit
        fires."""
        arguments = command.words[1:]
        while arguments and arguments[0].value in ('--',):
            arguments = arguments[1:]
        if not arguments or arguments[0].value in ('-p', '-l', '-P', '-'):
            self.emit(command)
            return
        self.unwrap_string(command, arguments[:1], 'trap')

    def unwrap_source(self, command):
        """`source` and `.` run a file in this shell; one read from stdin is a wrapper."""
        operand = command.words[1] if len(command.words) > 1 else None
        if operand is None:
            self.emit(command)
            return
        if operand.value is None:
            command.opaque = f'`{command.name}` runs a file whose name expands at run time'
            self.emit(command)
            return
        if operand.value in STDIN_SCRIPT_PATHS:
            self.reparse_stdin(command, command.name)
            return
        self.emit(command)

    def reparse_stdin(self, command, name):
        """Reparse the heredoc or here-string a shell reads commands from, or mark it opaque."""
        # Only the last redirect of stdin decides what the shell reads, so a heredoc followed by
        # `< file` reads the file. Reparse a heredoc only when it's the one stdin redirect.
        stdin_redirects = [
            redirect for redirect in command.redirects
            if redirect.fd in (None, '0') and redirect.op in ('<', '<<', '<<-', '<<<', '<&', '<>')
        ]
        heredoc = stdin_redirects[0] if len(stdin_redirects) == 1 else None
        body = None
        if heredoc is not None and heredoc.op in ('<<', '<<-', '<<<'):
            body = heredoc.heredoc if heredoc.op != '<<<' else heredoc.target
        if body is not None and body.value is not None:
            command.redirects = [
                redirect for redirect in command.redirects if redirect is not heredoc
            ]
            self.reparse(command, body.value, f'{name} reading a heredoc')
            return
        command.opaque = f'`{name}` reads commands from stdin, which this hook cannot see'
        self.emit(command)


def parse(text):
    """Parse one Bash tool call. Raises ParseError when the line can't be read."""
    parser = LineParser(text)
    try:
        parser.walk_statements(syntax_tree(text).get('Stmts', []), nested=False, top_level=True)
    except ParseError:
        raise
    except Exception as error:
        # Any surprise in the tree is a line this module didn't understand, which the hooks must
        # treat like one bash couldn't parse rather than let a traceback read as "no opinion".
        raise ParseError(f'this line could not be analyzed: {error!r}') from error
    return Parsed(commands=parser.commands, chain=parser.chain)


def join(words):
    """Render literal words back into one shell-quoted string, for messages."""
    return ' '.join(
        shlex.quote(word.value) if word.value is not None else word.raw for word in words
    )
