#!/usr/bin/env python3
"""
Refuses command shapes that slip past the prefix-matched rules in `settings.json`. Those rules
match from the start of the line, so a destructive git command wearing a `-C <path>`, an env
assignment, a wrapper like `env` or `sh -c`, or a quoted program name matches nothing. This hook
reads the line with `bash_ast` instead, so it sees every command the line runs, wherever it sits.

It decides six things, and the strongest verdict wins (deny, then ask, then silence):

  - A line that chains more than one command is denied, because splitting it into one tool call
    per command is a fix the caller can always make, and it's what lets every other hook and rule
    judge each command on its own. Piping into a shell gets its own message, since that runs a
    script nobody has read. A trailing `| head`, `| tail`, or `| wc` doesn't count as a chain.
  - A command whose program can't be read from the line (`$EDITOR`, `bash -c "$x"`, a bare
    `bash` reading stdin) is asked about, because no hook can vouch for it.
  - A git command retargeted at another repository with `GIT_DIR`, `--git-dir`, and the like is
    denied in favor of `git -C <path>`. Global options that run programs or rewrite config (`-c`,
    `--exec-path`) are asked about.
  - A destructive git subcommand, mirroring the `Bash(git ...)` entries in `permissions.deny`, is
    denied wherever it appears.
  - A program that `find -exec`, `-execdir`, `-ok`, or `-okdir` runs is asked about unless it only
    reads, because `settings.json` allows `Bash(find *)` and a prefix can't see what `-exec` runs.
    `rm` and `mv` there are denied, as is `-delete` however it's quoted, and `find`'s own
    `-fprint`-style writes are asked about.
  - Everything else is left to `settings.json` and the other hooks.

Runs unfiltered on every Bash call, because a chain or a nested git command can begin with any
program. Read-only and recoverable git forms pass through silently: `file-command-permissions.py`
owns `git add`, `git commit`, `git push`, and branch deletion, and decides those with checks a
prefix can't express.

The `Bash(git ...)` deny rules stay in `settings.json` even though this hook covers them, because
a settings `deny` is the one layer that keeps working if this hook is ever disabled.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import bash_ast
except ImportError as _import_error:
    # A traceback would exit non-zero, which Claude Code reads as "no opinion", letting every
    # line through unexamined. Prompting instead fails closed.
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'ask',
            'permissionDecisionReason': (
                f'bash_ast failed to load, so dangerous-command-shapes cannot vouch for the '
                f'command: {_import_error}'
            ),
        }
    }))
    sys.exit(0)

ASK = 'ask'
DENY = 'deny'

# A destructive form `settings.json` puts in `permissions.ask` rather than `deny`, so it gets a
# prompt here instead of a refusal. Kept apart from ASK because ASK also means "an argument is only
# known at run time", which needs a different message.
PROMPT = 'prompt'

PROMPTED_FORMS = frozenset({'git stash drop', 'git stash clear', 'git restore <path>'})

# Environment variables that point git at a different repository, work tree, or index than the
# one `-C` names, so the command acts somewhere the reader of the line doesn't expect.
GIT_RETARGETING_ENV = frozenset({'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_EXEC_PATH'})

# `GIT_CONFIG`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n`, and friends inject
# config, which can name programs for git to run.
GIT_CONFIG_ENV_PREFIX = 'GIT_CONFIG'

# Global options that retarget git the same way the variables above do.
GIT_RETARGETING_OPTIONS = frozenset({'--git-dir', '--work-tree'})

# Global options that can make git run a program of the caller's choosing. `file-command-
# permissions.py` already prompts on these, so this hook asks rather than refusing outright.
GIT_PROGRAM_OPTIONS = frozenset({'-c', '--exec-path', '--config-env'})

# Global options that take a value as the next word when it isn't attached with `=`.
GIT_GLOBAL_VALUE_OPTIONS = frozenset({
    '-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env', '--super-prefix',
    '--attr-source',
})

# Subcommands whose arguments decide whether they're destructive. A word among those arguments
# that expands at run time could be the flag that makes it so.
FLAG_SENSITIVE_SUBCOMMANDS = frozenset({
    'push', 'reset', 'checkout', 'restore', 'config', 'tag', 'submodule', 'stash',
})

# Subcommands denied whatever their arguments.
ALWAYS_DESTRUCTIVE_SUBCOMMANDS = frozenset({'clean', 'cherry-pick', 'update-ref'})

# Options that take a separate value, per subcommand, so the value isn't mistaken for a flag
# cluster or a positional. A short option listed here also ends a cluster, since everything after
# it is its value: `-bfix` is `-b fix`, not `-f`.
SUBCOMMAND_VALUE_OPTIONS = {
    'push': frozenset({'-o', '--push-option', '--receive-pack', '--exec', '--repo'}),
    'checkout': frozenset({'-b', '-B', '--orphan', '--conflict', '--pathspec-from-file'}),
    'restore': frozenset({'-s', '--source', '--conflict', '--pathspec-from-file'}),
    'tag': frozenset({'-u', '--local-user', '-m', '--message', '-F', '--file', '--cleanup',
                      '--sort', '--format', '--contains', '--no-contains', '--merged',
                      '--no-merged', '--points-at', '--color', '--column'}),
    'reset': frozenset({'--pathspec-from-file'}),
}

# `--prune` isn't in `permissions.deny`, but it deletes remote branches the same way `--delete`
# does, just without naming them.
PUSH_DESTRUCTIVE_LONG = frozenset({
    '--force', '--force-with-lease', '--mirror', '--delete', '--prune',
})

# Actions that make `git config` read rather than write. Old-style flags and the `get`/`list`
# subcommands git added in 2.46.
GIT_CONFIG_READ_FLAGS = frozenset({
    '--get', '--get-all', '--get-regexp', '--get-urlmatch', '--get-color', '--get-colorbool',
    '--list', '-l',
})
GIT_CONFIG_READ_ACTIONS = frozenset({'get', 'list'})
GIT_CONFIG_WRITE_FLAGS = frozenset({
    '--add', '--unset', '--unset-all', '--replace-all', '--rename-section', '--remove-section',
    '--edit', '-e',
})

# Every long option a destructive form is recognized by. Git accepts any unambiguous prefix of a
# long option, so `--har` is `--hard`; an argument that's a prefix of one of these counts as it.
# Options that make a command safer, like `--staged`, are deliberately absent, so an abbreviation
# of one can only make the verdict stricter.
DESTRUCTIVE_LONG_OPTIONS = PUSH_DESTRUCTIVE_LONG | GIT_CONFIG_WRITE_FLAGS | frozenset({
    '--hard', '--pathspec-from-file', '--worktree',
})


# Programs `find -exec` may run without a prompt, because they only read the files `find` hands
# them. Keep this an allowlist: anything else `-exec` runs could write, delete, or run a program.
FIND_EXEC_READERS = frozenset({
    'cat', 'grep', 'head', 'ls', 'md5', 'rg', 'shasum', 'stat', 'tail', 'wc',
})

# Options that make a reader above run a program of the caller's choosing, or never exit.
FIND_EXEC_READER_RUNNING_OPTIONS = {
    'rg': ('--pre', '--hostname-bin'),
    'tail': ('--follow', '--retry'),
}

# Short option letters with the same effect, counted anywhere in a cluster like `-fn`.
FIND_EXEC_READER_RUNNING_LETTERS = {
    'tail': frozenset({'f', 'F'}),
}

# Programs refused under any `find` action, mirroring the `Bash(find * -exec rm*)` and
# `Bash(find * -exec mv*)` deny rules, which can't see `-execdir`, `-ok`, or a wrapper.
FIND_EXEC_DENIED = frozenset({'rm', 'mv'})

# `find`'s own actions that create or truncate the file they name.
FIND_WRITING_ACTIONS = frozenset({'-fprint', '-fprint0', '-fprintf', '-fls'})


def expand_abbreviations(long_options):
    """Add the destructive option each abbreviated `--name` could stand for."""
    expanded = set(long_options)
    for name in long_options:
        if len(name) > 2:
            expanded.update(
                option for option in DESTRUCTIVE_LONG_OPTIONS
                if option.startswith('--') and option.startswith(name)
            )
    return expanded


CHAIN_MESSAGE = (
    'This line chains more than one command ({chain}). Send each command as its own tool call, '
    'per `running-commands.md`, so each one is judged on its own. A trailing `| head`, '
    '`| tail`, or `| wc` is fine, and so is a redirect to `/dev/null` or a file descriptor '
    '(`2>&1`).'
)

PIPE_TO_SHELL_MESSAGE = (
    'Never pipe output directly into bash, sh, zsh, or eval. Save the output to a temp file, '
    'review it, then execute it explicitly.'
)

RETARGET_MESSAGE = (
    'Never use `{what}` to point git at another repository. Use `git -C <path> <command>` '
    'instead.'
)

DESTRUCTIVE_MESSAGE = (
    '`{what}` is denied by `permissions.deny`, and reaching it through `-C`, a wrapper, or a '
    'nested command doesn\'t exempt it. If the task genuinely needs it, stop and say so rather '
    'than rewording the command.'
)


def output(decision, reason):
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': decision,
            'permissionDecisionReason': reason,
        }
    }))


def readable(word):
    """True when the program receives exactly this word's text. A leading `~` only swaps in a
    home directory, so it can't turn the word into a flag."""
    return word.value is not None and not (word.glob or word.brace)


def split_arguments(words, value_options):
    """Sort a subcommand's arguments into long options, short letters, and positionals.

    Returns (long_options, letters, positionals, saw_double_dash, unknown). A word that expands at
    run time could be any of the three, so it sets `unknown` and holds a None in `positionals`.
    """
    long_options = set()
    letters = set()
    positionals = []
    saw_double_dash = False
    unknown = False
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        if not readable(word):
            unknown = True
            positionals.append(None)
            continue
        value = word.value
        if saw_double_dash:
            positionals.append(value)
            continue
        if value == '--':
            saw_double_dash = True
            continue
        if value.startswith('--'):
            name = value.split('=', 1)[0]
            long_options.add(name)
            if name in value_options and '=' not in value:
                index += 1
            continue
        if value.startswith('-') and value != '-':
            for position, letter in enumerate(value[1:], start=1):
                letters.add(letter)
                if f'-{letter}' in value_options:
                    # Everything after a value-taking letter is its value: `-bfix` is `-b fix`.
                    if position == len(value) - 1:
                        index += 1
                    break
            continue
        positionals.append(value)
    return long_options, letters, positionals, saw_double_dash, unknown


def split_git_globals(words):
    """Walk git's global options, returning (options seen, subcommand index or None)."""
    seen = []
    index = 1
    while index < len(words):
        word = words[index]
        if word.value is None or word.glob or word.brace:
            return seen, index
        value = word.value
        if not value.startswith('-'):
            return seen, index
        name = value.split('=', 1)[0]
        seen.append(name)
        if name in GIT_GLOBAL_VALUE_OPTIONS and '=' not in value:
            index += 2
            continue
        index += 1
    return seen, None


def destructive_git(subcommand, words):
    """Decide one git subcommand. Returns (DENY or ASK, description) or None."""
    if subcommand in ALWAYS_DESTRUCTIVE_SUBCOMMANDS or subcommand.startswith('filter-'):
        return DENY, f'git {subcommand}'
    if subcommand not in FLAG_SENSITIVE_SUBCOMMANDS:
        return None

    long_options, letters, positionals, saw_double_dash, unknown = split_arguments(
        words, SUBCOMMAND_VALUE_OPTIONS.get(subcommand, frozenset())
    )
    long_options = expand_abbreviations(long_options)
    denied = destructive_form(subcommand, long_options, letters, positionals, saw_double_dash)
    if denied in PROMPTED_FORMS:
        return PROMPT, denied
    if denied:
        return DENY, denied
    if unknown:
        return ASK, f'git {subcommand}'
    return None


def destructive_form(subcommand, long_options, letters, positionals, saw_double_dash):
    """Name the destructive form of a flag-sensitive subcommand, or return None."""
    if subcommand == 'push':
        forced = long_options & PUSH_DESTRUCTIVE_LONG
        if forced:
            return 'git push ' + sorted(forced)[0]
        if letters & {'f', 'd'}:
            return 'git push -' + sorted(letters & {'f', 'd'})[0]
        # A `+` refspec force-updates its destination, and an empty source (`:branch`) deletes it.
        # A bare `:` is git's matching-branches refspec, which deletes nothing.
        for refspec in positionals:
            if refspec is not None and (refspec.startswith('+') or (
                refspec.startswith(':') and refspec != ':'
            )):
                return f'git push {refspec}'
        return None

    if subcommand == 'reset':
        return 'git reset --hard' if '--hard' in long_options else None

    if subcommand == 'checkout':
        if '--force' in long_options or 'f' in letters:
            return 'git checkout -f'
        if saw_double_dash or '--pathspec-from-file' in long_options:
            return 'git checkout -- <path>'
        # A branch name can't begin with `.`, so an operand that does is a pathspec.
        if any(path is not None and path.startswith('.') for path in positionals):
            return 'git checkout .'
        return None

    if subcommand == 'restore':
        # Without `--staged`, restore writes the work tree, which discards uncommitted changes.
        staged = '--staged' in long_options or 'S' in letters
        worktree = '--worktree' in long_options or 'W' in letters
        if worktree:
            return 'git restore --worktree'
        if staged:
            # `--staged` alone only touches the index, which the work tree still holds a copy of.
            return None
        if any(path is not None and path.startswith('.') for path in positionals):
            return 'git restore --worktree'
        return 'git restore <path>'

    if subcommand == 'config':
        flags = long_options | {f'-{letter}' for letter in letters}
        writes = flags & GIT_CONFIG_WRITE_FLAGS
        if writes:
            return 'git config ' + sorted(writes)[0]
        if flags & GIT_CONFIG_READ_FLAGS:
            return None
        if positionals and positionals[0] in GIT_CONFIG_READ_ACTIONS:
            return None
        # An unreadable first word might be `get`, so let the caller ask instead of refusing.
        if positionals and positionals[0] is None:
            return None
        return 'git config'

    if subcommand == 'tag':
        return 'git tag -d' if '--delete' in long_options or 'd' in letters else None

    if subcommand == 'submodule':
        return 'git submodule deinit' if positionals[:1] == ['deinit'] else None

    if subcommand == 'stash':
        if positionals[:1] in (['drop'], ['clear']):
            return f'git stash {positionals[0]}'
        return None

    return None


def judge_git(command):
    """Collect verdicts for one git command. Returns a list of (decision, reason)."""
    verdicts = []
    for name, _value in command.assigns:
        if name in GIT_RETARGETING_ENV or name.startswith(GIT_CONFIG_ENV_PREFIX):
            verdicts.append((DENY, RETARGET_MESSAGE.format(what=name)))

    globals_seen, subcommand_index = split_git_globals(command.words)
    for option in globals_seen:
        if option in GIT_RETARGETING_OPTIONS:
            verdicts.append((DENY, RETARGET_MESSAGE.format(what=f'git {option}')))
        elif option in GIT_PROGRAM_OPTIONS:
            verdicts.append((ASK, (
                f'`git {option}` can make git run a program or rewrite its config, so this '
                f'command needs a person to look at it.'
            )))

    if subcommand_index is None:
        if command.dynamic_args:
            verdicts.append((ASK, (
                '`git` gets its subcommand from `xargs` or `find -exec` at run time, so this hook '
                'cannot tell whether it\'s destructive.'
            )))
        return verdicts

    subcommand_word = command.words[subcommand_index]
    if subcommand_word.value is None or subcommand_word.glob or subcommand_word.brace:
        verdicts.append((ASK, (
            'The git subcommand expands at run time, so this hook cannot tell whether it\'s '
            'destructive.'
        )))
        return verdicts

    subcommand = subcommand_word.value
    verdict = destructive_git(subcommand, command.words[subcommand_index + 1:])
    if verdict is None and command.dynamic_args and subcommand in FLAG_SENSITIVE_SUBCOMMANDS:
        verdict = (ASK, f'git {subcommand}')
    if verdict is None:
        return verdicts

    decision, what = verdict
    if decision == DENY:
        verdicts.append((DENY, DESTRUCTIVE_MESSAGE.format(what=what)))
    elif decision == PROMPT:
        verdicts.append((ASK, (
            f'`{what}` discards work that can\'t be recovered, so a person needs to confirm it.'
        )))
    else:
        verdicts.append((ASK, (
            f'An argument to `{what}` is only known at run time, and it could be the one that '
            f'makes the command destructive.'
        )))
    return verdicts


def reader_runs_something(program, words):
    """True when a reader's arguments make it run a program or never exit, like `tail -f`."""
    running_options = FIND_EXEC_READER_RUNNING_OPTIONS.get(program, ())
    running_letters = FIND_EXEC_READER_RUNNING_LETTERS.get(program, frozenset())
    for word in words:
        value = word.value
        if value == '--':
            return False
        if value.startswith('--'):
            if value.split('=', 1)[0] in running_options:
                return True
        elif value.startswith('-') and running_letters & set(value[1:]):
            return True
    return False


def judge_find_action(command):
    """Judge a program a `find -exec`-style action runs. Returns (decision, reason) or None.

    Only a reader that `find` runs directly by its bare name, with literal arguments and no
    environment assignments, passes. `PATH=` could swap in another `grep`, and a variable could
    hold `rg --pre`.
    """
    find_wrappers = [
        index for index, wrapper in enumerate(command.wrappers) if wrapper.startswith('find -')
    ]
    if not find_wrappers or command.opaque:
        return None
    action = command.wrappers[find_wrappers[-1]]
    program = command.words[0].value if command.words else None
    if command.name in FIND_EXEC_DENIED:
        return DENY, (
            f'`find {action.split()[-1]} {command.name}` is denied, the same as `find -exec '
            f'{command.name}` in `permissions.deny`. If the task genuinely needs it, stop and say '
            f'so rather than rewording the command.'
        )
    # BSD `find -execdir` hands over a bare filename, so a file named `--pre=sh` becomes an rg
    # option. A `--` before the `{}` makes the reader treat it as a path.
    filename_is_option_safe = action in ('find -exec', 'find -ok') or any(
        word.value == '--' for word in command.words[1:next(
            (index for index, word in enumerate(command.words) if '{}' in (word.value or '')),
            len(command.words),
        )]
    )
    reads_only = (
        filename_is_option_safe
        and program in FIND_EXEC_READERS
        and command.name == program
        and len(command.wrappers) == find_wrappers[-1] + 1
        and not command.assigns
        and all(word.literal for word in command.words)
        and not reader_runs_something(program, command.words[1:])
    )
    if reads_only:
        return None
    return ASK, (
        f'`{action}` runs `{program or "a program"}` on every file it finds, and only '
        f'read-only programs like `grep` and `wc`, with literal arguments, pass without a prompt.'
    )


def find_writing_action(command):
    """Judge `find`'s own writes: `-delete`, and `-fprint` and the like. Returns (decision, reason).

    Words are compared after bash resolves their quoting, so `-dele''te` counts. The
    `Bash(find * -delete*)` deny rule only sees the raw line, and misses `find -delete`, which
    deletes everything under the working directory.
    """
    if command.name != 'find' or command.opaque:
        return None
    if any(word.value == '-delete' for word in command.words[1:]):
        return DENY, (
            '`find -delete` is denied by `permissions.deny`, however it\'s spelled. If the '
            'task genuinely needs it, stop and say so rather than rewording the command.'
        )

    writing_action = None
    expands = command.dynamic_args
    inside_exec = False
    for word in command.words[1:]:
        if inside_exec:
            # `judge_find_action` already judges the words an `-exec` action runs.
            inside_exec = not (word.literal and word.value in (';', '+'))
            continue
        if word.literal and word.value in bash_ast.FIND_EXEC_ACTIONS:
            inside_exec = True
        elif not readable(word):
            expands = True
        elif word.value in FIND_WRITING_ACTIONS and writing_action is None:
            writing_action = word.value

    if writing_action:
        return ASK, f'`find {writing_action}` creates or truncates the file it names.'
    if expands:
        return ASK, (
            'A `find` argument is only known at run time, and it could become `-exec`, '
            '`-delete`, or another action this hook can only judge when it can read it.'
        )
    return None


def pipes_into_shell(command):
    """True for a shell or `eval` reading a script it was handed on stdin."""
    if command.opaque is None or command.name is None:
        return False
    if command.name in bash_ast.SHELLS:
        # A shell bash_ast can't read for any reason -- stdin, or a grammar it doesn't parse --
        # is running whatever the pipe feeds it.
        return True
    return command.name == 'eval' and len(command.words) == 1


def decide(line):
    """Return (decision, reason) for one Bash line, or None to stay silent."""
    try:
        parsed = bash_ast.parse(line)
    except bash_ast.ParseError as error:
        return ASK, str(error)

    denials = []
    asks = []

    for command in parsed.commands:
        if command.opaque:
            asks.append(command.opaque)
        find_action = judge_find_action(command)
        if find_action:
            (denials if find_action[0] == DENY else asks).append(find_action[1])
        find_write = find_writing_action(command)
        if find_write:
            (denials if find_write[0] == DENY else asks).append(find_write[1])
        is_git = command.name == 'git'
        # A bare assignment can't run anything this call, but there's no honest reason to write
        # one for a git variable either, and it's what the old hook refused.
        if not command.words:
            is_git = any(
                name in GIT_RETARGETING_ENV or name.startswith(GIT_CONFIG_ENV_PREFIX)
                for name, _value in command.assigns
            )
        if is_git:
            for decision, reason in judge_git(command):
                (denials if decision == DENY else asks).append(reason)

    if parsed.chain:
        piped = '`|' in parsed.chain
        if piped and any(pipes_into_shell(command) for command in parsed.commands):
            denials.append(PIPE_TO_SHELL_MESSAGE)
        else:
            denials.append(CHAIN_MESSAGE.format(chain=parsed.chain))

    if denials:
        return DENY, ' '.join(dict.fromkeys(denials))
    if asks:
        return ASK, ' '.join(dict.fromkeys(asks))
    return None


def main():
    try:
        data = json.loads(sys.stdin.read())
    except ValueError:
        return
    tool_input = data.get('tool_input') if isinstance(data, dict) else None
    command = tool_input.get('command') if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return
    verdict = decide(command)
    if verdict is not None:
        output(*verdict)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # A traceback exits non-zero, which Claude Code reads as "no opinion"; prompting fails
        # closed instead.
        output(ASK, (
            f'dangerous-command-shapes crashed, so it cannot vouch for this command: {error!r}'
        ))
