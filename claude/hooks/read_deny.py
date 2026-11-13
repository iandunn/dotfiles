"""
The `Read(...)` deny rules from every settings file, as absolute globs a Bash hook can match a path
against. Shared by `file-command-permissions.py` and `read-deny-permissions.py`, so a path the Read
tool is denied asks when a Bash command names it too.
"""
import fnmatch
import functools
import glob
import json
import os
import subprocess
import unicodedata

MANAGED_SETTINGS_DIRECTORY = '/Library/Application Support/ClaudeCode'

# macOS reaches the data volume through this firmlink too, and `realpath` doesn't fold it away.
DATA_VOLUME_PREFIX = '/system/volumes/data/'


@functools.lru_cache(maxsize=None)
def git_toplevel(directory):
    """The realpath of the working tree containing `directory`, or None outside any repository."""
    try:
        result = subprocess.run(
            ['git', '-C', directory, 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return os.path.realpath(result.stdout.strip())


def read_deny_patterns(session_cwd):
    """Absolute `fnmatch` globs for the `Read(...)` deny rules in every settings file, or None.

    None means the user's own settings couldn't be read, so the caller can't tell what's denied.
    A missing project or managed file just contributes nothing. The project's settings are
    looked for in the session's cwd and at its repository root, since a session can start in a
    subdirectory.
    """
    home = os.path.realpath(os.path.expanduser('~'))
    cwd = os.path.realpath(session_cwd)
    project_roots = {cwd, git_toplevel(session_cwd) or cwd}
    # After a `cd` into another repository, the project the session started in still denies.
    launch_project = os.environ.get('CLAUDE_PROJECT_DIR')
    if launch_project:
        project_roots.add(os.path.realpath(launch_project))
    sources = [
        (os.path.join(home, '.claude', 'settings.json'), os.path.join(home, '.claude'), True),
        (os.path.join(MANAGED_SETTINGS_DIRECTORY, 'managed-settings.json'), '/', False),
    ]
    for drop_in in sorted(glob.glob(
        os.path.join(MANAGED_SETTINGS_DIRECTORY, 'managed-settings.d', '*.json')
    )):
        sources.append((drop_in, '/', False))
    for project_root in project_roots:
        for name in ('settings.json', 'settings.local.json'):
            sources.append((os.path.join(project_root, '.claude', name), project_root, False))
    globs = []
    for settings_path, settings_root, required in sources:
        try:
            with open(settings_path) as settings_file:
                rules = json.load(settings_file).get('permissions', {}).get('deny', [])
        except (OSError, ValueError, AttributeError):
            if required:
                return None
            continue
        for rule in rules:
            if isinstance(rule, str) and rule.startswith('Read(') and rule.endswith(')'):
                globs += read_deny_globs(rule[5:-1], home, settings_root, project_roots)
    return globs


def read_deny_globs(pattern, home, settings_root, project_roots):
    """The absolute globs one `Read(...)` pattern covers, under Claude Code's anchoring rules.

    `//x` is absolute, `~/x` is under home, `/x` is under the settings file's root, `**/x` is
    anywhere, and a bare or `./` pattern is under the cwd. Where that's ambiguous, every reading
    is kept, and each glob also covers what's under it, as gitignore-style rules do for a
    directory, so this can only deny more than Claude Code does, never less. `fnmatch`'s `*`
    crosses `/`, so `**` needs no special handling.
    """
    if pattern.startswith('//'):
        globs = [pattern[1:]]
    elif pattern.startswith('~/'):
        globs = [home + pattern[1:]]
    elif pattern.startswith('**/'):
        globs = ['*/' + pattern[3:]]
    elif pattern.startswith('/'):
        globs = [settings_root.rstrip('/') + pattern, pattern]
    else:
        relative = pattern
        while relative.startswith('./'):
            relative = relative[2:]
        globs = [os.path.join(root, relative) for root in project_roots]
    # A path like `/etc` is a link to `/private/etc`, and a command can name it either way.
    globs += [canonical for canonical in map(canonical_glob, globs) if canonical not in globs]
    return [fold(glob_pattern) for glob_pattern in globs] + [
        fold(glob_pattern.rstrip('/')) + '/*' for glob_pattern in globs
    ]


def fold(text):
    """Text the way APFS compares names: case folded, so `ſecrets.yml` opens `secrets.yml`."""
    return unicodedata.normalize('NFC', text).casefold()


def canonical_glob(glob_pattern):
    """The glob with the links in its literal leading directories resolved."""
    if not glob_pattern.startswith('/'):
        return glob_pattern
    components = glob_pattern.split('/')
    literal = 0
    while literal < len(components) and not any(
        character in components[literal] for character in '*?['
    ):
        literal += 1
    prefix = os.path.realpath('/'.join(components[:literal]) or '/')
    if literal == len(components):
        return prefix
    return '/'.join([prefix.rstrip('/')] + components[literal:])


def is_read_denied(path, globs):
    """True if any of the `read_deny_patterns()` globs matches the absolute path."""
    path = fold(path)
    paths = [path]
    if path.startswith(DATA_VOLUME_PREFIX):
        paths.append(path[len(DATA_VOLUME_PREFIX) - 1:])
    return any(
        fnmatch.fnmatchcase(candidate, glob_pattern)
        for candidate in paths for glob_pattern in globs
    )


def denied_names(globs):
    """The last literal path component of each glob, like `('.npmrc',)` or `('.ssh',)`.

    A word that expands at run time can't be resolved to a path, but one that spells out a denied
    name, like `$HOME/.ssh/id_rsa`, can still be caught by looking for that name in its text. A
    component as short as `gh` would match unrelated words, so it keeps its parent too, as
    `('.config', 'gh')`. So does an anchored rule's name without a leading dot, like the
    `credentials` in `~/.gem/credentials`, since projects have plenty of files by that name.
    """
    names = set()
    for glob_pattern in globs:
        components = glob_pattern.split('/')
        anchored = not glob_pattern.startswith('*')
        # A rule like `**/*.pem` names files only by a pattern, which stands in as the name.
        named = [component for component in components if component not in ('', '*', '**')]
        if named and any(character in named[-1] for character in '*?['):
            names.add((named[-1],))
            continue
        for index in range(len(components) - 1, -1, -1):
            component = components[index]
            if component and not any(character in component for character in '*?['):
                generic = len(component) < 4 or (anchored and not component.startswith('.'))
                if generic and index > 0 and components[index - 1]:
                    names.add((components[index - 1], component))
                else:
                    names.add((component,))
                break
    return names


def mentions_denied_name(components, names):
    """The denied name whose components appear in order in `components`, or None.

    A name can be a pattern, like `*.pem`, so components are compared with `fnmatch`.
    """
    for name in names:
        width = len(name)
        for start in range(len(components) - width + 1):
            if all(
                fnmatch.fnmatchcase(component, part)
                for component, part in zip(components[start:start + width], name)
            ):
                return '/'.join(name)
    return None
