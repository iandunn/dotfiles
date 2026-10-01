#!/usr/bin/env python3
"""
PreToolUse permission gate for `cp`, `git add`, `git commit`, `git push`, `rm`, `mv`,
`git worktree remove`, and the read-only git subcommands in
GIT_READ_ONLY_SUBCOMMANDS.

Before any gate runs, one shared guard: a gated command carrying a shell
operator that could run something beyond it never gets an allow. An "allow"
from this hook covers the ENTIRE command line, so without this, `git commit -m
x && <anything>` would ride a worktree approval out of the worktree.

The scanning lives in `shell_line_shapes`, shared with
`command-allowlist-permissions.py` so the two cannot disagree about how bash
reads a line. It tracks quote state rather than scanning the raw string,
because bash does. `;`, `&`, `|`, `<`, `>`, and a newline separate commands
only outside quotes; inside quotes of either kind bash treats each of them
literally. That distinction is what lets a multi-paragraph `git commit -m`
message through, whose body is one quoted argument no matter how many newlines
it holds. `$` and a backtick expand inside double quotes as well, so they are
refused there and unquoted alike, and permitted only inside single quotes,
where bash performs no expansion or escaping whatsoever. `$'...'` cannot slip
past on that permission: its `$` is read while still unquoted, before the quote
opens.

What the guard does about a finding depends on whether the caller could have
avoided it. `;`, `&`, `|`, and a newline are DENIED, because splitting the line
into one tool call per command is a fix the caller can always apply, and saying
so is more useful than asking a person to approve a line nobody needed to
write. A redirect to a real file, an expansion, a subshell, an unterminated
quote, and a trailing backslash all ASK, because no such rewrite exists.

Three shapes don't count as reaching beyond the command at all. A redirect to
`/dev/null` or a file descriptor throws output away, and it is stripped before
the arguments are read so it can't be mistaken for an operand. A pipeline
ending in `head`, `tail`, or `wc` is judged as the command that feeds it, since
those three read stdin and write stdout and can do nothing else; the tail comes
off before the guard runs. A `>` or `>>` whose destination is inside this
directory's `.claude/tmp/` or Claude Code's own session directory under an OS
temporary directory writes only scratch, so `strip_scratch_redirects` cuts it
out before the guard runs too. Every redirect on the line has to qualify, and a
destination that expands, globs, or resolves through a symlink out of scratch
disqualifies the line; `git --output` to the same places is cleared the same
way, in `git_read_only_option_reason`.

Single-quoted `$` and backticks are permitted because the commit convention in
CLAUDE.md puts backticks around code references, so refusing them would prompt
for nearly every commit message this gate exists to approve. The rm/mv/cp gates
re-check their own operands for `$` and backtick regardless, so relaxing the
guard here does not relax containment there.

Four independent gates, each keyed on what actually makes the command safe:

`git add` / `git commit` -- auto-approved when git runs in a LINKED git
worktree under `.claude/worktrees/` (the kind the EnterWorktree flow creates),
whether that is the session's working directory or a single `-C <path>` aimed
there. The path restriction narrows the promptless surface to throwaway trees
this workflow created, instead of every linked worktree on the machine.

Everywhere else the hook stays SILENT for a commit that names its files, so the
autoMode `soft_deny` rule in settings.json decides it: the classifier lets it
through only when the user asked for the commit. What the hook still prompts
on outside a worktree is anything that might stage more than the files it
names, because the main checkout holds other sessions' uncommitted work. That
check fails closed: every option has to be on GIT_STAGING_SAFE_OPTIONS and
every pathspec has to be a literal path to a file strictly below the repository
root, so `-A`, `-Av`, `--al`, `commit -a`, `--pathspec-from-file`, a glob, a
`:` magic, a directory, and `.` or `..` all prompt. Naming files is what keeps a commit to this
session's changes, and CLAUDE.md tells the agent to stage that way, Relay's
commit phases included.

Any global flag other than a single `-C` prompts, whatever the subcommand.
`--git-dir` and `--work-tree` aim git somewhere else, `-c core.hooksPath=...`
changes what it runs, and `-c alias.x=push` turns any name into any
subcommand. More than one `-C` prompts too, since each is resolved relative to
the last. A subcommand that is a configured alias prompts for the same reason.
A single `-C` ahead of a subcommand in GIT_SUBCOMMANDS_GATED_BY_SETTINGS
prompts too, because it hides the line from prefix rules like
`Bash(git clean*)` that would otherwise deny or ask about it.

`git push` and the other GIT_PUSHING_SUBCOMMANDS prompt in every shape that
starts with `git` or `command git`, including `git -C <path> push`, which the
settings.json `Bash(git push *)` ask rule cannot match. A line that reaches git
some other way, like `env git push` or `/usr/bin/git push`, never gets here.

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

Source globs are expanded and containment-checked like rm's.

A destination inside the working directory's own `.claude/tmp/` takes a
separate path, `decide_mv_into_scratch`, written either relatively or
absolutely. Sweeping scratch there is sanctioned cleanup, but `mv` deletes the
source, so the checks invert: the destination is already known to be scratch,
and it is the SOURCES that decide whether this is cleanup or displacement. A
source qualifies when it is under an OS temp directory -- where the Chrome MCP
must write screenshots before CLAUDE.md has them moved into the project -- or
is an untracked file inside the working directory, which is where an agent's
stray output lands. Anything else asks, so a file of the user's cannot be
displaced into scratch without confirmation. This gate is the sole authority
for that shape: settings.json's `mv * .claude/tmp/*` allow rules were removed,
since they would override it and reinstate the unrestricted grant.

`cp` -- the destination is where the danger lives, and it gets mv's worktree
checks (contained, nothing untracked overwritten, realpath-resolved directory
dests). A destination under `.claude/tmp/` is exempt the way rm's operands are:
silent when relative, allowed here when absolute. That grant needs no source
restriction, because a copy leaves the original in place and so cannot displace
anything. SOURCES may likewise live outside the worktree: cp only reads them, so
copying a fixture in from the main checkout writes nothing outside and destroys
nothing. (mv cannot have that freedom -- an outside source means deleting a file
from wherever it came from.) The
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

`git [-C <path>] <read-only subcommand>` -- auto-approved for a subcommand in
GIT_READ_ONLY_SUBCOMMANDS when no global option other than `-C <path>` sits
between `git` and the subcommand, and no argument after it names a program to
run or a file to write. A settings.json rule like `Bash(git -C * diff *)`
cannot express the first half: its wildcard spans as many tokens as it likes,
so `git -C . -c diff.external=/bin/sh diff HEAD~1 HEAD` matched it and ran the
injected program with no prompt. Each global option is a way to change what a
read-only subcommand executes (`-c` sets any config, `--exec-path` swaps the
git binaries themselves), so none of them is vouched for. The `-C` path itself
is unrestricted, matching what those rules granted: reading a repository
anywhere on the machine is the point of the flag.

The second half covers the options a prefix rule like `Bash(git grep *)` waves
through, each observed running or writing with no prompt:

    --output[=<file>]            diff/log/show/stash list write their output there
    grep -O / --open-files-in-pager  runs the named program on the matching files
    fetch --upload-pack          runs the named program to serve the fetch
    fetch <non-remote-name>      a path or URL is served by a program fetch runs
                                 locally, and an `ext::<command>` helper IS one
    diff --no-index, or diff with two operands and either outside the working
                                 tree: git prints both files from disk, wherever
                                 they are, with no repository involved

`git fetch` therefore auto-approves only against a plain remote name (or none,
for `--all`); a refspec with `:` in it prompts too, which is a false positive
accepted for the simpler rule.

This hook is the SOLE authority for these commands: the corresponding entries
(`rm`, `git add`, `git commit`, `mv` in ask; a blanket `cp *`, the ten
`git -C * <subcommand> *` rules, and the bare `git diff *`, `git fetch *`,
`git grep *`, `git log *`, and `git show *` rules in allow) were removed from
settings.json's permission lists,
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
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import shell_line_shapes
except ImportError as error:
    # Letting the traceback stand would exit non-zero, which Claude Code reads as "no opinion",
    # dropping every command this hook gates to the auto-mode classifier. Failing closed with a
    # prompt is the whole point of the hook.
    print(json.dumps({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'ask',
            'permissionDecisionReason': (
                f'shell_line_shapes failed to load, so this hook cannot vouch for the '
                f'command: {error}'
            ),
        }
    }))
    sys.exit(0)


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

# Subcommands that leave the working tree alone, auto-approved with no global option beyond `-C`
# and no program-running or file-writing argument. A multi-word entry has to match the tokens
# after the subcommand too, so `stash list` reads while `stash drop` falls through to whatever
# settings.json says.
GIT_READ_ONLY_SUBCOMMANDS = frozenset({
    ('diff',), ('fetch',), ('grep',), ('log',), ('ls-tree',), ('remote', 'get-url'), ('show',),
    ('stash', 'list'), ('stash', 'show'), ('status',), ('symbolic-ref',),
})

# A `git fetch` operand that is only a remote name. Anything else -- a URL, a filesystem path, or a
# `<helper>::<address>` like `ext::sh -c ...` -- can make fetch run a program. Git refuses a remote
# name beginning with `.`, which is what keeps `.` and `..` on the path side of the line.
GIT_REMOTE_NAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._-]*')

# A short-option cluster carrying grep's `-O`, whose optional value names the pager to run.
GIT_GREP_PAGER_CLUSTER = re.compile(r'-[^-]*O')


def shell_operator_decision(command):
    """Return (decision, reason) when bash might run more than this one gated command, or None.

    A chaining operator is refused outright rather than prompted, because the agent that wrote it
    always has a mechanical fix: run each command in its own tool call. Refusing states that fix
    where the agent can act on it, instead of asking a person to approve something nobody needed
    to write. Everything else prompts, because there's no equivalent rewrite -- a `$` can expand
    to anything, a `> file` decomposes only into a different tool, and a line whose quoting can't
    be read to the end can't be advised about at all.
    """
    finding = shell_line_shapes.first_operator(command)
    if finding is None:
        return None

    kind, description = finding
    if kind == shell_line_shapes.CHAIN:
        return 'deny', (
            f'{description}, so this may reach beyond one gated command. Run each command in '
            'its own tool call (running-commands.md). A trailing `| head`, `| tail`, or `| wc` '
            'is the only pipeline this hook accepts; do not reword the line to get past this.'
        )
    return 'ask', f'{description}, so this may reach beyond one gated command; confirm it'


def is_gated_command(command):
    """True for the commands this hook gates, checked on the raw string.

    Deliberately loose on git: only add, commit, worktree remove, branch
    deletion, and the read-only subcommands are gated, but this decides which
    lines the operator guard runs on, and a line carrying an operator is
    exactly the kind whose subcommand cannot be identified reliably. Answering
    yes for every git line costs nothing, since a git line with no operator
    falls through to the real subcommand check below.
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


def resolve_all_but_final(operand, cwd):
    """Resolve the operand the way the kernel walks it, leaving only a plain final name unresolved.

    A symlink operand names the link rather than what it points at, so `rm link` touches only the
    link. Everything before it is resolved physically rather than normalized first, because the
    kernel follows `link/..` to the link target's parent, where `normpath` would collapse it as
    text. A final `.` or `..`, or a trailing slash, makes the kernel follow the last component
    too, so those resolve in full.
    """
    absolute = os.path.join(cwd, operand)
    if operand.endswith(os.sep) or os.path.basename(absolute) in ('.', '..'):
        return os.path.realpath(absolute)
    return os.path.join(os.path.realpath(os.path.dirname(absolute)), os.path.basename(absolute))


def is_cwd_claude_tmp_path(operand, cwd):
    """True if the operand, and every path a glob in it matches, lies in the cwd's `.claude/tmp/`.

    A glob is expanded first, because `*` can match a directory symlink partway along the path and
    carry the operand out of scratch.
    """
    if expands_after_this_hook(operand):
        return False
    scratch_root = os.path.join(os.path.realpath(cwd), '.claude', 'tmp')
    # Bash passes a glob that matches nothing through as literal text.
    for match in expand_globs(operand, cwd) or [operand]:
        resolved = resolve_all_but_final(match, cwd)
        if resolved != scratch_root and not resolved.startswith(scratch_root + os.sep):
            return False
    return True


def is_cwd_scratch_write_destination(operand, cwd):
    """True if writing into or through this operand can only touch the cwd's own `.claude/tmp/`.

    `cp` and `mv` write through a symlink destination, or into the directory it points at, so
    unlike `is_cwd_claude_tmp_path` this resolves the final component too, and refuses a file that
    shares its inode with another name.
    """
    return is_scratch_destination(operand, cwd, include_agent_temp=False)


SCRATCH_DESTINATION_ESCAPES = (
    '`{operand}` leads out of .claude/tmp/ through a link, or shares its inode with a file '
    'outside it, so this {command} could write there; confirm it'
)


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


def temp_roots():
    """The directories the OS hands out for temporary files, fully resolved."""
    return [
        os.path.realpath(path)
        for path in (tempfile.gettempdir(), '/tmp', '/var/folders')
    ]


def is_agent_scratch_source(operand, cwd):
    """True if the operand names something an agent produced rather than a file of the user's.

    Two shapes qualify. Anything under an OS temporary directory does, because
    the Chrome MCP can only write screenshots there and CLAUDE.md then asks for
    them to be moved into the project. So does an untracked file inside the
    working directory, which is where an agent's stray output lands. A tracked
    file is excluded: moving one into scratch is a change to the repository, not
    cleanup.
    """
    resolved = resolve_all_but_final(operand, cwd)

    for root in temp_roots():
        if resolved == root or resolved.startswith(root + os.sep):
            return True

    cwd_root = os.path.realpath(cwd)
    inside_cwd = resolved == cwd_root or resolved.startswith(cwd_root + os.sep)
    return inside_cwd and is_untracked_work_tree_file(resolved)


def true_case_path(path):
    """The absolute path spelled with each component's case as stored on disk, or None if missing."""
    result = os.sep
    for component in path.strip(os.sep).split(os.sep):
        try:
            entries = os.listdir(result)
        except OSError:
            return None
        if component in entries:
            result = os.path.join(result, component)
            continue
        matches = [entry for entry in entries if entry.lower() == component.lower()]
        if len(matches) != 1:
            return None
        result = os.path.join(result, matches[0])
    return result


def is_untracked_work_tree_file(resolved):
    """True if this is a plain file that git sees as untracked, rather than as the user's.

    Being absent from the index alone isn't enough. Outside any repository nothing is in an
    index, a gitignored file is one the user chose to keep out of it, and a directory or a `.git`
    entry can hold the repository itself. Git is asked from the file's own directory, so a file
    in a nested repository is judged by that repository. The path's real letter case is restored
    first, because the filesystem opens `CLAUDE/claude.md` as the tracked `claude/CLAUDE.md`
    while git's index lookup is case-sensitive.
    """
    resolved = true_case_path(resolved)
    if resolved is None or '.git' in resolved.split(os.sep):
        return False
    if os.path.islink(resolved) or not os.path.isfile(resolved):
        return False
    directory = os.path.dirname(resolved)
    if git_toplevel(directory) is None or is_tracked(resolved, directory):
        return False
    try:
        ignored = subprocess.run(
            ['git', '-C', directory, 'check-ignore', '-q', '--', resolved],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return ignored.returncode == 1


# Claude Code names its per-session scratch directory after itself and puts it directly under an
# OS temporary directory, as `/private/tmp/claude-501/<project>/<session>/scratchpad`, with the
# user's uid as the suffix. Matching that shape exactly is what separates a session's scratchpad
# from the temporary files every other program on the machine keeps in the same place, and from
# Claude Code's own task output, which sits beside the scratchpad.
AGENT_TEMP_PREFIX = 'claude'


def is_agent_temp_path(resolved):
    """True if this resolved path is inside Claude Code's own directory under an OS temp root."""
    for root in temp_roots():
        if not resolved.startswith(root + os.sep):
            continue
        segments = resolved[len(root) + 1:].split(os.sep)
        if (len(segments) > 4 and segments[0] == f'{AGENT_TEMP_PREFIX}-{os.getuid()}'
                and segments[3] == 'scratchpad'):
            return True
    return False


def is_scratch_destination(target, cwd, resolve_from=None, include_agent_temp=True):
    """True if writing to this path can only touch scratch.

    `resolve_from` is the directory a relative target is written relative to, when that isn't
    `cwd` -- git's `-C` directory, for `--output`. Scratch itself always belongs to `cwd`, the
    session's working directory, whichever directory the writer runs in. `include_agent_temp`
    False narrows scratch to the cwd's `.claude/tmp/` alone.

    Two places qualify: the working directory's own `.claude/tmp/`, which `debugging.md` names as
    where temporary files belong, and Claude Code's own session directory under an OS temporary
    directory. The rest of `/tmp` and `/var/folders` is deliberately left out, so `> /tmp/out.txt`
    keeps prompting the way `running-commands.md` says it does; those directories hold other
    programs' files, and nothing in this workflow writes there.

    Containment here resolves the FULL path, final component included, which is the opposite of
    what the rm and mv gates do. `rm link` deletes the link, but `> link` truncates whatever the
    link points at, so a symlink sitting in scratch would otherwise carry the write anywhere on
    the machine. A `~`, a `$`, a backtick, or a glob character in either path is refused outright,
    because bash rewrites each of them after this hook has read the command.

    The path is never normalized before it's resolved, because the kernel follows `link/..` to
    the link target's parent while `normpath` would collapse it as text. A file with more than one
    hard link is refused too, since truncating it empties every other name for the same inode.
    """
    if not target:
        return False
    for path in (target, resolve_from or ''):
        if (path.startswith('~') or os.sep + '~' in path or expands_after_this_hook(path)
                or any(char in path for char in GLOB_CHARS)):
            return False

    absolute = os.path.join(resolve_from or cwd, target.rstrip(os.sep) or target)
    if os.path.basename(absolute) in ('', '.', '..'):
        return False
    if os.path.lexists(absolute):
        resolved = os.path.realpath(absolute)
        try:
            if os.path.isfile(resolved) and os.stat(resolved).st_nlink > 1:
                return False
        except OSError:
            return False
    else:
        resolved = os.path.join(os.path.realpath(os.path.dirname(absolute)),
                                os.path.basename(absolute))

    scratch_root = os.path.join(os.path.realpath(cwd), '.claude', 'tmp')
    if resolved == scratch_root or resolved.startswith(scratch_root + os.sep):
        return True
    return include_agent_temp and is_agent_temp_path(resolved)


def strip_scratch_redirects(command, cwd):
    """Remove the output redirects that can only write scratch, leaving the rest of the line.

    Cutting them before the operator guard runs is what lets `git diff > .claude/tmp/x.patch` be
    judged as the bare `git diff`, the same way a `/dev/null` redirect already is. The line comes
    back unchanged whenever anything is unclear, so the guard still sees every redirect it would
    have seen before.

    Stripping is all or nothing: `cmd > a > b` truncates both files, so a single destination
    outside scratch leaves the whole line for the guard to prompt on. Cutting happens before the
    guard rather than after a verdict, because `first_operator` stops at what it finds first --
    forgiving a redirect in place would leave a `;` further along the line unexamined.
    """
    redirects = shell_line_shapes.output_redirects(command)
    if not redirects:
        return command

    for _start, _end, target in redirects:
        if not is_scratch_destination(target, cwd):
            return command

    for start, end, _target in reversed(redirects):
        command = command[:start] + ' ' + command[end:]
    return command


def strip_command_prefix(tokens):
    """Drop a leading `command` builtin, which CLAUDE.md uses to bypass aliases."""
    if tokens and tokens[0] == 'command':
        return tokens[1:]
    return tokens


def git_globals_and_subcommand(tokens):
    """Split `git [globals] <subcommand> ...` into (globals, subcommand, subcommand index)."""
    globals_used = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith('-'):
            return globals_used, token, index
        globals_used.append(token)
        index += 2 if token in GIT_GLOBAL_FLAGS_TAKING_A_VALUE else 1
    return globals_used, None, None


def is_read_only_git_subcommand(tokens, subcommand_index):
    """True if the tokens from the subcommand onward start with a GIT_READ_ONLY_SUBCOMMANDS entry."""
    if subcommand_index is None:
        return False
    return any(
        tuple(tokens[subcommand_index:subcommand_index + len(entry)]) == entry
        for entry in GIT_READ_ONLY_SUBCOMMANDS
    )


def is_long_option(argument, option):
    """True if the argument spells `option`, or an abbreviation git accepts, with or without `=value`.

    Git's parser takes any unambiguous prefix of a long option, so `--open=vim` is
    `--open-files-in-pager=vim`. A prefix short enough to be ambiguous also matches
    here; git would reject it, so asking costs nothing.
    """
    name = argument.split('=', 1)[0]
    return len(name) > 2 and name.startswith('--') and option.startswith(name)


def git_read_only_option_reason(subcommand, arguments, cwd, git_cwd):
    """Why an argument makes a read-only git subcommand run a program or write a file, or None.

    `--output` is the one option here that names a file rather than a program, so it is the one
    that can be cleared by where the file lands. A destination inside scratch gets the same grant
    a `> .claude/tmp/x` redirect gets, since git writing the patch itself and bash writing it are
    the same act. `cwd` is the session's working directory, which owns scratch; `git_cwd` is
    git's, which a `-C` ahead of the subcommand moves and which a relative `--output` lands in.
    """
    for index, argument in enumerate(arguments):
        if is_long_option(argument, '--output'):
            if '=' in argument:
                destination = argument.split('=', 1)[1]
            else:
                destination = arguments[index + 1] if index + 1 < len(arguments) else ''
            if is_scratch_destination(destination, cwd, resolve_from=git_cwd):
                continue
            return f'`{argument}` makes git {subcommand} write a file'
        if subcommand == 'grep' and (
            is_long_option(argument, '--open-files-in-pager')
            or GIT_GREP_PAGER_CLUSTER.match(argument)
        ):
            return f'`{argument}` makes git grep run a program on the matching files'
        if subcommand == 'fetch':
            if is_long_option(argument, '--upload-pack'):
                return f'`{argument}` names a program for git fetch to run'
            if not argument.startswith('-') and not GIT_REMOTE_NAME.fullmatch(argument):
                return (f'`{argument}` is not a plain remote name, and a URL, path, or '
                        '`ext::` helper can make git fetch run a program')
    return None


# The options a `git add` or `git commit` outside a worktree may carry and still be judged by its
# pathspecs alone. It's a list of what is known to be safe rather than of what sweeps the tree,
# because git accepts clusters (`-Av`), abbreviations (`--al`), and `--pathspec-from-file`, and an
# enumeration of the dangerous spellings missed each of them. Anything off the list asks.
GIT_STAGING_SAFE_OPTIONS = {
    'add': {
        'short': frozenset('vfnNAu'),
        'short_taking_a_value': frozenset(),
        'long': frozenset({
            '--verbose', '--force', '--dry-run', '--intent-to-add', '--all', '--update',
        }),
        'long_taking_a_value': frozenset(),
    },
    'commit': {
        # `-n` is `--no-verify` here, so it is left off; skipping the hooks is worth a prompt.
        'short': frozenset('qvs'),
        'short_taking_a_value': frozenset('mFS'),
        'long': frozenset({
            '--amend', '--no-edit', '--allow-empty', '--allow-empty-message', '--signoff',
            '--no-signoff', '--quiet', '--verbose', '--gpg-sign', '--no-gpg-sign',
        }),
        'long_taking_a_value': frozenset({
            '--message', '--file', '--author', '--date', '--cleanup', '--trailer',
        }),
    },
}

# Subcommands that send commits or patches off this machine, or serve the repository to others.
# `send-pack` and `http-push` are the plumbing under `push`, `subtree push` runs `push` itself,
# and the rest publish to email, Subversion, Perforce, LFS, or anyone who connects to `daemon`.
GIT_PUSHING_SUBCOMMANDS = frozenset({
    'push', 'send-pack', 'http-push', 'subtree', 'send-email', 'imap-send', 'svn', 'p4', 'lfs',
    'daemon', 'instaweb',
})

# Subcommands that settings.json denies or asks about by prefix, like `Bash(git clean*)`. A `-C`
# ahead of the subcommand, or a leading `command`, defeats every one of those prefixes, so the hook
# asks on their behalf.
GIT_SUBCOMMANDS_GATED_BY_SETTINGS = frozenset({
    'branch', 'checkout', 'cherry-pick', 'clean', 'config', 'filter-branch', 'filter-repo',
    'merge', 'pull', 'rebase', 'reset', 'restore', 'stash', 'submodule', 'switch', 'tag',
    'update-ref', 'worktree',
})

# `-S` takes its key id attached or not at all, so it never consumes the next token.
GIT_COMMIT_ATTACHED_ONLY_VALUE = frozenset('S')

# `git add` options that stage the whole tree when no pathspec follows, and only the named paths
# (deletions included) when one does.
GIT_ADD_WHOLE_TREE_WITHOUT_PATHSPEC = frozenset({'-A', '-u', '--all', '--update'})


def unsafe_staging_reason(subcommand, arguments, git_cwd):
    """Why this `git add` or `git commit` might take more than the files it names, or None.

    Outside a worktree the main checkout holds other sessions' uncommitted work, so staging the
    whole tree would sweep it into this commit. The command passes only when every option is on
    GIT_STAGING_SAFE_OPTIONS and every pathspec is a literal path strictly below the repository
    root. A glob, a `:` pathspec magic, or a path that resolves to the root or above could each
    cover the whole tree, and a leading `~` expands after this hook has read it.
    """
    safe = GIT_STAGING_SAFE_OPTIONS[subcommand]
    pathspecs = []
    whole_tree_flag = None
    skip_next = False
    for position, argument in enumerate(arguments):
        if skip_next:
            skip_next = False
            continue
        if argument == '--':
            pathspecs.extend(arguments[position + 1:])
            break
        if argument.startswith('--'):
            name = argument.split('=', 1)[0]
            if name in safe['long_taking_a_value']:
                skip_next = '=' not in argument
            elif argument not in safe['long'] and not (
                    name == '--gpg-sign' and subcommand == 'commit'):
                return f'`{argument}` is not an option this hook can vouch for'
            if subcommand == 'add' and argument in GIT_ADD_WHOLE_TREE_WITHOUT_PATHSPEC:
                whole_tree_flag = argument
            continue
        if argument.startswith('-') and len(argument) > 1:
            for index, letter in enumerate(argument[1:]):
                if letter in safe['short_taking_a_value']:
                    at_end = index == len(argument) - 2
                    skip_next = at_end and letter not in GIT_COMMIT_ATTACHED_ONLY_VALUE
                    break
                if letter not in safe['short']:
                    return f'`-{letter}` in `{argument}` is not an option this hook can vouch for'
                if subcommand == 'add' and f'-{letter}' in GIT_ADD_WHOLE_TREE_WITHOUT_PATHSPEC:
                    whole_tree_flag = f'-{letter}'
            continue
        pathspecs.append(argument)

    if not pathspecs:
        if whole_tree_flag:
            return f'`{whole_tree_flag}` with no pathspec stages every change in the tree'
        return None

    toplevel = git_toplevel(git_cwd)
    if not toplevel:
        return 'Could not find the repository root to check the pathspecs against'
    for pathspec in pathspecs:
        if not pathspec or pathspec.startswith((':', '~')) or any(c in pathspec for c in '*?[\\'):
            return f'`{pathspec}` is not a plain path, so it could cover the whole tree'
        resolved = os.path.realpath(os.path.join(git_cwd, pathspec))
        if not resolved.startswith(toplevel + os.sep):
            return f'`{pathspec}` resolves to the repository root or outside it'
        # A directory deleted from disk still has entries in the index, and staging it stages the
        # removal of every tracked file under it, so the index is checked as well as the disk.
        if os.path.isdir(resolved) or git_output(git_cwd, 'ls-files', '--', pathspec.rstrip('/') + '/'):
            return f'`{pathspec}` is a directory, so it takes every change under it'
    return None


def git_effective_cwd(tokens, subcommand_index, cwd):
    """The directory git runs in: the hook's cwd, moved by a `-C <path>` ahead of the subcommand.

    The path is resolved rather than normalized, because git's chdir follows `link/..` to the link
    target's parent, where `normpath` would collapse it as text.
    """
    for index in range(1, subcommand_index):
        if tokens[index] == '-C' and index + 1 < subcommand_index:
            return os.path.realpath(os.path.join(cwd, tokens[index + 1]))
    return cwd


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


def git_diff_no_index_reason(tokens, subcommand_index, cwd):
    """Why this `git diff` would compare files on disk rather than repository content, or None.

    `--no-index` says so outright, but git also switches to that mode on its own whenever exactly
    two operands are given and either one lies outside the working tree -- a `--` doesn't stop
    it, so `git diff -- /etc/hosts /etc/passwd` prints both files in full. Compared that way, git
    is a file reader with no connection to the repository, so it doesn't earn the read-only
    allow; the prompt puts it on the same footing as any other command that reads an arbitrary
    path. Revisions and pathspecs both resolve inside the working tree, which is what keeps
    `git diff HEAD~1 HEAD` on the allow side.
    """
    operands = []
    end_of_options = False
    for argument in tokens[subcommand_index + 1:]:
        if end_of_options:
            operands.append(argument)
        elif argument == '--':
            end_of_options = True
        elif is_long_option(argument, '--no-index'):
            return f'`{argument}` makes git diff compare files on disk rather than the repository'
        elif not argument.startswith('-'):
            operands.append(argument)

    if len(operands) != 2:
        return None

    git_cwd = git_effective_cwd(tokens, subcommand_index, cwd)
    toplevel = git_toplevel(git_cwd)
    for operand in operands:
        if expands_after_this_hook(operand):
            return f'`{operand}` expands after this hook reads it, so its target cannot be checked'
        if toplevel is None:
            # Outside any repository every two-operand diff is a no-index one, but a
            # revision-looking operand here is most likely a `-C` aimed at a path this machine
            # doesn't have, so only an operand that plainly names a filesystem location counts.
            outside = os.path.isabs(operand) or os.path.normpath(operand).startswith('..')
        else:
            outside = not is_inside(operand, toplevel, git_cwd)
        if outside:
            return f'`{operand}` is outside the repository, so git diff would read it from disk'
    return None


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
    resolved = resolve_all_but_final(operand, cwd)
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
        if all(is_cwd_claude_tmp_path(operand, cwd) for operand in operands):
            return None
        return 'ask', 'An operand leaves .claude/tmp/ through a symlink; confirm this rm'

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


def decide_mv_into_scratch(flags, operands, cwd):
    """Decide an `mv` whose destination is this working directory's own `.claude/tmp/`.

    Sweeping a scratch file into the project's scratch directory is sanctioned
    cleanup, but `mv` deletes the source, so an unrestricted grant would let any
    file on the machine be displaced into scratch with no prompt. Restricting
    the SOURCES to what an agent produced is what separates cleanup from
    displacement; the destination needs no further check, since it has already
    been established to be inside this directory's scratch. The flag whitelist
    still applies, because GNU `-t` names the destination as a flag value and
    would leave the real destination somewhere this gate never examined.
    """
    for flag in flags:
        if not re.fullmatch(r'-[finv]+', flag):
            return 'ask', f'`{flag}` changes how mv picks its destination; confirm this mv'

    if len(operands) < 2:
        return 'ask', 'This mv has no source and destination to check; confirm it'

    for source in operands[:-1]:
        if expands_after_this_hook(source):
            return 'ask', f'`{source}` expands to a path this hook cannot see; confirm this mv'
        matches = expand_globs(source, cwd)
        if not matches:
            return 'ask', f'`{source}` matches nothing here; confirm this mv'
        for match in matches:
            if not is_agent_scratch_source(match, cwd):
                return 'ask', (f'`{match}` is neither under an OS temp directory nor an '
                               'untracked file in this directory, so this mv would displace '
                               'it rather than sweep up scratch; confirm it')

    return 'allow', "mv of agent scratch into this directory's own .claude/tmp/"


def decide_mv(tokens, cwd):
    """Allow mv when everything it touches stays inside a sanctioned worktree and
    nothing unrecoverable gets overwritten.

    Returns (decision, reason), or None to stay silent and leave the decision
    to settings.json rules.
    """
    flags, operands = rm_flags_and_operands(tokens)

    if operands and (is_relative_claude_tmp_path(operands[-1])
                     or sweeps_into_cwd_scratch(operands[-1:], cwd)):
        if any(char in operands[-1] for char in GLOB_CHARS):
            return 'ask', f'`{operands[-1]}` is a glob destination; confirm this mv'
        # `mv` renames over a file symlink or a hard link rather than writing through it, so only
        # a destination that resolves to a directory needs following to see where it lands.
        dest_real = os.path.realpath(os.path.join(cwd, operands[-1]))
        if os.path.isdir(dest_real):
            lands_in_scratch = is_cwd_scratch_write_destination(dest_real, cwd)
        else:
            lands_in_scratch = is_cwd_claude_tmp_path(operands[-1], cwd)
        if not lands_in_scratch:
            return 'ask', SCRATCH_DESTINATION_ESCAPES.format(operand=operands[-1], command='mv')
        return decide_mv_into_scratch(flags, operands, cwd)

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


def cp_into_scratch_reason(flags, operands, cwd):
    """Why a cp aimed at this directory's `.claude/tmp/` could write outside it, or None.

    cp writes through a symlink or hard link at the name it lands on, so when the destination is
    a directory, each source's landing is checked as well as the destination itself. The flag
    whitelist keeps out GNU `-t`, which names the real destination as a flag value.
    """
    for flag in flags:
        if not re.fullmatch(r'-[RrfinvpXcLPH]+', flag):
            return f'`{flag}` is not a cp flag this gate reasons about; confirm this cp'
    recursive = any(char in 'Rr' for flag in flags for char in flag[1:])

    dest = operands[-1]
    if not is_cwd_scratch_write_destination(dest, cwd):
        return SCRATCH_DESTINATION_ESCAPES.format(operand=dest, command='cp')

    dest_real = os.path.realpath(os.path.join(cwd, dest))
    if not os.path.isdir(dest_real):
        return None
    for source in operands[:-1]:
        if expands_after_this_hook(source):
            return f'`{source}` expands to a path this hook cannot see; confirm this cp'
        for match in expand_globs(source, cwd) or [source]:
            if recursive and (match.endswith(os.sep) or os.path.basename(match) in ('.', '..')):
                return (f'`{match}` copies its contents rather than itself, so where each file '
                        'lands cannot be checked; confirm this cp')
            name = os.path.basename(os.path.normpath(os.path.join(cwd, match)))
            landing = os.path.join(dest_real, name)
            if not os.path.lexists(landing):
                continue
            if recursive:
                return (f'`{landing}` already exists, and a recursive copy writes through any '
                        'link inside it; confirm this cp')
            if not is_cwd_scratch_write_destination(landing, cwd):
                return SCRATCH_DESTINATION_ESCAPES.format(operand=landing, command='cp')
    return None


def decide_cp(tokens, cwd):
    """Allow cp when everything it names stays inside a sanctioned worktree and
    nothing unrecoverable gets overwritten.

    Returns (decision, reason), or None to stay silent and leave the decision
    to settings.json rules.
    """
    flags, operands = rm_flags_and_operands(tokens)

    # A link in scratch shares its target's inode, so a later write that scratch grants for free
    # would land in the original file.
    for flag in flags:
        if is_long_option(flag, '--link') or is_long_option(flag, '--symbolic-link') or (
            not flag.startswith('--') and any(char in 'ls' for char in flag[1:])
        ):
            return 'ask', f'`{flag}` makes cp create links rather than copies; confirm it'

    if operands and (is_relative_claude_tmp_path(operands[-1])
                     or sweeps_into_cwd_scratch(operands[-1:], cwd)):
        reason = cp_into_scratch_reason(flags, operands, cwd)
        if reason:
            return 'ask', reason
        if is_relative_claude_tmp_path(operands[-1]):
            return None
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

    # `head`, `tail`, and `wc` can only trim what the gated command already printed, so a
    # pipeline ending in one is judged as the command that feeds it. Stripping the tail before
    # anything else keeps that pipe from reading as a chain, and keeps it out of the token list.
    command = shell_line_shapes.strip_output_limiting_tail(command)

    if is_gated_command(command):
        # A redirect that can only write scratch comes off here, so the rest of the line is judged
        # on its own. Removing it first, rather than forgiving it in the verdict, is what keeps a
        # chaining operator further along the line from going unexamined.
        command = strip_scratch_redirects(command, cwd)
        decision = shell_operator_decision(command)
        if decision:
            emit(*decision)
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

    # The guard above has confirmed every redirect left in the line targets `/dev/null` or a file
    # descriptor. Bash consumes a redirection before the command sees its argv, so dropping them
    # here is what leaves the tokens the command is actually run with; leaving `2>&1` in would
    # hand `git fetch` a phantom operand that reads as a suspicious remote name.
    command_for_tokens = shell_line_shapes.STRIP_REDIRECT.sub(' ', command)
    try:
        raw_tokens = shlex.split(command_for_tokens)
        tokens = strip_command_prefix(raw_tokens)
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
        git_globals, subcommand, subcommand_index = git_globals_and_subcommand(tokens)
        if subcommand is None:
            return
        # A global other than one `-C` can aim git at another repository (`--git-dir`), change what
        # it runs (`-c core.pager=...`), or turn any name into any subcommand (`-c alias.x=push`),
        # so no verdict below can be trusted once one is present, whatever the subcommand.
        if git_globals and git_globals != ['-C']:
            extra = [flag for flag in git_globals if flag != '-C'] or ['-C']
            emit('ask', f'`{extra[0]}` ahead of the subcommand can aim git elsewhere or change '
                        f'what git {subcommand} runs; confirm it')
            return
        git_cwd = git_effective_cwd(tokens, subcommand_index, cwd)
        if is_read_only_git_subcommand(tokens, subcommand_index):
            option_reason = git_read_only_option_reason(
                subcommand, tokens[subcommand_index + 1:], cwd, git_cwd,
            )
            if not option_reason and subcommand == 'diff':
                option_reason = git_diff_no_index_reason(tokens, subcommand_index, cwd)
            if option_reason:
                emit('ask', f'{option_reason}; confirm it')
            else:
                emit('allow', f'git {subcommand} with no program-running or file-writing option; '
                              'auto-approved')
            return
        if subcommand in GIT_PUSHING_SUBCOMMANDS:
            emit('ask', f'git {subcommand} can send commits off this machine; confirm it')
            return
        hidden_by = '-C' if git_globals else ('command' if raw_tokens[0] == 'command' else None)
        if hidden_by and subcommand in GIT_SUBCOMMANDS_GATED_BY_SETTINGS:
            emit('ask', f'`{hidden_by}` hides this git {subcommand} from the settings.json rules '
                        'that gate it; confirm it')
            return
        if subcommand not in ('add', 'commit'):
            # An alias can expand to anything, `push` or `add -A` included, and nothing on the line
            # says which. Git ignores an alias that shadows a builtin, so the lookup only matters for
            # names like these, which are the ones this hook would otherwise stay silent on.
            if git_output(git_cwd, 'config', '--get', f'alias.{subcommand}'):
                emit('ask', f'`git {subcommand}` is an alias, so this hook cannot tell what it runs; '
                            'confirm it')
            return
        if sanctioned_worktree_root(git_cwd):
            emit('allow', f'Inside a .claude/worktrees/ worktree; git {subcommand} auto-approved')
            return
        reason = unsafe_staging_reason(subcommand, tokens[subcommand_index + 1:], git_cwd)
        if reason:
            emit('ask', f"{reason}. Outside a worktree that can sweep in other sessions' work; "
                        f'name the files instead, or confirm this git {subcommand}')
        # Anywhere else stays silent, so the autoMode `soft_deny` rule in settings.json decides
        # whether the user actually asked for this staging or commit.


if __name__ == '__main__':
    main()
