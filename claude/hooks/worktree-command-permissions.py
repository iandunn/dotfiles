#!/usr/bin/env python3
"""
PreToolUse permission gate for `cp`, `git add`, `git commit`, `rm`, `mv`, and
`git worktree remove`.

Before any gate runs, one shared guard: a gated command carrying a shell
operator that could run something beyond it always asks. An "allow" from this
hook covers the ENTIRE command line, so without this, `git commit -m x &&
<anything>` would ride a worktree approval out of the worktree.

The guard tracks quote state rather than scanning the raw line, because bash
does. `;`, `&`, `|`, `<`, `>`, and a newline chain a second command only
outside quotes; inside quotes of either kind bash treats each of them
literally. That distinction is what lets a multi-paragraph `git commit -m`
message through, whose body is one quoted argument no matter how many newlines
it holds. `$` and a backtick expand inside double quotes as well, so they are
refused there and unquoted alike, and permitted only inside single quotes,
where bash performs no expansion or escaping whatsoever. `$'...'` cannot slip
past on that permission: its `$` is read while still unquoted, before the quote
opens. An unterminated quote or a trailing backslash asks, since the rest of
the line cannot be read.

Single-quoted `$` and backticks are permitted because the commit convention in
CLAUDE.md puts backticks around code references, so refusing them would prompt
for nearly every commit message this gate exists to approve. The rm/mv/cp gates
re-check their own operands for `$` and backtick regardless, so relaxing the
guard here does not relax containment there.

Four independent gates, each keyed on what actually makes the command safe:

`git add` / `git commit` -- auto-approved when the session's working directory
is a LINKED git worktree under `.claude/worktrees/` (the kind the EnterWorktree
flow creates), and prompted ("ask") everywhere else: the main working tree, a
hand-made worktree elsewhere, a non-repo directory, or when git can't be
queried. The path restriction narrows the promptless surface to throwaway
trees this workflow created, instead of every linked worktree on the machine.

Rationale: per CLAUDE.md, file-mutating work belongs in an isolated worktree,
never the shared main checkout, and committing on a worktree's own branch is
explicitly sanctioned there while advancing the main checkout is not. This
removes the permission prompt for these commands inside a worktree while
keeping the prompt on the main checkout, so the friction nudges work off the
shared tree.

Unlike `cp`, `git` can be aimed somewhere other than the working directory:
`-C <path>`, `--git-dir`, and `--work-tree` would let `git add` run from inside
a worktree while staging in the main checkout, defeating a cwd-based check. So
ANY global flag between `git` and the subcommand forces a prompt instead of an
attempt to resolve the real target. That is deliberately broader than the three
redirect flags: `-c core.hooksPath=...` redirects behavior just as effectively,
and a bare `git add` / `git commit` is the only shape this gate needs to cover.

`rm` -- auto-approved only when the working directory is such a worktree AND
every operand resolves inside that worktree's root AND every file it names is
tracked by git. A cwd check alone is not enough here: a bare `git add` can only
stage in the repository it runs in, but `rm <main checkout path>` typed from
inside a worktree destroys a file in the shared checkout. Containment alone is
not enough either: an untracked worktree file is the ONLY copy of that work,
while a tracked file can be restored from the index after deletion, so only
tracked deletions are free of unrecoverable loss.

These force a prompt rather than an attempt to reason further:

    -r / -R / --recursive   this gate covers deleting FILES; a recursive
                            directory delete stays a decision worth confirming
    -d / --dir              removes an empty directory, which is exactly what
                            the `rmdir` deny rule already refuses; allowing it
                            here would route around that rule
    $, backtick, leading ~  command substitution and tilde expansion happen
                            after this hook reads the command, so the operand
                            it checked is not the path that gets deleted
    no operands             nothing to contain
    unparseable quoting     shlex cannot tokenize it, so no operand is known

Glob operands (`*`, `?`, `[`) are expanded here with glob.glob against the cwd
-- the same default rules bash uses (dotfiles excluded, extglob off) -- and
every match is containment- and tracked-checked exactly like a literal operand.
An expansion with no matches asks: bash would pass the pattern through
literally in that case, so the hook cannot know what rm will actually see.

Containment resolves the operand's PARENT with realpath and re-joins the
basename, rather than realpath-ing the whole operand. `rm somelink` deletes the
link, not its target, so resolving the final component would ask about a
contained symlink that happens to point outside. Note that `rmdir` is denied
outright in settings.json and a hook "allow" cannot clear a deny rule, so it
stays blocked everywhere, worktree or not, and is out of scope here.

One exemption: when every operand is a relative path under `.claude/tmp/`,
the hook stays SILENT instead of deciding. Scratch cleanup there is
settings.json's turf -- its `rm .claude/tmp/*` allow rules (with and without
`-f`, with and without a `command` prefix) -- and those files are untracked by
design, so this gate's tracked-only rule would re-prompt the exact cleanup the
allow rules exist to approve. Silence hands the decision back to them. The
shared operator guard runs first, so a chained or `$`-bearing command never
reaches this exemption.

The same sweep written with ABSOLUTE paths is allowed here rather than passed
back, and that asymmetry is deliberate. Those settings.json rules are literal
prefixes that an absolute path can never match, so silence would drop the
command to the auto-mode classifier with no guaranteed approval. Since
`running-commands.md` tells agents to write absolute paths, that spelling is
the one scratch cleanup actually arrives in. The operand must land inside the
WORKING DIRECTORY's own `.claude/tmp/`, not merely some path containing those
segments, which is what stops it sanctioning a sweep into another project's
scratch. The resulting grant matches what the relative rules already give.

`mv` -- auto-approved only when the working directory is a sanctioned worktree,
every operand (sources AND destination) is contained, and nothing unrecoverable
gets overwritten. Unlike `rm`, sources need no tracked requirement: a move
relocates content rather than destroying it, and the motivating use is exactly
untracked scratch. The destructive edge of `mv` is the DESTINATION, so that is
where the checks concentrate:

    dest is an existing file      must be tracked, or it is the only copy of
                                  something and gets silently replaced
    dest is a directory           must REALPATH-resolve inside the worktree (a
                                  symlinked dir would carry the file out), and
                                  each landing spot `dir/basename(src)` must be
                                  absent or tracked
    dest has glob characters      ask; expansion could pick a different target
    flags beyond -f/-i/-n/-v      ask; e.g. GNU `-t` moves the destination to a
                                  flag and defeats the last-operand rule

Source globs are expanded and containment-checked like rm's. A destination
that is a relative path under `.claude/tmp/` makes the hook stay silent, same
rationale as the rm exemption: sweeping scratch into `.claude/tmp/` is
sanctioned cleanup owned by settings.json's `mv * .claude/tmp/*` allow rules.
An absolute destination inside the working directory's own `.claude/tmp/` is
allowed here instead, for the reason the rm exemption gives. Only the
destination is examined either way, since that is the operand that decides
where the file ends up.

`cp` -- same shape as mv: the destination is where the danger lives, and it
gets mv's checks (contained, nothing untracked overwritten, realpath-resolved
directory dests, `.claude/tmp/` dest silence). Unlike mv, SOURCES may live
outside the worktree: cp only reads them, so copying a fixture in from the main
checkout writes nothing outside and destroys nothing. (mv cannot have that
freedom -- an outside source means deleting a file from the main checkout.) The
one cp-specific rule: a RECURSIVE copy onto a landing path that already exists
asks, because a directory merge can silently replace untracked files arbitrarily
deep, and checking that honestly costs more than a prompt.

`git branch -D worktree-*` -- auto-approved only when the branch holds nothing
the current branch does not already have. Worktree branches exist to carry work
back to the main checkout; once `go` has patched them in and that patch is
committed, the branch is dead weight. Git cannot see this on its own: the patch
lands as a new commit with a different SHA, so `git branch --merged` reports the
branch as unmerged forever and only `-D` can delete it.

Two independent proofs are accepted, because each covers a case the other
misses:

    content   every file the branch touched is byte-identical on HEAD
              (`git diff --quiet <branch> HEAD -- <paths it changed>`).
              Immune to squashing, reordering, and combining, since it never
              looks at commits -- and `go` collapses a branch into ONE main
              commit, so this is the case that actually occurs.
    patch-id  `git cherry HEAD <branch>` reports no `+` lines, meaning every
              commit's diff already exists on HEAD under another SHA. Catches
              the single-commit-applied-verbatim case.

Either one establishes that deleting the branch destroys no content. Neither
can report success while the work is missing: both require HEAD to already
contain it. Anything else -- a name outside the `worktree-` convention, main
having moved on top of those files, an amended patch, a git command that fails
-- asks.

What this deliberately gives up is HISTORY, not content: if a branch carried
several meaningful commits and the patch landed as one, `-D` discards those
messages and boundaries. For throwaway branches whose commits exist only to
produce a patch, that is the intended trade.

`git worktree remove` -- auto-approved when no force flag is present, and
prompted when one is. Without `--force`, git itself refuses to delete anything
that holds unique work; the observed behavior is:

    dirty worktree (modified or untracked)  fatal: ... use --force to delete it
    the main working tree                   fatal: '.' is a main working tree
    a path that is not a worktree           fatal: 'x' is not a working tree

so the only reachable outcome is deleting a clean linked worktree, whose
commits survive on its branch. `--force` defeats all of that and deletes
uncommitted work, so it stays behind a prompt. This gate is deliberately
flag-based rather than path-based: git has already established that the target
is a linked worktree, which is a stronger guarantee than any path prefix.

This hook is the SOLE authority for these commands: the corresponding entries
(`rm`, `git add`, `git commit`, `mv` in ask; a blanket `cp *` in allow) were
removed from settings.json's permission lists,
because settings rules are evaluated regardless of hook output and would
override the hook's "allow" (see the "Hook decisions don't bypass permission
rules" note in the Claude Code permissions docs). Emitting "ask" here
reproduces the previous prompt behavior independent of the active permission
mode.

Note that the hardcoded bash checks in Claude Code (`cd-git-compound`,
`multi-cd`, `shell-operators`) carry decisionReason type "other", which is NOT
re-escalated after a hook allow -- only "rule", "safetyCheck", and
"sandboxOverride" are. A hook "allow" therefore does clear those three.

A `git commit` run with `dangerouslyDisableSandbox` inside a sanctioned
worktree has been observed completing with no prompt. That was an auto-mode
session, where the classifier could have approved the re-escalated sandbox
override on its own rather than the allow clearing it, and the autoMode
`soft_deny` list exempts worktree commits by name. Sessions here run in auto
mode, so the promptless outcome is the real one either way; what it does not
establish is how the same command behaves with auto mode off.

A linked worktree is detected by comparing `git rev-parse --git-dir` against
`--git-common-dir`: they resolve to the same path in the main working tree and
differ in a linked worktree (git-dir is <common-dir>/worktrees/<name>).

The settings.json `if` filters already scope this hook to the commands above,
but each command is re-checked here as defense in depth: without that guard, a
hook wired without the filter would gate *every* Bash command.

The filters cannot enumerate every way of writing these commands -- they are
literal prefixes, so `git --git-dir=/x add .` matches none of them and never
reaches this hook. Nothing regresses when that happens: such a shape matched no
permissions.ask entry before this hook existed either, so it falls through to
the same place it always did.
"""
import glob
import json
import os
import re
import shlex
import subprocess
import sys


def emit(decision, reason):
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': decision,
            'permissionDecisionReason': reason,
        }
    }))


# Global git options that consume the following argument, so the token after
# them is a value rather than the subcommand.
GIT_GLOBAL_FLAGS_TAKING_A_VALUE = {
    '-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path',
    '--super-prefix', '--config-env',
}


# Operators that expand into another command wherever bash still expands anything, which is
# everywhere but inside single quotes.
EXPANDING_OPERATORS = ('$', '`')

# Operators that chain a second command only when they sit outside quotes. Inside quotes of
# either kind bash treats every one of them literally, which is what lets the newlines in a
# multi-paragraph commit message through.
CHAINING_OPERATORS = (';', '&', '|', '<', '>', '\n')


def shell_operator_reason(command):
    """Return why bash might run more than this one gated command, or None."""
    quote = None
    escaped = False

    for character in command:
        if escaped:
            escaped = False
        elif character == '\\' and quote != "'":
            escaped = True
        elif quote == "'":
            if character == "'":
                quote = None
        elif quote == '"':
            if character == '"':
                quote = None
            elif character in EXPANDING_OPERATORS:
                return f'{character!r} expands even inside double quotes'
        elif character in ('"', "'"):
            quote = character
        elif character in EXPANDING_OPERATORS:
            return f'{character!r} outside quotes can expand into another command'
        elif character in CHAINING_OPERATORS:
            return f'{character!r} outside quotes can chain a second command onto this one'

    if quote is not None:
        return 'a quote is left open, so the rest of the line cannot be read'
    if escaped:
        return 'the line ends in a backslash, so it continues where this hook cannot see'
    return None


def is_gated_command(command):
    """True for the commands this hook gates, checked on the raw string.

    Deliberately loose on git: only add/commit/worktree-remove are gated, but
    this decides which lines the operator guard runs on, and a line carrying an
    operator is exactly the kind whose subcommand cannot be identified
    reliably. Answering yes for every git line costs nothing, since a git line
    with no operator falls through to the real subcommand check below.
    """
    stripped = command.strip()
    if stripped.startswith('command '):
        stripped = stripped[len('command '):].lstrip()
    return re.match(r'^(rm|mv|cp|git)\b', stripped) is not None


def is_relative_claude_tmp_path(operand):
    """True if the operand textually names a path under ./.claude/tmp/."""
    if os.path.isabs(operand):
        return False
    normalized = os.path.normpath(operand)
    scratch_dir = os.path.join('.claude', 'tmp')
    return normalized == scratch_dir or normalized.startswith(scratch_dir + os.sep)


def is_cwd_claude_tmp_path(operand, cwd):
    """True if the operand resolves inside the working directory's own `.claude/tmp/`.

    The final component is left unresolved for the same reason containment does
    it: a symlink operand names the link, not what it points at.
    """
    scratch_root = os.path.join(os.path.realpath(cwd), '.claude', 'tmp')
    absolute = os.path.normpath(os.path.join(cwd, operand))
    parent = os.path.realpath(os.path.dirname(absolute))
    resolved = os.path.join(parent, os.path.basename(absolute))
    return resolved == scratch_root or resolved.startswith(scratch_root + os.sep)


def sweeps_into_cwd_scratch(operands, cwd):
    """True if every operand lands in this working directory's `.claude/tmp/`.

    This is the absolutely-spelled twin of the `is_relative_claude_tmp_path`
    exemption, and it exists because `running-commands.md` tells agents to write
    absolute paths, so that is the spelling scratch cleanup actually arrives in.
    The two are handled differently: a relative operand makes the hook stay
    silent so settings.json's `.claude/tmp/` allow rules decide, while an
    absolute one is allowed here, because those rules are literal prefixes that
    an absolute path can never match and silence would drop the command to the
    auto-mode classifier with no guaranteed approval.

    Scoping to the working directory's own scratch directory, rather than any
    path with `.claude/tmp/` in it, is what keeps this from sanctioning a sweep
    into some other project's scratch. The grant that results is the same one
    the relative rules already give.
    """
    return bool(operands) and all(
        not expands_after_this_hook(operand) and is_cwd_claude_tmp_path(operand, cwd)
        for operand in operands
    )


def strip_command_prefix(tokens):
    """Drop a leading `command` builtin, which CLAUDE.md uses to bypass aliases."""
    if tokens and tokens[0] == 'command':
        return tokens[1:]
    return tokens


def git_globals_and_subcommand(tokens):
    """Split `git [globals] <subcommand> ...` into (globals, subcommand)."""
    globals_used = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith('-'):
            return globals_used, token
        globals_used.append(token)
        index += 2 if token in GIT_GLOBAL_FLAGS_TAKING_A_VALUE else 1
    return globals_used, None


def is_worktree_remove(command):
    return re.match(r'^git\s+worktree\s+remove\b', command.strip()) is not None


def rm_flags_and_operands(tokens):
    """Split an `rm` invocation into (flags, operands), honoring the `--` terminator."""
    flags = []
    operands = []
    end_of_flags = False
    for token in tokens[1:]:
        if not end_of_flags and token == '--':
            end_of_flags = True
        elif not end_of_flags and token.startswith('-') and token != '-':
            flags.append(token)
        else:
            operands.append(token)
    return flags, operands


def has_recursive_flag(flags):
    return any(
        flag in ('--recursive', '--dir') or re.match(r'^-[a-zA-Z]*[rRd]', flag)
        for flag in flags
    )


def expands_after_this_hook(operand):
    """True if the shell will rewrite this operand into a path we cannot see now."""
    return '$' in operand or '`' in operand or operand.startswith('~')


GLOB_CHARS = ('*', '?', '[')


def expand_globs(operand, cwd):
    """Expand a glob operand the way bash would by default; a literal operand passes through."""
    if not any(char in operand for char in GLOB_CHARS):
        return [operand]
    return glob.glob(os.path.join(glob.escape(cwd), operand))


def is_tracked(path, cwd):
    try:
        result = subprocess.run(
            ['git', '-C', cwd, 'ls-files', '--error-unmatch', '--', path],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def is_inside(operand, root, cwd):
    """True if the operand names a path within root, without resolving its final component."""
    absolute = os.path.normpath(os.path.join(cwd, operand))
    parent = os.path.realpath(os.path.dirname(absolute))
    resolved = os.path.join(parent, os.path.basename(absolute))
    return resolved == root or resolved.startswith(root + os.sep)


def has_force_flag(command):
    """True if any argument is a force flag, including short-flag clusters like `-fv`."""
    for token in shlex.split(command):
        if token == '--':
            break
        if token == '--force' or token.startswith('--force='):
            return True
        if re.match(r'^-[a-zA-Z]*f', token):
            return True
    return False


def git_rev_parse(cwd, flag):
    try:
        result = subprocess.run(
            ['git', '-C', cwd, 'rev-parse', flag],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def is_linked_worktree(cwd):
    git_dir = git_rev_parse(cwd, '--git-dir')
    common_dir = git_rev_parse(cwd, '--git-common-dir')
    if not git_dir or not common_dir:
        return False

    # git-dir can be returned relative (".git" in the main tree) while
    # common-dir is absolute, so resolve both against cwd before comparing.
    def resolve(path):
        return os.path.realpath(os.path.join(cwd, path))

    return resolve(git_dir) != resolve(common_dir)


def sanctioned_worktree_root(cwd):
    """The worktree root if cwd is inside a linked worktree under `.claude/worktrees/`, else None."""
    if not is_linked_worktree(cwd):
        return None
    toplevel = git_rev_parse(cwd, '--show-toplevel')
    if not toplevel:
        return None
    root = os.path.realpath(toplevel)
    if f'{os.sep}.claude{os.sep}worktrees{os.sep}' not in root + os.sep:
        return None
    return root


WORKTREE_BRANCH_PREFIX = 'worktree-'


def git_output(cwd, *args):
    """Run a read-only git command; return stdout, or None if it failed."""
    try:
        result = subprocess.run(
            ['git', '-C', cwd, *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def branch_content_is_on_head(branch, cwd):
    """True if every file the branch touched is identical on HEAD."""
    base = git_output(cwd, 'merge-base', branch, 'HEAD')
    if base is None:
        return False

    names = git_output(cwd, 'diff', '--name-only', base.strip(), branch)
    if names is None:
        return False

    paths = [path for path in names.splitlines() if path]
    if not paths:
        return True

    return git_output(cwd, 'diff', '--quiet', branch, 'HEAD', '--', *paths) is not None


def branch_commits_are_on_head(branch, cwd):
    """True if every commit on the branch has a patch-id equivalent on HEAD."""
    cherry = git_output(cwd, 'cherry', 'HEAD', branch)
    if cherry is None:
        return False
    return not any(line.startswith('+') for line in cherry.splitlines())


def is_branch_delete(tokens):
    return (
        len(tokens) >= 2
        and tokens[0] == 'git'
        and tokens[1] == 'branch'
        and any(re.fullmatch(r'--delete|-[a-zA-Z]*[dD]', token) for token in tokens[2:])
    )


def decide_branch_delete(tokens, cwd):
    """Allow deleting a worktree branch whose content is already on HEAD."""
    operands = [token for token in tokens[2:] if not token.startswith('-')]

    if len(operands) != 1:
        return 'ask', 'Delete one branch at a time so each can be checked; confirm this'

    branch = operands[0]
    if not branch.startswith(WORKTREE_BRANCH_PREFIX):
        return 'ask', f'`{branch}` is not a {WORKTREE_BRANCH_PREFIX}* branch; confirm this delete'

    if git_output(cwd, 'rev-parse', '--verify', f'refs/heads/{branch}') is None:
        return 'ask', f'`{branch}` is not a local branch here; confirm this delete'

    if branch_content_is_on_head(branch, cwd):
        return 'allow', f'Every file `{branch}` touched is identical on HEAD; nothing to lose'

    if branch_commits_are_on_head(branch, cwd):
        return 'allow', f'Every commit on `{branch}` already exists on HEAD by patch-id'

    return 'ask', (f'`{branch}` holds content HEAD does not have; deleting it would '
                   'destroy that work; confirm this delete')


def decide_rm(tokens, cwd):
    """Allow only a non-recursive rm of tracked files contained in a sanctioned worktree.

    Returns (decision, reason), or None to stay silent and leave the decision
    to settings.json rules.
    """
    flags, operands = rm_flags_and_operands(tokens)

    if operands and all(is_relative_claude_tmp_path(operand) for operand in operands):
        return None

    if sweeps_into_cwd_scratch(operands, cwd):
        return 'allow', "Every operand is in this directory's own .claude/tmp/ scratch"

    root = sanctioned_worktree_root(cwd)
    if not root:
        return 'ask', 'Not inside a .claude/worktrees/ worktree; confirm this rm'

    if not operands:
        return 'ask', 'This rm has no operands to check; confirm it'
    if has_recursive_flag(flags):
        return 'ask', 'This rm removes directories, not just files; confirm it'

    for operand in operands:
        if expands_after_this_hook(operand):
            return 'ask', f'`{operand}` expands to a path this hook cannot see; confirm this rm'
        if not is_inside(operand, root, cwd):
            return 'ask', f'`{operand}` is outside the worktree at {root}; confirm this rm'
        targets = expand_globs(operand, cwd)
        if not targets:
            return 'ask', f'`{operand}` matches nothing here; confirm this rm'
        for target in targets:
            if not is_inside(target, root, cwd):
                return 'ask', f'`{target}` is outside the worktree at {root}; confirm this rm'
            if not is_tracked(target, cwd):
                return 'ask', f'`{target}` is untracked, so git cannot restore it; confirm this rm'

    return 'allow', f'Non-recursive rm of tracked files inside the worktree at {root}'


def decide_mv(tokens, cwd):
    """Allow mv when everything it touches stays inside a sanctioned worktree and
    nothing unrecoverable gets overwritten.

    Returns (decision, reason), or None to stay silent and leave the decision
    to settings.json rules.
    """
    flags, operands = rm_flags_and_operands(tokens)

    if operands and is_relative_claude_tmp_path(operands[-1]):
        return None

    if operands and sweeps_into_cwd_scratch(operands[-1:], cwd):
        return 'allow', "mv into this directory's own .claude/tmp/ scratch"

    root = sanctioned_worktree_root(cwd)
    if not root:
        return 'ask', 'Not inside a .claude/worktrees/ worktree; confirm this mv'

    for flag in flags:
        if not re.fullmatch(r'-[finv]+', flag):
            return 'ask', f'`{flag}` changes how mv picks its destination; confirm this mv'

    if len(operands) < 2:
        return 'ask', 'This mv has no source and destination to check; confirm it'

    sources, dest = operands[:-1], operands[-1]

    for operand in operands:
        if expands_after_this_hook(operand):
            return 'ask', f'`{operand}` expands to a path this hook cannot see; confirm this mv'
        if not is_inside(operand, root, cwd):
            return 'ask', f'`{operand}` is outside the worktree at {root}; confirm this mv'

    if any(char in dest for char in GLOB_CHARS):
        return 'ask', f'`{dest}` is a glob destination; confirm this mv'

    expanded_sources = []
    for source in sources:
        matches = expand_globs(source, cwd)
        if not matches:
            return 'ask', f'`{source}` matches nothing here; confirm this mv'
        for match in matches:
            if not is_inside(match, root, cwd):
                return 'ask', f'`{match}` is outside the worktree at {root}; confirm this mv'
        expanded_sources.extend(matches)

    dest_absolute = os.path.normpath(os.path.join(cwd, dest))
    dest_real = os.path.realpath(dest_absolute)
    if os.path.isdir(dest_real):
        if dest_real != root and not dest_real.startswith(root + os.sep):
            return 'ask', f'`{dest}` resolves outside the worktree at {root}; confirm this mv'
        for source in expanded_sources:
            source_name = os.path.basename(os.path.normpath(os.path.join(cwd, source)))
            landing = os.path.join(dest_real, source_name)
            if os.path.lexists(landing) and not is_tracked(landing, cwd):
                return 'ask', (f'`{landing}` exists and is untracked; this mv would '
                               'silently replace the only copy; confirm it')
    else:
        if len(expanded_sources) > 1:
            return 'ask', 'Multiple sources need a directory destination; confirm this mv'
        if os.path.lexists(dest_absolute) and not is_tracked(dest_absolute, cwd):
            return 'ask', (f'`{dest}` exists and is untracked; this mv would silently '
                           'replace the only copy; confirm it')

    return 'allow', f'mv contained in the worktree at {root}; nothing unrecoverable overwritten'


def decide_cp(tokens, cwd):
    """Allow cp when everything it names stays inside a sanctioned worktree and
    nothing unrecoverable gets overwritten.

    Returns (decision, reason), or None to stay silent and leave the decision
    to settings.json rules.
    """
    flags, operands = rm_flags_and_operands(tokens)

    if operands and is_relative_claude_tmp_path(operands[-1]):
        return None

    if operands and sweeps_into_cwd_scratch(operands[-1:], cwd):
        return 'allow', "cp into this directory's own .claude/tmp/ scratch"

    root = sanctioned_worktree_root(cwd)
    if not root:
        return 'ask', 'Not inside a .claude/worktrees/ worktree; confirm this cp'

    for flag in flags:
        if not re.fullmatch(r'-[RrfinvpaXcLPH]+', flag):
            return 'ask', f'`{flag}` is not a cp flag this gate reasons about; confirm this cp'
    recursive = any(char in 'Rra' for flag in flags for char in flag[1:])

    if len(operands) < 2:
        return 'ask', 'This cp has no source and destination to check; confirm it'

    sources, dest = operands[:-1], operands[-1]

    for operand in operands:
        if expands_after_this_hook(operand):
            return 'ask', f'`{operand}` expands to a path this hook cannot see; confirm this cp'

    if not is_inside(dest, root, cwd):
        return 'ask', f'`{dest}` is outside the worktree at {root}; confirm this cp'

    if any(char in dest for char in GLOB_CHARS):
        return 'ask', f'`{dest}` is a glob destination; confirm this cp'

    expanded_sources = []
    for source in sources:
        matches = expand_globs(source, cwd)
        if not matches:
            return 'ask', f'`{source}` matches nothing here; confirm this cp'
        expanded_sources.extend(matches)

    dest_absolute = os.path.normpath(os.path.join(cwd, dest))
    dest_real = os.path.realpath(dest_absolute)
    if os.path.isdir(dest_real):
        if dest_real != root and not dest_real.startswith(root + os.sep):
            return 'ask', f'`{dest}` resolves outside the worktree at {root}; confirm this cp'
        landings = [
            os.path.join(dest_real, os.path.basename(os.path.normpath(os.path.join(cwd, source))))
            for source in expanded_sources
        ]
    else:
        if len(expanded_sources) > 1:
            return 'ask', 'Multiple sources need a directory destination; confirm this cp'
        landings = [dest_absolute]

    for landing in landings:
        if not os.path.lexists(landing):
            continue
        if recursive:
            return 'ask', (f'`{landing}` already exists; a recursive copy can silently replace '
                           'untracked files inside it; confirm this cp')
        if not is_tracked(landing, cwd):
            return 'ask', (f'`{landing}` exists and is untracked; this cp would silently '
                           'replace the only copy; confirm it')

    return 'allow', f'cp contained in the worktree at {root}; nothing unrecoverable overwritten'


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')
    cwd = data.get('cwd') or os.getcwd()

    if is_gated_command(command):
        operator_reason = shell_operator_reason(command)
        if operator_reason:
            emit('ask', f'{operator_reason}, so this may reach beyond one gated command; confirm it')
            return

    if is_worktree_remove(command):
        try:
            forced = has_force_flag(command)
        except ValueError:
            emit('ask', 'Could not parse the arguments of this git worktree remove; confirm it')
            return
        if forced:
            emit('ask', 'git worktree remove --force deletes uncommitted work; confirm it')
        else:
            emit('allow', 'git worktree remove without --force cannot delete a dirty or non-worktree path')
        return

    try:
        tokens = strip_command_prefix(shlex.split(command))
    except ValueError:
        emit('ask', 'Could not parse the arguments of this command; confirm it')
        return

    if not tokens:
        return

    if tokens[0] == 'rm':
        decision = decide_rm(tokens, cwd)
        if decision:
            emit(*decision)
        return

    if tokens[0] == 'mv':
        decision = decide_mv(tokens, cwd)
        if decision:
            emit(*decision)
        return

    if tokens[0] == 'cp':
        decision = decide_cp(tokens, cwd)
        if decision:
            emit(*decision)
        return

    if is_branch_delete(tokens):
        emit(*decide_branch_delete(tokens, cwd))
        return

    if tokens[0] == 'git':
        git_globals, subcommand = git_globals_and_subcommand(tokens)
        if subcommand not in ('add', 'commit'):
            return
        if git_globals:
            emit('ask', f'`{git_globals[0]}` can aim git outside this worktree; '
                        f'confirm this git {subcommand}')
        elif sanctioned_worktree_root(cwd):
            emit('allow', f'Inside a .claude/worktrees/ worktree; git {subcommand} auto-approved')
        else:
            emit('ask', f'Not inside a .claude/worktrees/ worktree; confirm this git {subcommand}')


if __name__ == '__main__':
    main()
