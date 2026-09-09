---
name: parallel-plan-worktrees
description: "Mechanics of parallel-plan workflow: creating an isolated worktree with `EnterWorktree`, patching changes back to the main tree on `go`, and cleaning up afterward."
when_to_use: "Use when user says `parallel plan` (before creating the worktree) or `go` (before patching changes back). Covers mechanics only -- the guardrails that must hold even if this skill never loads live in CLAUDE.md."
---

<!-- Why this is split across two places: the guardrails in CLAUDE.md are the ones that are expensive to recover from if they aren't loaded -- clobbering the main checkout, or editing the wrong tree for an hour. CLAUDE.md is loaded every session unconditionally, so those stay there. Everything in this file is mechanics: which tool to call, which flag does what, what to clean up. Getting those wrong costs a retry, not lost work, so they can load on demand. If you edit one side, check whether the other side needs the matching change. -->

## Creating the worktree

Use the `EnterWorktree` tool, not `git worktree add`. It places the worktree under `.claude/worktrees/`, switches the session into it, and tracks it for cleanup. Being a native tool, it needs no bash approval. This is also what `superpowers:using-git-worktrees` Step 1a tells you to do; `git worktree add` is the fallback for when no native tool exists.

`EnterWorktree` takes no ref argument. It branches from `worktree.baseRef`, which is set to `head` -- the user's current local HEAD -- so the worktree starts from whatever they're working on and the `go` patch applies back cleanly.

When the work has to start from some other ref, run `git worktree add <path> <ref>` and then enter it by passing that `path` to `EnterWorktree`.

## Working in it

Run all verification (`tsc`, `lint`, `test`) from inside the worktree, and confirm the files under test actually contain the change -- `grep` for a distinctive string. A green run against the wrong tree is worse than no run.

## Patching back on `go`

1. **Commit the work on the worktree branch first.** `git diff <base>..HEAD` below only sees committed work, so an uncommitted tree produces an empty patch. It also leaves the worktree clean, so `ExitWorktree` won't later refuse to remove it.
2. **Generate the patch while still inside the worktree**, since the diff has to be taken from the worktree branch: `git diff <base>..HEAD > <patch path>`. Write it outside the worktree (the session scratchpad) so it survives the worktree being removed.
3. **Exit the worktree with `ExitWorktree` and `action: "keep"`.** That restores the session's working directory to the main checkout and leaves the branch and its commits on disk. Use `"keep"` rather than `"remove"`: until the patch lands, that branch is the only other copy of the work.
4. **`git apply <patch path>` from the restored working directory** -- a bare invocation, no `-C` and no `cd`. Run `git apply --check` first; the main tree may have advanced while the worktree was open.

Committing on the worktree branch is fine; advancing main is not.

`git apply` fails safe: it refuses rather than clobbering an existing untracked file, and leaves what it applies unstaged.

After applying, kill any artifacts the session left running -- `npm dev` services, Chrome MCP, etc.

When writing the end-of-session summary, prepend a one-sentence overview of the session's main goal.

## Cleanup

Clear the worktree when done. User's standing request in `CLAUDE.md` covers this, so don't ask.

Do it after the patch has been committed in the main checkout, not at `go` time. Branch deletion is gated on the branch's content already existing on `HEAD`, and that is only true once the commit lands; run it earlier and the gate correctly refuses. Each command runs bare, one per tool call -- chaining them re-introduces the prompt.

- Created by `EnterWorktree`, still inside it: use `ExitWorktree` with `action: "remove"`. It refuses to delete uncommitted or unmerged work unless you pass `discard_changes`. If it refuses, tell the user what it found instead of overriding it.

- Created by `EnterWorktree`, already exited with `action: "keep"` -- which is every worktree that has been patched back on `go`: `ExitWorktree` is a no-op now, so remove it with `git worktree remove <path>` followed by `git branch -D <branch>`. The branch needs `-D` rather than `-d` because its commits are unmerged even once the patch has landed in the main tree. `hooks/file-command-permissions.py` auto-approves that `-D` for a `worktree-*` branch after verifying every file it touched is identical on `HEAD`, so no prompt appears once the work is really in. If it does prompt, the work is not all there yet -- read the reason and tell the user rather than forcing it.

- Created by `git worktree add`: `ExitWorktree` won't touch it. Use `git worktree remove`, without `--force`.
