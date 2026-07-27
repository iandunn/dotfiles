#!/usr/bin/env python3
"""
PreToolUse permission gate for `cp`, `npm install`, and `git worktree remove`.

Two independent gates, each keyed on what actually makes the command safe:

`cp` / `npm install` -- auto-approved when the session's working directory is a
LINKED git worktree, and prompted ("ask") everywhere else: the main working
tree, a non-repo directory, or when git can't be queried.

Rationale: per CLAUDE.md, file-mutating work belongs in an isolated worktree,
never the shared main checkout. This removes the permission prompt for these
two commands inside a worktree while keeping the prompt on the main checkout,
so the friction nudges work off the shared tree.

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
were removed from settings.json's permissions.ask and permissions.deny lists,
because settings rules are evaluated regardless of hook output and would
override the hook's "allow" (see the "Hook decisions don't bypass permission
rules" note in the Claude Code permissions docs). Emitting "ask" here
reproduces the previous prompt behavior independent of the active permission
mode.

Note that the hardcoded bash checks in Claude Code (`cd-git-compound`,
`multi-cd`, `shell-operators`) carry decisionReason type "other", which is NOT
re-escalated after a hook allow -- only "rule", "safetyCheck", and
"sandboxOverride" are. A hook "allow" therefore does clear those three.

A linked worktree is detected by comparing `git rev-parse --git-dir` against
`--git-common-dir`: they resolve to the same path in the main working tree and
differ in a linked worktree (git-dir is <common-dir>/worktrees/<name>).

The settings.json `if` filters already scope this hook to the commands above,
but each command is re-checked here as defense in depth: without that guard, a
hook wired without the filter would gate *every* Bash command.
"""
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


def is_worktree_gated_command(command):
    stripped = command.strip()
    if stripped == 'cp' or stripped.startswith('cp '):
        return True
    if stripped == 'npm install' or stripped.startswith('npm install'):
        return True
    if stripped == 'npm i' or stripped.startswith('npm i '):
        return True
    return False


def is_worktree_remove(command):
    return re.match(r'^git\s+worktree\s+remove\b', command.strip()) is not None


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


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')

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

    if not is_worktree_gated_command(command):
        return

    cwd = data.get('cwd') or os.getcwd()
    if is_linked_worktree(cwd):
        emit('allow', 'Inside a linked git worktree (not the main checkout); cp/npm install auto-approved')
    else:
        emit('ask', 'On the main working tree (or outside a worktree); confirm this cp/npm install')


if __name__ == '__main__':
    main()
