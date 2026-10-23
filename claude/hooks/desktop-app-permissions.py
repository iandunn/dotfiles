#!/usr/bin/env python3
"""
Permission gate for macOS application bundles, covering Bash commands that write into one and
Bash commands that launch one (PreToolUse hook).

Writing into an application directory is denied outright. Nothing an agent legitimately does
puts a file into /Applications, and unlike a launch, the destination is provable from the
command string: a redirect target, an `rm` operand, the last argument of a `cp`. Proving where
a byte lands needs no guess about intent, so the answer can be no without asking. `write_targets`
is what makes that precise -- a command reaches the deny only when its own syntax names an
application path as something it modifies, whether that is a redirect, an operand of a command
from WRITE_ARGUMENT_COMMANDS, the destination of one from WRITE_DESTINATION_COMMANDS, or a
reader turned writer by one of the flags in CONDITIONAL_WRITE_MARKERS.

Launching never gets more than "ask", and never "allow". Whether starting a GUI application is
wanted is not a thing the command string can settle, unlike the path-containment check in
file-command-permissions.py, so there is no shape that earns a silent approval. An
auto-allow for "correctly flagged" invocations would only teach the model to reword a command
until the matcher is satisfied, which is the opposite of a gate. The decision stays with the
human every time; CLAUDE.md carries the rules about which browser to prefer and which
isolation flags to pass, because prose is read by the party that can actually judge intent.

The launch check is deliberately narrow at the edges to keep this quiet enough to live on every
Bash call. It fires on:

  1. A path through `<bundle>.app/Contents/MacOS/` anywhere in a command that is not a pure
     reader (see READ_ONLY_COMMANDS, and READ_ONLY_DISQUALIFIERS for the flags that cancel it). A
     bundle's executable directory is somewhere you exec from, but it is also somewhere you read
     from -- `grep` over a binary for a string constant, `codesign -dv` for a signature -- and the
     reader list is what tells those apart.
     It is a whitelist rather than a blacklist because plenty of tools merely accept a path and
     can still get it run: `find -exec`, `xargs`, `awk`'s `system()`, and `echo path | sh`.
  2. A command name that is any path inside an applications directory or a `.app`
     bundle (see APPLICATION_DIRS), bare binaries included, with no exception for depth.
     APPLICATION_PATH_EXCLUSIONS names the individual binaries that may run anyway.
  3. A command name that is a known GUI launcher -- the curated LAUNCHER_COMMANDS
     list, plus every `*.app` bundle name discovered in APPLICATION_DIRS at runtime, so newly
     installed applications are covered without editing this file. A discovered name only counts
     when it resolves through PATH to a binary inside an applications directory, which keeps a
     coincidental collision quiet -- `Claude.app` is installed, but `claude` is the CLI in
     ~/.local/bin, and `local` is a shell builtin that resolves nowhere at all.
  4. `open` as the command, in every form. On macOS `open` exists to hand something to an
     application: `open -a Slack`, `open -b com.apple.Safari`, `open -e notes.txt`, and bare
     `open index.html`, which silently uses whatever owns the file type.
  5. `osascript` / `osacompile` whose arguments or heredoc contain `tell application` or
     `activate`.
  6. `launchctl` subcommands that start something rather than query it.
  7. Browser-automation drivers (see AUTOMATION_TOOLS), whether invoked directly or through a
     package runner such as `npx`.
  8. Any command bash_ast marks opaque, because what runs is decided at run time (`$BROWSER`,
     `bash -c "$script"`, a shell reading stdin), and a line bash_ast cannot parse at all. Either
     one could be a launch this hook has no way to rule out.

Commands come from bash_ast, which reports every simple command the line can run -- inside
`if`, loops, subshells, `$(...)`, backticks, unquoted heredocs, and literal `bash -c` / `eval`
strings -- with wrappers like `sudo` / `env` / `nohup` / `command` / `exec` already peeled off and
quoting resolved. Matching only the command name is what keeps ordinary work quiet: `grep -i
firefox log.txt` and `git commit -m "fix Safari bug"` mention an application without launching
one, and `ls -d /Applications/Firefox*.app` reads a bundle without executing it.

LIMITATIONS -- this hook sees a command string, so it cannot see through indirection:

  - A script hides everything. `bash ./run.sh`, `npm run test:e2e`, `make screenshots`, or a
    Python file calling subprocess all launch applications invisibly from here. This is the
    largest hole and it is not closable at this layer.
  - Only Bash is gated. An MCP server that drives or launches a browser itself never reaches
    this hook and needs its own gate, the way chrome-mcp-permissions.py gates Chrome DevTools.
  - A shell function or alias defined outside the line runs under a name that looks ordinary.
    A variable in command position is caught only because bash_ast marks it opaque, which asks.
  - A throwaway profile does not make a launch side-effect-free. Firefox's updater will try to
    apply a staged update to the installed bundle in /Applications, and its crash reporter will
    surface dialogs, both of which live outside the profile entirely.
  - The write deny reads argument syntax, so an installer writes freely: `brew install --cask`,
    a `.pkg`, and an application's own updater all put files in /Applications without ever
    naming the path in a command this hook can see.

Fails open on an unexpected input or internal error, which exits silently so that a bug here can
never block every Bash command in a session. A line bash_ast can't parse, or bash_ast failing to
import, asks instead, because that line might hide a launch.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import bash_ast
except ImportError:
    bash_ast = None

APPLICATION_DIRS = (
    '/Applications',
    '/Applications/Utilities',
    '/System/Applications',
    '/System/Applications/Utilities',
    '~/Applications',
)

# Bare command names that start a GUI application. Discovered bundle names are added to this at
# runtime, but a bundle name rarely matches its own CLI entry point ("Visual Studio Code.app"
# is invoked as `code`), so the common ones are spelled out.
LAUNCHER_COMMANDS = {
    # Browsers
    'firefox', 'firefox-bin', 'safari', 'chromium', 'google-chrome', 'msedge',
    'microsoft-edge', 'brave', 'opera', 'orion',
    # Communication
    'slack', 'teams', 'msteams', 'zoom', 'discord', 'signal',
    # Editors and terminals
    'iterm', 'iterm2', 'code', 'code-insiders', 'codium', 'cursor', 'windsurf', 'zed',
    'subl', 'sublime_text', 'mate', 'idea', 'pycharm', 'phpstorm', 'webstorm', 'rubymine',
    # Networking and VPN
    'openvpn', 'openvpn-connect', 'tunnelblick', 'viscosity', 'wireguard',
}

# Headless-capable drivers still start a real browser process.
AUTOMATION_TOOLS = {
    'playwright', 'puppeteer', 'selenium', 'webdriver', 'webdriverio', 'cypress',
    'geckodriver', 'chromedriver', 'safaridriver', 'chrome-headless-shell',
}

PACKAGE_RUNNERS = {'npx', 'bunx', 'pnpx', 'dlx', 'uvx', 'pipx'}

# Absolute paths inside an applications directory that are allowed to run without asking.
# Everything else under those directories asks, bare binaries included. Bundles do ship ordinary
# command line tools, and Local keeps its copy of WP-CLI inside its bundle, so that one binary is
# exempt. Add a path here only when the binary is a CLI that starts no application.
APPLICATION_PATH_EXCLUSIONS = {
    '/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/posix/wp',
}

# Commands that treat a path argument as something to read, never as something to run. A path
# inside a bundle's executable directory stays quiet when it is an argument to one of these.
# Keep this a whitelist: `find`, `xargs`, `awk`, `sed`, and `echo` all accept a path and have a
# route to executing it, so they keep asking.
READ_ONLY_COMMANDS = {
    'grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack', 'cat', 'head', 'tail', 'strings', 'file', 'otool',
    'nm', 'lipo', 'codesign', 'plutil', 'defaults', 'stat', 'wc',
    'xxd', 'hexdump', 'od', 'ls', 'du', 'md5', 'shasum', 'sha256sum', 'cmp', 'diff',
}

# Flags that let a reader run a program, which cancels its place in READ_ONLY_COMMANDS. Pagers
# like `less`, `more`, and `bat` are left out of that list entirely, because LESSOPEN and their
# own commands can run programs with no flag on the line.
READ_ONLY_DISQUALIFIERS = {
    'rg': ('--pre',),
}

# Commands that modify every path handed to them, so any application path among the arguments is
# a destination. `mv` belongs here rather than with the destination-only commands because moving
# a bundle out of /Applications changes /Applications just as much as moving one in.
WRITE_ARGUMENT_COMMANDS = {
    'rm', 'rmdir', 'unlink', 'shred', 'touch', 'mkdir', 'tee', 'truncate', 'chmod', 'chown',
    'chgrp', 'chflags', 'xattr', 'mv', 'install_name_tool', 'strip',
}

# Commands that read every path but the last one, which is where the bytes land.
WRITE_DESTINATION_COMMANDS = {'cp', 'ln', 'ditto', 'install', 'rsync', 'scp'}

# Destinations that arrive as the value of a flag instead of as the last argument.
WRITE_FLAG_DESTINATIONS = {
    'unzip': ('-d',),
    'tar': ('-C', '--directory'),
    'ditto': ('--extract', '-x'),
}

# Readers that turn into writers under the right flag or subcommand. Without this the reader
# whitelist above would vouch for `plutil -replace` and `defaults write`, which is the one hole
# a whitelist of tool names opens on its own.
CONDITIONAL_WRITE_MARKERS = {
    'plutil': ('-replace', '-insert', '-remove', '-convert'),
    'codesign': ('-s', '--sign', '-f', '--force', '--remove-signature'),
    'defaults': ('write', 'delete', 'import', 'rename'),
    'find': ('-delete',),
}

# Editors that rewrite the file they are given rather than printing to stdout.
IN_PLACE_EDITORS = {'sed', 'gsed', 'perl', 'ruby', 'awk'}

LAUNCHCTL_START_SUBCOMMANDS = {'load', 'start', 'kickstart', 'bootstrap', 'asuser', 'submit'}

BUNDLE_EXECUTABLE_PATH = re.compile(r'\.app/Contents/MacOS/', re.IGNORECASE)
IN_PLACE_FLAG = re.compile(r'^-[A-Za-z]*i')

# Output redirects that write to the file they name. `>&` counts when its target isn't a
# descriptor, because `>&file` is bash's spelling of `&>file`.
WRITING_REDIRECT_OPS = {'>', '>>', '>|', '&>', '&>>', '<>', '>&'}

# Browser flags that keep a launch away from the profile and the instance already running.
FIREFOX_ISOLATION_FLAGS = ('--profile', '--no-remote', '--new-instance')


def application_dir_prefixes():
    """Absolute applications directories, each with a trailing separator."""
    return tuple(os.path.expanduser(d).rstrip('/') + '/' for d in APPLICATION_DIRS)


def discover_bundle_names():
    """Lowercased names of installed `.app` bundles, with a space-free variant of each."""
    names = set()

    for directory in application_dir_prefixes():
        try:
            entries = os.listdir(directory)
        except OSError:
            continue

        for entry in entries:
            if not entry.lower().endswith('.app'):
                continue
            base = entry[:-4].lower()
            names.add(base)
            names.add(re.sub(r'[\s_-]+', '', base))

    return names


def word_text(word):
    """A word's value, or its source text when it expands at run time, for best-effort matching."""
    return word.value if word.value is not None else word.raw


def names_for(token):
    """The comparable forms of a command token: its basename, lowercased and space-free."""
    base = os.path.basename(token.rstrip('/')).lower()
    return {base, re.sub(r'[\s_-]+', '', base)}


def points_into_application(token):
    """True when the token is any path inside an applications directory or a `.app` bundle."""
    lowered = token.lower()

    if '.app/' in lowered or lowered.rstrip('/').endswith('.app'):
        return True

    expanded = os.path.expanduser(token)
    return any(expanded.startswith(prefix) for prefix in application_dir_prefixes())


def targets_application(path):
    """True when a path names an application directory, something inside one, or any `.app`.

    Wider than points_into_application() at one end and narrower at the other: an application
    directory counts as its own target, because `cp foo /Applications` writes there, while a
    bare relative word never does.
    """
    expanded = os.path.expanduser(path).rstrip('/')
    if not expanded:
        return False

    lowered = expanded.lower()
    if '.app/' in lowered or lowered.endswith('.app'):
        return True

    return any(
        expanded == prefix.rstrip('/') or expanded.startswith(prefix)
        for prefix in application_dir_prefixes()
    )


def redirect_targets(redirects):
    """Every path a redirect on this command would write to."""
    return [
        word_text(redirect.target) for redirect in redirects
        if redirect.op in WRITING_REDIRECT_OPS and redirect.target is not None
        and not redirect.benign
    ]


def flag_value(args, flags):
    """The value following any of `flags`, whether attached with `=` or given as the next word."""
    for index, arg in enumerate(args):
        for flag in flags:
            if arg == flag and index + 1 < len(args):
                return args[index + 1]
            if arg.startswith(flag + '='):
                return arg[len(flag) + 1:]
            # A single-dash short flag takes its value attached, as in `-d/Applications`.
            if len(flag) == 2 and flag[0] == '-' and flag[1] != '-' and arg.startswith(flag) \
                    and len(arg) > 2:
                return arg[2:]
    return None


def write_targets(token, args, redirects):
    """Every path this command would create, overwrite, move, delete, or re-permission."""
    names = names_for(token) if token else set()
    non_flags = [arg for arg in args if not arg.startswith('-')]
    targets = redirect_targets(redirects)

    if names & WRITE_ARGUMENT_COMMANDS:
        targets.extend(non_flags)

    if names & WRITE_DESTINATION_COMMANDS and non_flags:
        targets.append(non_flags[-1])

    if names & IN_PLACE_EDITORS and any(IN_PLACE_FLAG.match(arg) for arg in args):
        targets.extend(non_flags)

    if names & {'dd'}:
        targets.extend(arg[len('of='):] for arg in args if arg.startswith('of='))

    for name in names & set(WRITE_FLAG_DESTINATIONS):
        destination = flag_value(args, WRITE_FLAG_DESTINATIONS[name])
        if destination:
            targets.append(destination)

    for name in names & set(CONDITIONAL_WRITE_MARKERS):
        if any(arg in CONDITIONAL_WRITE_MARKERS[name] for arg in args):
            targets.extend(non_flags)

    return [target for target in targets if targets_application(target)]


def resolves_into_application(token):
    """True when a bare command name resolves, through PATH, to a binary inside an applications
    directory. A bundle name matching a command proves nothing on its own -- `Claude.app` exists
    while `claude` is ~/.local/bin/claude, and `local` is a shell builtin that resolves nowhere.
    Checking where the name actually points separates the app launcher from the coincidence."""
    if os.sep in token:
        return points_into_application(token)

    resolved = shutil.which(token)
    return bool(resolved) and points_into_application(resolved)


def first_non_flag(args):
    """The first argument that is not an option, or None."""
    for arg in args:
        if not arg.startswith('-'):
            return arg
    return None


def is_read_only(names, args, assigns):
    """True when the command only reads the paths it's given.

    An assignment ahead of the command cancels it, since variables like RIPGREP_CONFIG_PATH can
    hand a reader the same program-running flags READ_ONLY_DISQUALIFIERS looks for.
    """
    if not names & READ_ONLY_COMMANDS or assigns:
        return False
    for name in names & set(READ_ONLY_DISQUALIFIERS):
        for flag in READ_ONLY_DISQUALIFIERS[name]:
            if any(arg == flag or arg.startswith(flag + '=') for arg in args):
                return False
    return True


def applescript_text(command):
    """Everything an AppleScript runner was handed on the line: its arguments and any heredoc."""
    parts = [word_text(word) for word in command.words[1:]]
    for redirect in command.redirects:
        if redirect.heredoc is not None:
            parts.append(word_text(redirect.heredoc))
        elif redirect.op == '<<<' and redirect.target is not None:
            parts.append(word_text(redirect.target))
    return ' '.join(parts).lower()


def find_start_paths(find_command):
    """The paths a `find` searches: its operands before the first expression token."""
    paths = []
    for word in find_command.words[1:]:
        text = word_text(word)
        if text.startswith(('-', '(', '!')):
            break
        paths.append(text)
    return paths


def find_exec_args(command, commands):
    """A command's arguments, with `{}` filled in from `find` when `-exec` runs it.

    bash_ast reports `find /Applications/X.app -exec rm {} +` as `find` plus an `rm {}`, and only
    the `find` knows which paths `{}` becomes.
    """
    args = [word_text(word) for word in command.words[1:]]
    if not command.wrappers or not command.wrappers[-1].startswith('find -'):
        return args
    parent = next(
        (other for other in commands
         if other is not command and other.raw == command.raw and other.name == 'find'),
        None,
    )
    if parent is None:
        return args
    filled = []
    for arg in args:
        if '{}' in arg:
            filled.extend(arg.replace('{}', path) for path in find_start_paths(parent))
        else:
            filled.append(arg)
    return filled


def detect(commands):
    """Returns `(decision, reason)` when any of the parsed commands writes into or launches an
    application bundle, else None. Writes are checked across every command first, so a launch
    prompt can never stand in for a refusal the write rule would have given."""
    for command in commands:
        token = word_text(command.words[0]) if command.words else ''
        args = find_exec_args(command, commands)
        targets = write_targets(token, args, command.redirects)
        if targets:
            return 'deny', ('`%s` would write to %s, and nothing may write into an application '
                            'directory.' % (os.path.basename(token) or 'A redirect', targets[0]))

    bundle_names = discover_bundle_names()

    for command in commands:
        if command.opaque:
            return 'ask', ('This hook cannot tell what runs, so it might be a desktop application: '
                           '%s' % command.opaque)

        if not command.words:
            continue

        token = word_text(command.words[0])
        args = [word_text(word) for word in command.words[1:]]
        names = names_for(token)

        if os.path.expanduser(token) in APPLICATION_PATH_EXCLUSIONS:
            continue

        if points_into_application(token):
            return 'ask', 'Runs `%s` from an applications directory' % os.path.basename(token)

        mentioned = args + [
            word_text(redirect.target) for redirect in command.redirects
            if redirect.target is not None
        ]
        if any(BUNDLE_EXECUTABLE_PATH.search(arg) for arg in mentioned) \
                and not is_read_only(names, args, command.assigns):
            return 'ask', 'Hands a path inside a .app bundle to `%s`' % token

        if names & {'open'}:
            return 'ask', '`open` hands its argument to a desktop application'

        if names & {'osascript', 'osacompile'}:
            text = applescript_text(command)
            if 'tell application' in text or 'activate' in text:
                return 'ask', 'AppleScript targets a desktop application'

        if names & {'launchctl'}:
            if first_non_flag(args) in LAUNCHCTL_START_SUBCOMMANDS:
                return 'ask', '`launchctl` starts a service or agent'

        if names & AUTOMATION_TOOLS:
            return 'ask', 'Runs the browser automation driver `%s`' % token

        if names & PACKAGE_RUNNERS:
            target = first_non_flag(args)
            if target and names_for(target) & AUTOMATION_TOOLS:
                return 'ask', ('Runs the browser automation driver `%s` via %s'
                               % (target, token))

        if names & LAUNCHER_COMMANDS:
            return 'ask', 'Launches the `%s` application' % token

        if names & bundle_names and resolves_into_application(token):
            return 'ask', 'Runs the installed application "%s"' % token

    return None


def isolation_note(command):
    """For browser launches, whether the flags that protect a real profile are present."""
    if 'firefox' not in command.lower():
        return ''

    missing = [flag for flag in FIREFOX_ISOLATION_FLAGS if flag not in command]
    if not missing:
        return (' Isolation flags are present, but note that a throwaway profile does not stop '
                'the updater from touching the installed bundle.')

    return ' Missing isolation flags: %s (see the Browsers section of CLAUDE.md).' % ', '.join(missing)


def emit(decision, reason):
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': decision,
            'permissionDecisionReason': reason,
        }
    }))


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get('tool_name') != 'Bash':
        sys.exit(0)

    command = (data.get('tool_input') or {}).get('command') or ''
    if not command:
        sys.exit(0)

    if bash_ast is None:
        emit('ask', 'The bash parser failed to load, so this line might launch a desktop '
             'application unseen. Desktop applications need permission before launching.')
        sys.exit(0)

    try:
        parsed = bash_ast.parse(command)
    except bash_ast.ParseError as error:
        emit('ask', '%s, so it might launch a desktop application unseen. Desktop applications '
             'need permission before launching.' % error)
        sys.exit(0)
    except Exception:
        sys.exit(0)

    try:
        found = detect(parsed.commands)
    except Exception:
        sys.exit(0)

    if not found:
        sys.exit(0)

    decision, reason = found

    if decision == 'deny':
        emit(decision, reason)
    else:
        emit(decision, '%s. Desktop applications need permission before launching.%s'
             % (reason, isolation_note(command)))


if __name__ == '__main__':
    main()
