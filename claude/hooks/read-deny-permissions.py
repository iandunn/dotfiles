#!/usr/bin/env python3
"""
PreToolUse gate that asks when a Bash line could read a path settings.json denies the Read tool.

The `Read(...)` deny rules keep the Read tool away from files like `.npmrc` and `~/.ssh/*`, but
`Bash(cat *)`, `Bash(wc *)`, and the other read allows would print the same files with no prompt,
and the sandbox's read denylist doesn't block all of them, like `~/.npmrc`. The set of programs
that can read a file is open-ended, so this hook doesn't keep a list of them. It checks every word
on the line instead, whatever the program: arguments, the program word itself, assignment values,
redirect targets, `for` lists, and the words inside a `bash -c` string or `$(...)`. A hook's `ask`
overrides a settings.json allow rule, so the read allows can stay.

A literal word is resolved the way bash would see it: `~` expanded, globs matched against the
disk, and braces expanded. A relative path is resolved against the session's cwd and against each
literal `cd` or `pushd` target on the line. The text after a word's first `=`, `@`, or `:`, and
after a short option's letter, is checked too, so `--file=~/.npmrc`, `-d @auth.json`, and `-f.npmrc`
are caught. Each candidate is checked as written and with its links resolved.

A word that isn't a path on disk, like `$HOME/.ssh/id_rsa` or the script in `python3 -c "..."`,
asks when its text contains the last literal component of a deny rule, like `.ssh`, after quotes
and backslashes are dropped and braces expanded. One that hides the name entirely, like
`$(printf '\\x2essh')`, gets past this check; the program inside the substitution is still
scanned, though.

This hook is a second layer behind the sandbox, which blocks the paths a `Read(...)` rule names
explicitly. See `README.md`.

A recursive search names only a parent directory, so two more checks cover it. `rg` is trusted to
skip denied files only when `RIPGREP_CONFIG_PATH` points at a config that excludes every denied
name, and the line has a shape this hook can read in full: known words, allowlisted options, and
positive globs only like `'*.php'`. `fd -x` and `-X` ask when a
denied file exists under a directory they search, or a link there points at one. `grep` and `find`
are denied by `dangerous-command-shapes.py`, so neither needs the same treatment.

Repository content isn't a path on disk, so `git show HEAD:auth.json` is judged by where
`auth.json` would sit in the cwd, which asks. That's accepted as a false positive.

A line the parser can't read asks. So does one when the user's settings can't be read, since the
hook can't tell what's denied. A crash asks too, rather than exiting non-zero and leaving the
command to the allow rules.
"""
import fnmatch
import glob
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import bash_ast
    from read_deny import (
        denied_names, fold, is_read_denied, mentions_denied_name, read_deny_patterns,
    )
except ImportError as error:
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'ask',
            'permissionDecisionReason': (
                f'A helper module failed to load, so this hook cannot check the command: {error}'
            ),
        }
    }))
    sys.exit(0)


# Where a path can start inside a word that also carries an option name or other prefix.
EMBEDDED_PATH_SEPARATORS = ('=', '@', ':')

# Characters that separate the components of a word's text when looking for a denied name.
NAME_BOUNDARY = re.compile(r'''[/\s=:@$()`;<>|&,{}\[\]]+''')

# Options that hand a program a file holding the names of more files to read, which this hook
# never sees, like `sort --files0-from=list`.
FILE_LIST_OPTIONS = ('--files0-from', '--files-from')

# Quoting that bash removes before a program sees the word, so `.n\pmrc` and `.ss"h"` are `.npmrc`
# and `.ssh`.
QUOTING = re.compile(r'''["'\\]''')

# Parameter expansions and command substitutions, any of which can expand to nothing.
EXPANSION = re.compile(
    r'\$\{[^}]*\}|\$\([^)]*\)|`[^`]*`|\$[A-Za-z_][A-Za-z0-9_]*|\$[0-9@*#?$!-]'
)

# The start of a `${name<operator>word}` expansion, up to where its default or alternate begins.
PARAMETER_OPERATOR = re.compile(
    r'\$\{[#!]?[A-Za-z_0-9@*]*(:?[-=+?]|#{1,2}|%{1,2}|/{1,2}|\^{1,2}|,{1,2}|:)?'
)

# Stands in for an expansion's unknown text. A character no name boundary or name contains.
EXPANSION_MARK = '\x00'

DIRECTORY_CHANGING_PROGRAMS = frozenset({'cd', 'pushd'})

# Options that make a program like `tar`, `git`, or `make` read its operands from another directory.
DIRECTORY_OPTIONS = frozenset({'-C', '--directory', '--cwd', '--chdir', '--work-tree'})

# Programs whose `-C` changes directory. For others, like `rg -C 3`, it means something else.
SHORT_C_DIRECTORY_PROGRAMS = frozenset({'git', 'tar', 'gtar', 'bsdtar', 'make', 'gmake'})

RIPGREP_CONFIG_VARIABLE = 'RIPGREP_CONFIG_PATH'

# The `rg` options that pass without a prompt, as of ripgrep 15. Keep these allowlists, so an
# option that undoes the config, follows links, or runs a program, like `--no-config`, `-L`, or
# `--pre`, asks without having to be named.
RIPGREP_FLAG_LETTERS = frozenset('.0abcFhHiIlnNopPqsSuUvVwxz')
RIPGREP_VALUE_LETTERS = frozenset('ABCdeEfgjmMrtT')
RIPGREP_FLAG_LONGS = frozenset({
    '--ignore-case', '--smart-case', '--case-sensitive', '--fixed-strings', '--line-number',
    '--no-line-number', '--files-with-matches', '--files-without-match', '--count',
    '--count-matches', '--word-regexp', '--line-regexp', '--invert-match', '--hidden',
    '--no-ignore', '--no-ignore-vcs', '--json', '--vimgrep', '--no-heading', '--heading',
    '--with-filename', '--no-filename', '--only-matching', '--quiet', '--files', '--multiline',
    '--multiline-dotall', '--pcre2', '--text', '--null', '--unrestricted', '--no-messages',
    '--trim', '--column', '--stats', '--byte-offset', '--passthru', '--sort-files',
    '--version', '--help', '--type-list', '--search-zip', '--pretty', '--no-require-git',
    '--one-file-system', '--glob-case-insensitive', '--no-ignore-parent', '--no-ignore-dot',
    '--include-zero', '--crlf', '--null-data', '--binary', '--no-encoding', '--mmap',
    '--no-mmap', '--line-buffered', '--block-buffered', '--no-unicode', '--no-ignore-global',
    '--no-ignore-files', '--no-ignore-exclude', '--no-ignore-messages', '--no-column',
    '--no-trim', '--no-stats', '--no-json', '--no-context-separator', '--stop-on-nonmatch',
    '--no-stop-on-nonmatch', '--max-columns-preview', '--debug', '--trace',
})
RIPGREP_VALUE_LONGS = frozenset({
    '--regexp', '--file', '--glob', '--iglob', '--type', '--type-not', '--max-count',
    '--max-depth', '--maxdepth', '--context', '--after-context', '--before-context',
    '--max-columns', '--replace', '--sort', '--sortr', '--threads', '--encoding', '--color',
    '--colors', '--max-filesize', '--ignore-file', '--context-separator', '--engine',
    '--hyperlink-format', '--field-match-separator',
})

# The short letter each long option that matters to this hook stands for.
RIPGREP_LONG_LETTERS = {'--regexp': 'e', '--file': 'f', '--glob': 'g', '--iglob': 'g'}

# Glob syntax that rg and bash read differently from Python's `fnmatch`, which this hook matches
# with: a backslash escape, `[^x]` negation, and `[[:lower:]]` classes.
FOREIGN_GLOB_SYNTAX = ('\\', '[^', '[:')

# A word with more brace groups than this asks rather than being expanded, since each group
# doubles the work and a hook that runs out of time gives no verdict.
BRACE_GROUP_LIMIT = 10

# Variables whose value the hook knows, so a word built on them can still be checked by name.
KNOWN_VARIABLES = re.compile(r'\$\{(?:HOME|PWD)\}|\$(?:HOME|PWD)(?![A-Za-z0-9_])|~\+(?=/|$)')

# macOS opens a file by its device and inode under this path, which no deny rule can match.
INODE_PATH = '/.vol/'
# Programs that read a script from a file the hook can't see, and the options that name it.
SCRIPT_FILE_OPTIONS = {
    'sed': ('-f', '--file'), 'gsed': ('-f', '--file'),
    'awk': ('-f', '--file', '-i', '--include', '-E', '--exec'),
    'gawk': ('-f', '--file', '-i', '--include', '-E', '--exec'),
    'mawk': ('-f',), 'nawk': ('-f',),
    'jq': ('-f', '--from-file', '-L', '--library-path'),
    'gojq': ('-f', '--from-file', '-L'), 'jaq': ('-f', '--from-file', '-L'),
}

# Text in an awk program that can build a file name at run time and then read it, or hand a
# command to a shell this hook never parses.
AWK_PROGRAMS = frozenset({'awk', 'gawk', 'mawk', 'nawk'})
AWK_RUN_TIME_READS = ('ARGV', 'ENVIRON', 'getline', 'system')

# A pipe in an awk program, which runs a command through a shell. `||` is a logical or.
AWK_PIPE = re.compile(r'(?<!\|)\|(?!\|)')

# jq can load a module from a file the line never names, like `import "auth" as $a`, which
# reads `auth.json` from a `-L` folder.
JQ_PROGRAMS = frozenset({'jq', 'gojq', 'jaq'})
JQ_MODULE = re.compile(r'\b(?:import|include)\b')

# Commands that can change rg's environment for the rest of a line.
ENVIRONMENT_CHANGING_BUILTINS = frozenset({
    'unset', 'export', 'declare', 'typeset', 'readonly', 'local', 'set', 'source', '.', 'eval',
    'hash', 'alias', 'enable',
})

# Wrappers that run `rg` with the environment it was given. Anything else, like `env -i`, `sudo`,
# or `xargs` handing it file names, asks.
RIPGREP_WRAPPERS = frozenset({'command', 'bash -c', 'sh -c', 'fd -x', 'fd -X', 'nice', 'timeout'})

# Wrappers that hand a program file names this hook never sees, from stdin or a file.
FILE_NAME_FEEDING_WRAPPERS = frozenset({'xargs'})

# Wrapper options that run the program in another directory, like `env -C ~/.config cat gh/x`.
WRAPPER_DIRECTORY_OPTIONS = {
    'env': re.compile(r'(?:^|\s)(?:-[A-Za-z]*C|--chdir)'),
    'sudo': re.compile(r'(?:^|\s)(?:-[A-Za-z]*D|--chdir)'),
}

# A shell started with an option, like `bash -O dotglob -c '...'` or `sh -o posix`.
SHELL_OPTION = re.compile(
    r'(?:^|[\s;&|(`$])(?:\S*/)?(?:bash|sh|zsh|ksh|dash)\s+(?:[-+]\S+\s+)*?[-+][A-Za-z]*[Oo](?:\s|$)'
)

# Variables that change what a line reads without the line naming it.
LINE_CHANGING_VARIABLES = {
    'CDPATH': 'can send a `cd` somewhere the line never names',
    'BASHOPTS': 'can turn on `dotglob` or `extglob` in a shell, changing what a glob matches',
    'SHELLOPTS': 'can change how a shell reads the rest of the line',
}

# An extglob pattern, like `.@(npmrc)` or `!(x)`, which Python's `glob` can't resolve.
EXTGLOB = re.compile(r'[?*+@!]\(')

# How many seconds the search for denied files under every `fd -x` directory may take in total
# before it asks, and how many links it checks.
FD_SEARCH_BUDGET = 5
FD_LINK_LIMIT = 2000


def emit(decision, reason):
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': decision,
            'permissionDecisionReason': reason,
        }
    }))


def expand_braces(text):
    """Every word a brace expression like `~/.{npmrc,bashrc}` turns into, or None if it can't tell.

    Only comma lists are expanded. A sequence like `{1..3}` returns None, and so does a word with
    more than `BRACE_GROUP_LIMIT` groups.
    """
    if text.count('{') > BRACE_GROUP_LIMIT:
        return None
    depth = 0
    start = None
    for index, character in enumerate(text):
        if character == '{':
            if depth == 0:
                start = index
            depth += 1
        elif character == '}' and depth:
            depth -= 1
            if depth == 0:
                body = text[start + 1:index]
                options = split_top_level_commas(body)
                if len(options) < 2:
                    if '..' in body:
                        return None
                    continue
                prefix, suffix = text[:start], text[index + 1:]
                expanded = []
                for option in options:
                    words = expand_braces(prefix + option + suffix)
                    if words is None:
                        return None
                    expanded += words
                return expanded
    return [text]


def split_top_level_commas(body):
    parts, depth, current = [], 0, ''
    for character in body:
        if character == ',' and depth == 0:
            parts.append(current)
            current = ''
            continue
        if character == '{':
            depth += 1
        elif character == '}':
            depth -= 1
        current += character
    parts.append(current)
    return parts


def candidate_texts(value):
    """The word itself, plus whatever follows an option letter or an embedded separator."""
    texts = [value]
    if re.match(r'-[A-Za-z]', value) and not value.startswith('--'):
        texts.append(value[2:])
    for separator in EMBEDDED_PATH_SEPARATORS:
        if separator in value:
            texts.append(value.split(separator, 1)[1])
    return [text for text in texts if text]


def expand_tilde(text, cwd):
    """The text with a leading `~`, `~user`, or `~+` expanded the way bash would.

    `os.path.expanduser` leaves `~+`, the cwd, alone, so a path through it would be checked as a
    relative path that doesn't exist.
    """
    if text == '~+' or text.startswith('~+/'):
        return cwd + text[2:]
    return os.path.expanduser(text)


def resolve(text, word, bases):
    """The absolute paths bash could hand the program for this text, links resolved and not."""
    text = expand_tilde(text, bases[0])
    texts = [text]
    if word.glob:
        texts += glob.glob(text) if os.path.isabs(text) else [
            match for base in bases for match in glob.glob(os.path.join(base, text))
        ]
    paths = []
    for candidate in texts:
        joined = [candidate] if os.path.isabs(candidate) else [
            os.path.join(base, candidate) for base in bases
        ]
        for path in joined:
            normal = os.path.normpath(path)
            for resolved in (normal, os.path.realpath(normal)):
                # A trailing slash lets a rule like `~/.ssh/**` cover the directory itself, which
                # `ls` or `rg` would read through.
                paths.append(resolved + '/' if os.path.isdir(resolved) else resolved)
    return paths


def name_components(text):
    """The path components in a word's text, with `.` dropped and `..` applied."""
    components = []
    for component in NAME_BOUNDARY.split(fold(text)):
        if component in ('', '.'):
            continue
        if component == '..' and components:
            components.pop()
            continue
        components.append(component)
    return components


def mentioned_name(text, names):
    """The denied name this text spells out, '' when its braces can't be expanded, or None."""
    unquoted = QUOTING.sub('', text)
    variants = (
        unquoted,
        # An expansion can be empty, so `.np${Y}mrc` may be `.npmrc`.
        EXPANSION.sub('', unquoted),
        # Or its default, so `.npmr${X:-c}` and `${X:-.npmrc}` may be `.npmrc`.
        PARAMETER_OPERATOR.sub('', unquoted).replace('}', ''),
    )
    for variant in variants:
        expansions = expand_braces(variant)
        if expansions is None:
            return ''
        for expansion in expansions:
            hit = mentions_denied_name(name_components(expansion), names)
            if hit:
                return hit

    # Or anything at all, like `.npmr$(echo c)`, so a component that mixes an expansion with
    # literal text asks when the expansion could complete a denied name.
    for expansion in expand_braces(EXPANSION.sub(EXPANSION_MARK, unquoted)) or []:
        components = [
            component for component in NAME_BOUNDARY.split(fold(expansion)) if component
        ]
        for component in components:
            if EXPANSION_MARK not in component or component == EXPANSION_MARK:
                continue
            pattern = component.replace(EXPANSION_MARK, '*')
            for name in names:
                if any(fnmatch.fnmatchcase(part, pattern) for part in name):
                    return '/'.join(name)
    return None


def word_reason(word, bases, globs, names, directory_prefixes):
    """Why this word may name a denied path, or None."""
    if word is None:
        return None
    values = None
    if word.value is not None:
        values = expand_braces(word.value) if word.brace else [word.value]
    if word.brace and values is None:
        return f'`{word.raw}` has a brace sequence this hook cannot expand'
    if word.value is None and word.glob:
        # Like `$HOME/.n?mrc`: the variable hides where the wildcard matches, and the wildcard
        # hides the name from the check below.
        return f'`{word.raw}` expands at run time and has a wildcard, so it could match any file'
    if word.glob and any(syntax in word.raw for syntax in FOREIGN_GLOB_SYNTAX[1:]):
        return f'`{word.raw}` uses glob syntax this hook cannot match the way bash does'
    if INODE_PATH.rstrip('/') in word.raw:
        return f'`{word.raw}` may open a file by its inode, which no deny rule can match'
    if re.search(r'(?:^|[=:"\'])~-', word.raw):
        return f'`{word.raw}` starts in the previous directory, which this hook cannot see'
    if word.value is None and EXTGLOB.search(word.raw):
        return f'`{word.raw}` may be an extended glob, which this hook cannot resolve'

    names_a_path = False
    for value in values or []:
        for text in candidate_texts(value):
            for path in resolve(text, word, bases):
                if is_read_denied(path, globs):
                    return f'`{word.raw}` names `{path}`, which settings.json denies the Read tool'
                if path.startswith(INODE_PATH):
                    return f'`{word.raw}` opens a file by its inode, which no deny rule can match'
                names_a_path = names_a_path or os.path.lexists(path.rstrip('/'))

    # A path that exists was judged above, so a project's own `.docker/` doesn't ask just for
    # sharing a name with `~/.docker`. Anything else may be text a program reads a path out of,
    # and after a directory change that expands, an existing path may be read from elsewhere.
    if names_a_path and not directory_prefixes:
        return None
    # `$PWD` and `~+` are the cwd, so from `~/.config`, `$PWD/gh` spells out `.config/gh`.
    known = KNOWN_VARIABLES.sub(
        lambda match: os.path.expanduser('~') if 'HOME' in match.group(0) else bases[0],
        word.raw,
    )
    for prefix in [''] + directory_prefixes:
        hit = mentioned_name(f'{prefix}/{word.raw}', names) or (
            known != word.raw and mentioned_name(f'{prefix}/{known}', names)
        )
        if hit == '':
            return f'`{word.raw}` has braces this hook cannot expand'
        if hit:
            return f'`{word.raw}` mentions `{hit}`, which settings.json denies the Read tool'
    return None


def tree_words(node, parser):
    """Every word node anywhere in shfmt's syntax tree, including `for` lists and `[[ ]]` tests."""
    if isinstance(node, dict):
        if 'Parts' in node and 'Type' not in node:
            yield parser.word(node)
        for child in node.values():
            yield from tree_words(child, parser)
    elif isinstance(node, list):
        for child in node:
            yield from tree_words(child, parser)


def command_words(command):
    yield from command.words
    for _name, value in command.assigns:
        yield value
    for redirect in command.redirects:
        yield redirect.target


def option_directories(command, cwd):
    """Directories a program moves into before reading its operands, like `tar -C ~` or `git -C`."""
    directories, expanding = [], []
    words = command.words[1:]
    for index, word in enumerate(words):
        value = word.value or ''
        target = None
        if value == '-C' and command.name not in SHORT_C_DIRECTORY_PROGRAMS:
            continue
        if value in DIRECTORY_OPTIONS and index + 1 < len(words):
            target = words[index + 1].value
            if target is None:
                expanding.append(words[index + 1].raw)
        elif value.startswith('-C') and command.name in SHORT_C_DIRECTORY_PROGRAMS:
            target = value[2:]
        elif '=' in value and value.split('=', 1)[0] in DIRECTORY_OPTIONS:
            target = value.split('=', 1)[1]
        short_c = word.raw.startswith('-C') and command.name in SHORT_C_DIRECTORY_PROGRAMS
        if word.value is None and (short_c or word.raw.startswith(('--directory=', '--chdir='))):
            expanding.append(word.raw)
        if target:
            directories.append(os.path.join(cwd, expand_tilde(target, cwd)))
    return directories, expanding


def directory_bases(parsed, cwd):
    """The directories a relative path could be under, and the raw text of `cd` targets that expand.

    The bases are the session's cwd plus each literal `cd` or `pushd` target on the line. A target
    that expands at run time can't be joined to a path, so its text is returned instead, for the
    name check to put in front of every word.
    """
    bases = [cwd]
    expanding = []
    for command in parsed.commands:
        option_bases, option_expanding = option_directories(command, cwd)
        bases += option_bases
        expanding += option_expanding
        if command.name not in DIRECTORY_CHANGING_PROGRAMS:
            continue
        operands = [word for word in command.words[1:] if not (word.value or '').startswith('-')]
        if not operands:
            bases.append(os.path.expanduser('~'))
            continue
        target = operands[0]
        if target.value is None or target.glob or target.brace:
            expanding.append(target.raw)
            continue
        value = expand_tilde(target.value, cwd) if target.tilde else target.value
        bases += [os.path.join(base, value) for base in list(bases)]
    return bases, expanding


def ripgrep_exclusions(names):
    """The `--glob` lines an rg config needs so a recursive search skips every denied name."""
    return {'--glob-case-insensitive'} | {
        f'--glob=!{name[0]}' if len(name) == 1 else f'--glob=!**/{"/".join(name)}'
        for name in names
    }


def two_part_parents(globs, names):
    """The directory holding each denied path whose name keeps its parent, like `~/.config`."""
    parents = set()
    for glob_pattern in globs:
        literal = glob_pattern.split('*')[0].rstrip('/')
        if not literal.startswith('/'):
            continue
        parent, last = os.path.split(literal)
        if (os.path.basename(parent), last) in names:
            parents.add(parent)
    return parents


def inside_two_part_parent(paths, globs, names):
    """The parent of a two-part denied name that one of these paths sits in, or None.

    rg matches a glob against the path as it walks it, starting from its cwd or a search root
    as written. From `~/.config`, through a link to it, or through `~/.config/gh/..`, it sees
    `gh/hosts.yml`, which `--glob=!**/.config/gh` doesn't match.
    """
    parents = two_part_parents(globs, names)
    for path in paths:
        for spelling in {path, os.path.realpath(path)} if path else ():
            folded = fold(spelling).rstrip('/')
            for parent in parents:
                if folded == parent or folded.startswith(parent + '/'):
                    return parent
    return None


def positive_glob_names(pattern):
    """The file-name parts of a positive `-g` value, like `*.php` in `src/**/*.php`, or None.

    A glob can only bring back a denied file or folder whose own name its last part matches,
    because rg doesn't look inside a folder its config excludes. So the folders before that part
    don't matter, as long as they're literal or `**`, and the hook checks only the last part,
    everywhere rg searches. rg matches the folders from its cwd, not from a search root, so the
    hook doesn't narrow the check to them. A glob using syntax `fnmatch` reads differently from
    rg, like `\\.np?rc` or `[^x]`, returns None.
    """
    names = []
    for each in expand_braces(pattern) or []:
        if any(syntax in each for syntax in FOREIGN_GLOB_SYNTAX):
            return None
        *folders, last = each.strip('/').split('/')
        if not last or any(
            folder != '**' and any(character in folder for character in '*?[')
            for folder in folders
        ):
            return None
        names.append(fold(last))
    return names or None


def ripgrep_word_text(word, cwd):
    """A word's text when it's known before the command runs, or None.

    Beyond literal text, that covers a leading `~` and a leading `$HOME` or `$PWD`, as in
    `"$HOME/dotfiles"`, whose values the hook knows.
    """
    if word.literal:
        return word.value
    if word.tilde and word.value is not None and not word.glob and not word.brace:
        return expand_tilde(word.value, cwd)
    unquoted = QUOTING.sub('', word.raw)
    match = KNOWN_VARIABLES.match(unquoted)
    rest = unquoted[match.end():] if match else ''
    if not match or word.glob or word.brace or re.search(r'[$`~*?\[{]', rest):
        return None
    known = os.path.expanduser('~') if 'HOME' in match.group(0) else cwd
    return known + rest


def root_spelling_reason(path):
    """Why rg could walk this root's denied paths under a spelling its config can't match.

    rg matches globs against the path as written, so `~/.config/./gh`, `~/.config//gh`, and
    `~/.config/gh/..` don't match `**/.config/gh`. A leading `./` or run of `../` is fine, since
    `**` covers it.
    """
    components = path.removesuffix('/').split('/')
    while components[:1] in (['.'], ['..']):
        components = components[1:]
    if any(component in ('', '.', '..') for component in components[1:]):
        return (f'`rg` searches `{path}`, whose `.`, `..`, or `//` can hide a denied path from '
                'its config')
    return None


def ripgrep_reason(command, bases, globs, names, expanding_directories, deadline):
    """Why this `rg` command could read a denied file during a recursive search, or None.

    `rg` passes only in a shape this hook can read in full: plain words, options from an
    allowlist, positive globs like `'*.php'`, and search roots with no `..` that don't sit in
    the parent of a two-part denied name. Anything else asks.
    """
    if command.name != 'rg':
        return None
    if expanding_directories:
        return (f'`rg` runs after a `cd` to `{expanding_directories[0]}`, which expands at run '
                'time, so its config may not match a denied path from there')
    parent = inside_two_part_parent(bases, globs, names)
    if parent:
        return f'`rg` runs inside `{parent}`, where its config cannot match a denied path'
    extra_wrappers = [wrapper for wrapper in command.wrappers if wrapper not in RIPGREP_WRAPPERS]
    if extra_wrappers or command.assigns:
        return (f'`rg` runs under `{(extra_wrappers or ["an assignment"])[0]}`, which could hide '
                f'the {RIPGREP_CONFIG_VARIABLE} config that keeps it out of denied files')

    config_path = os.environ.get(RIPGREP_CONFIG_VARIABLE)
    try:
        with open(config_path) as config:
            lines = {line.strip() for line in config}
    except (OSError, TypeError):
        return (f'{RIPGREP_CONFIG_VARIABLE} is not set to a readable config, so `rg` could '
                'search denied files')
    missing = sorted(ripgrep_exclusions(names) - lines)
    if missing:
        return f'The rg config at `{config_path}` is missing `{missing[0]}`'

    words = []
    for word in command.words[1:]:
        text = ripgrep_word_text(word, bases[0])
        if text is None:
            return (f'`rg` gets `{word.raw}`, which bash expands at run time. Put a regex in '
                    'single quotes, per `running-commands.md`')
        words.append(text)

    # Sort the words into options, glob values, and operands, refusing any option not listed.
    positive_globs, operands, has_pattern_option = [], [], False
    index, after_double_dash = 0, False
    while index < len(words):
        value = words[index]
        index += 1
        if after_double_dash or not value.startswith('-') or value == '-':
            operands.append(value)
            continue
        if value == '--':
            after_double_dash = True
            continue
        option_value = None
        if value.startswith('--'):
            name, has_value, attached = value.partition('=')
            if name in RIPGREP_FLAG_LONGS and not has_value:
                # `--files` takes no pattern, so every operand is a search root.
                has_pattern_option = has_pattern_option or name == '--files'
                continue
            if name not in RIPGREP_VALUE_LONGS:
                return f'`rg {name}` is not an option this hook knows to be read-only'
            if not has_value and index >= len(words):
                return f'`rg {name}` is missing its value'
            option_value = attached if has_value else words[index]
            index += 0 if has_value else 1
            letter = RIPGREP_LONG_LETTERS.get(name)
        else:
            letter = None
            for position, character in enumerate(value[1:], start=1):
                if character in RIPGREP_VALUE_LETTERS:
                    rest = value[position + 1:]
                    if not rest and index >= len(words):
                        return f'`rg -{character}` is missing its value'
                    option_value = rest or words[index]
                    index += 0 if rest else 1
                    letter = character
                    break
                if character not in RIPGREP_FLAG_LETTERS:
                    return f'`rg -{character}` is not an option this hook knows to be read-only'
        if letter in ('e', 'f'):
            has_pattern_option = True
        if letter == 'g' and not option_value.startswith('!'):
            parts = positive_glob_names(option_value)
            if parts is None:
                return (f'`rg` glob `{option_value}` has a wildcard in a folder name, an empty '
                        'part, or syntax this hook reads differently from rg')
            positive_globs.append((option_value, parts))

    # A search root goes through the same checks as the cwd, as written and through its links.
    paths = operands if has_pattern_option else operands[1:]
    roots = []
    for path in paths:
        reason = root_spelling_reason(path)
        if reason:
            return reason
        joined = [os.path.normpath(os.path.join(base, path)) for base in bases]
        # A root that is the parent of a two-part name, like `~/.config` or `/etc`, keeps that
        # name in every path rg walks, so `**/.config/gh` still matches. A link to the parent
        # under another name, like `cfg`, hides it. A root deeper inside the parent can't reach
        # the denied path at all, since rg doesn't follow links.
        for root in joined:
            real = fold(os.path.realpath(root)).rstrip('/')
            for parent in two_part_parents(globs, names):
                if real == parent and fold(os.path.basename(root)) != os.path.basename(parent):
                    return (f'`rg` searches `{path}`, a link to `{parent}`, where its config '
                            'cannot match a denied path')
        roots += [root for root in joined if os.path.isdir(root)]

    # A later glob overrides the config's exclusions, so `-g '*.yml'` brings back `secrets.yml`.
    # That only matters where such a file exists, so look before asking.
    if not positive_globs:
        return None
    file_names = sorted({name for _glob, parts in positive_globs for name in parts})
    where, found = denied_file_in(
        sorted(set(roots if paths else bases)), globs, names, deadline,
        file_names=file_names, for_ripgrep=True,
    )
    if found == '':
        return (f'`rg` glob `{positive_globs[0][0]}` could include a denied file, and the check '
                f'of `{where}` could not finish')
    if found:
        return (f'`rg` glob `{positive_globs[0][0]}` could include `{found}`, which '
                'settings.json denies the Read tool')
    return None


def shell_option_reason(command, command_line):
    """Why a shell option could make a glob match more than this hook resolves, or None.

    The hook resolves globs with bash's defaults. `shopt` or `bash -O` can turn on `dotglob`,
    `nocaseglob`, or `extglob`, so `cat ~/*` reaches `~/.npmrc`.
    """
    if command.name == 'shopt':
        return '`shopt` can change what a glob matches'
    if SHELL_OPTION.search(QUOTING.sub('', command_line)):
        return 'A shell option like `-O dotglob` can change what a glob matches'
    return None


def wrapper_text(command):
    """The source text of a command before the program it runs, like `env -C dir ` in front."""
    if not command.words or command.words[0].raw not in command.raw:
        return command.raw
    return command.raw.split(command.words[0].raw, 1)[0]


def wrapper_directory_reason(command):
    """Why a wrapper could run the program in a directory the line doesn't `cd` to, or None."""
    prefix = QUOTING.sub('', wrapper_text(command))
    for wrapper in command.wrappers:
        pattern = WRAPPER_DIRECTORY_OPTIONS.get(wrapper.split()[0])
        if pattern and pattern.search(prefix):
            return (f'`{wrapper}` runs `{command.name}` in another directory, so its relative '
                    'paths could name a denied file')
    return None


def file_list_reason(command):
    """Why a program could read files named inside another file, or None."""
    for word in command.words[1:]:
        if (word.value or word.raw).startswith(FILE_LIST_OPTIONS):
            return (f'`{command.name} {word.raw}` reads file names from a file this hook cannot '
                    'see')
    return None


def script_reason(command):
    """Why a `sed` or `awk` program could read a file the line never names, or None."""
    if command.name not in SCRIPT_FILE_OPTIONS and command.name not in AWK_PROGRAMS:
        return None
    words = command.words[1:]
    options = SCRIPT_FILE_OPTIONS.get(command.name, ())
    letters = {option[1] for option in options if not option.startswith('--')}
    for word in words:
        value = word.value
        if value is None:
            if bash_ast.could_become_option(word):
                return f'`{command.name}` gets `{word.raw}`, which could become an option'
            continue
        if value == '--':
            break
        if value.startswith('--') and value.split('=', 1)[0] in options:
            return f'`{command.name} {value}` runs a script from a file this hook cannot read'
        if value.startswith('-') and not value.startswith('--'):
            for letter in value[1:]:
                if letter in letters:
                    return (f'`{command.name} -{letter}` runs a script from a file this hook '
                            'cannot read')
                # `sed -i` takes an attached suffix and `-l` a length, so the rest isn't options.
                if letter in 'il':
                    break
    if command.name in AWK_PROGRAMS:
        for word in words:
            for token in AWK_RUN_TIME_READS:
                if token in word.raw:
                    return (f'The awk program uses `{token}`, which can build a file name at run '
                            'time and read it')
            if AWK_PIPE.search(word.raw) or '@include' in word.raw or '@load' in word.raw:
                return ('The awk program pipes into a command or loads another file, which this '
                        'hook cannot read')
    if command.name in JQ_PROGRAMS:
        for word in words:
            if JQ_MODULE.search(word.raw):
                return ('The jq program imports a module, which reads a file the line never '
                        'names')
    return None


def fd_arguments(own):
    """`fd`'s own words sorted into operands and options, the way `fd` reads them.

    Returns (operands, options), where each option is (name, value word or None). A short
    option's name is its letter, like `-e`, and in a bundle like `-He php` the first letter that
    takes a value gets the rest of the word or the next one.
    """
    operands, options, index, after_double_dash = [], [], 0, False
    while index < len(own):
        word = own[index]
        value = word.value or ''
        following = own[index + 1] if index + 1 < len(own) else None
        index += 1
        if after_double_dash or not value.startswith('-') or value == '-':
            operands.append(word)
            continue
        if value == '--':
            after_double_dash = True
            continue
        if value.startswith('--'):
            name, has_value, attached = value.partition('=')
            if has_value:
                options.append((name, bash_ast.Word(value=attached, raw=attached)))
            elif name in bash_ast.FD_VALUE_OPTIONS:
                options.append((name, following))
                index += 1
            else:
                options.append((name, None))
            continue
        for position, letter in enumerate(value[1:], start=1):
            if letter in bash_ast.FD_VALUE_LETTERS:
                # Like any short option's value, an attached one drops a leading `=`.
                rest = value[position + 1:]
                if rest:
                    stripped = rest.removeprefix('=')
                    options.append((f'-{letter}', bash_ast.Word(value=stripped, raw=rest)))
                else:
                    options.append((f'-{letter}', following))
                    index += 1
                break
            options.append((f'-{letter}', None))
    return operands, options


def fd_search_paths(operands, options, bases):
    """The directories an `fd` command searches, or the raw text of a path that expands.

    The first operand is the pattern and the rest are paths, plus any `--search-path`. With no
    path, `fd` searches its cwd, which `--base-directory` can move.
    """
    searched = operands[1:] + [word for name, word in options if name == '--search-path']
    roots = list(bases)
    for name, word in options:
        if name == '--base-directory':
            if word is None or word.value is None:
                return word.raw if word else name
            roots = [os.path.join(base, expand_tilde(word.value, bases[0])) for base in bases]
    if not searched:
        return sorted(set(roots))
    directories = set()
    for word in searched:
        if word is None or word.value is None:
            return word.raw if word else '--search-path'
        value = expand_tilde(word.value, bases[0])
        directories.update(os.path.normpath(os.path.join(root, value)) for root in roots)
    return sorted(directories)


def fd_extensions(options):
    """The extensions `fd`'s `-e` or `--extension` options limit it to, or [] for no limit.

    `fd` drops a leading `.` from each, so `-e .json` means `json`.
    """
    extensions = [word for name, word in options if name in ('-e', '--extension')]
    if any(word is None or not word.value for word in extensions):
        return []
    extensions = [word.value.lstrip('.') for word in extensions]
    return [] if any(not extension for extension in extensions) else extensions


def start_fd(arguments):
    """Start an `fd` walk in the background, or None when it can't start."""
    try:
        return subprocess.Popen(
            ['fd', '--hidden', '--no-ignore', '--absolute-path', *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
    except OSError:
        return None


def finish_fd(process, deadline):
    """The lines a started `fd` printed, or None when it failed or ran out of time."""
    if process is None:
        return None
    try:
        output, _errors = process.communicate(timeout=max(deadline - time.monotonic(), 0.01))
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return None
    return output.splitlines() if process.returncode == 0 else None


def denied_file_in(roots, globs, names, deadline, file_names=None, for_ripgrep=False):
    """The first root holding a denied path and that path, as (root, path).

    The path is '' when a root's search can't finish, and (None, None) means no root holds one.
    Every root's walks start at once, so the check costs the slowest walk's time rather than the
    sum of them. See `denied_path_among` for what counts.
    """
    # The filesystem ignores case, so `.NPMRC` is the same file as `.npmrc`.
    pattern = '**/{' + ','.join(sorted('/'.join(name) for name in names)) + '}'
    walks = []
    for root in roots:
        real_root = os.path.realpath(root)
        name_walk = start_fd(['--ignore-case', '--full-path', '--glob', pattern, real_root])
        link_walk = None if for_ripgrep else start_fd(
            ['--type', 'symlink', '--max-results', str(FD_LINK_LIMIT), '.', real_root],
        )
        walks.append((root, real_root, name_walk, link_walk))

    for root, real_root, name_walk, link_walk in walks:
        found = finish_fd(name_walk, deadline)
        links = finish_fd(link_walk, deadline) if link_walk else []
        if found is None or links is None or len(links) >= FD_LINK_LIMIT:
            return root, ''
        candidates = [
            literal for literal in (pattern.split('*')[0].rstrip('/') for pattern in globs)
            if literal.startswith('/') and (literal + '/').startswith(fold(real_root) + '/')
            and os.path.lexists(literal)
        ]
        path = denied_path_among(candidates, found + links, globs, file_names, for_ripgrep)
        if path:
            return root, path
    return None, None


def denied_path_among(candidates, found, globs, file_names, for_ripgrep):
    """The first denied path among a walk's results, or None.

    `file_names` limits it to denied paths whose own name matches one of those globs, like an
    rg glob or `fd -e php` that can only hand those over. For `fd`, a denied folder still counts
    whatever its name, because `fd` walks into it, and so does a link, which the program it runs
    follows. rg doesn't walk into a folder its config excludes or follow links, so
    `for_ripgrep` filters folders by name too and skips links.
    """
    for path in candidates + found:
        filtered = for_ripgrep or not os.path.isdir(os.path.realpath(path))
        if file_names is not None and filtered:
            own_name = fold(os.path.basename(path.rstrip('/')))
            if not any(fnmatch.fnmatchcase(own_name, each) for each in file_names):
                continue
        if path in candidates:
            return path
        for candidate in (path, os.path.realpath(path)):
            candidate += '/' if os.path.isdir(candidate) else ''
            if is_read_denied(candidate, globs):
                return path
    return None


def fd_reason(command, bases, globs, names, deadline):
    """Why `fd -x` or `-X` could hand a denied file to the program it runs, or None."""
    if command.name != 'fd' or command.opaque:
        return None
    parsed = bash_ast.parse_fd(command.words)
    if not parsed.execs:
        if command.nested:
            # `cat $(fd npmrc ~)` hands what `fd` finds to another program as its arguments.
            return '`fd` runs inside a substitution, so what it finds becomes another command\'s'
        return None
    # An attached program, like `--exec=cat`, is the option's only word.
    exec_words = {index for _action, first, start, end in parsed.execs if first is None
                  for index in range(start, end + 1)}
    own = [command.words[index] for index in sorted(parsed.own) if index not in exec_words]
    operands, options = fd_arguments(own)
    if any(name in ('-L', '--follow') for name, _value in options):
        return '`fd --follow` follows links, which could lead to denied files'
    roots = fd_search_paths(operands, options, bases)
    if not isinstance(roots, list):
        return f'`fd` searches `{roots}`, which expands at run time'
    # `-e php` can only hand over files ending in `.php`, so other denied files don't matter.
    extensions = fd_extensions(options)
    file_names = [f'*.{fold(extension)}' for extension in extensions] or None
    root, found = denied_file_in(roots, globs, names, deadline, file_names=file_names)
    if found == '':
        return f'`fd` could not finish checking `{root}` for files settings.json denies'
    if found:
        return (f'`fd` runs a program on what it finds under `{root}`, which holds '
                f'`{found}`, a path settings.json denies the Read tool')
    return None


def decide(command_line, cwd):
    try:
        parsed = bash_ast.parse(command_line)
        tree = bash_ast.syntax_tree(command_line)
    except bash_ast.ParseError as error:
        return 'ask', f'{error}, so this hook cannot check it for paths the Read tool is denied'

    globs = read_deny_patterns(cwd)
    if globs is None:
        return 'ask', ("The user's settings.json couldn't be read, so this hook cannot tell which "
                       'paths the Read tool is denied; confirm it')
    if not globs:
        return None
    names = denied_names(globs)

    if RIPGREP_CONFIG_VARIABLE in command_line:
        return 'ask', f'The line mentions {RIPGREP_CONFIG_VARIABLE}; confirm it'

    bases, expanding_directories = directory_bases(parsed, cwd)

    words = list(tree_words(tree, bash_ast.LineParser(command_line)))
    for command in parsed.commands:
        words += list(command_words(command))
    seen = set()
    for word in words:
        if word is None or (word.raw, word.value) in seen:
            continue
        seen.add((word.raw, word.value))
        reason = word_reason(word, bases, globs, names, expanding_directories)
        if reason:
            return 'ask', f'{reason}; confirm it'

    for variable, effect in LINE_CHANGING_VARIABLES.items():
        if variable in command_line:
            return 'ask', f'`{variable}` {effect}; confirm it'

    runs_ripgrep = any(command.name == 'rg' for command in parsed.commands)
    # One budget for every directory walk on the line, so the hook answers before Claude Code
    # gives up on it, which would leave the command to the allow rules.
    deadline = time.monotonic() + FD_SEARCH_BUDGET
    for command in parsed.commands:
        feeding = FILE_NAME_FEEDING_WRAPPERS.intersection(command.wrappers)
        if feeding:
            return 'ask', (f'`{sorted(feeding)[0]}` hands `{command.name}` file names this hook '
                           'never sees; confirm it')
        if runs_ripgrep and command.name in ENVIRONMENT_CHANGING_BUILTINS:
            return 'ask', (f'`{command.name}` could change the environment `rg` runs with on '
                           'the same line; confirm it')
        reason = (
            shell_option_reason(command, command_line) or wrapper_directory_reason(command)
            or file_list_reason(command)
            or ripgrep_reason(command, bases, globs, names, expanding_directories, deadline)
            or script_reason(command) or fd_reason(command, bases, globs, names, deadline)
        )
        if reason:
            return 'ask', f'{reason}; confirm it'
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    command_line = data.get('tool_input', {}).get('command', '')
    if not command_line:
        return
    cwd = data.get('cwd') or os.getcwd()
    verdict = decide(command_line, cwd)
    if verdict:
        emit(*verdict)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        emit('ask', f'read-deny-permissions crashed, so it cannot check this command: {error!r}')
