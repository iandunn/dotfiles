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

`git diff` from the worktree branch, then `git apply` in the main tree. Committing on the worktree branch is fine; advancing main is not.

`git apply` fails safe: it refuses rather than clobbering an existing untracked file, and leaves what it applies unstaged.

After applying, kill any artifacts the session left running -- `npm dev` services, Chrome MCP, etc.

When writing the end-of-session summary, prepend a one-sentence overview of the session's main goal.

## Cleanup

Clear the worktree when done. User's standing request in `CLAUDE.md` covers this, so don't ask.

- Created by `EnterWorktree`: use `ExitWorktree` with `action: "remove"`. It refuses to delete uncommitted or unmerged work unless you pass `discard_changes`. If it refuses, tell the user what it found instead of overriding it.
- Created by `git worktree add`: `ExitWorktree` won't touch it. Use `git worktree remove`, without `--force`.
