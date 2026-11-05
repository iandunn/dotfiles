---
name: relay-workflow
description: "How to run Relay's PRD commands on a ticket, walk the user through the stages, and handle Relay's own commit phases."
when_to_use: "Use in any repo with a `.relay/` directory and `requirements/`, before planning or implementing a ticket, and before running any `/relay-eng:` command. Follow all of it; the commit-phase rules are easy to get wrong."
---

If the project has Relay set up (a `.relay/` directory plus `requirements/`), then use its workflow and commands on every ticket and make sure its docs stay up to date as you plan and implement tasks.

Relay runs a feature through five stages, and each one has a command:

| Stage | Command |
|---|---|
| Define the feature | `/relay-eng:add-prd` |
| Refine the feature | `/relay-eng:refine-prd` |
| Approve the feature | `/relay-eng:approve-prd` |
| Execute the feature | `/relay-eng:execute-prd` |
| Validate the feature | `/relay-eng:verify-prd` |

I'm still learning that flow and I don't intend to memorize it, so walk me through it as we go. Name the stage we're on in those words, say what the command is about to do, and tell me which stage comes next once it finishes. Spending words on that is worth it even where the rest of my rules are pushing you to be brief.

For a ticket-sized fix, stay at the PRD level and pick the entry point from what already exists. If no PRD covers the code, run `/relay-eng:add-prd` into the epic that `path_routing` in `.relay/config.json` maps the files to. When `add-prd`'s research finds an existing implementation it replaces its interview with a confirm-me pass seeded from the code, so answer that pass from the ticket and the code and only bring me the questions neither can answer. If a PRD exists but doesn't cover what this ticket changes, run `/relay-eng:refine-prd` first. Then run `/relay-eng:approve-prd` when it's still a draft, then `/relay-eng:execute-prd` (it enters delta mode on its own when the PRD is `implemented`), then `/relay-eng:verify-prd`. Skip `execute-epic`, `verify-epic`, `sync-docs`, and `ship` unless I ask for them.


## Commit phases

Relay's commands commit their own doc changes (`add-prd`, `approve-prd`, `execute-prd`, `verify-prd`, `sync-docs`). Before a Relay commit phase, check the current branch. If it's the main branch (`main`, `trunk`, `master`, etc), create a ticket branch per `running-commands.md` and switch to it first, because a Relay commit never goes on the main branch. Those commits are sanctioned and are an exception to the "don't commit unless I ask" rule in `CLAUDE.md`, so never skip a commit phase. The commands spell the message as `-m "$(cat <<'EOF' ... EOF)"`, and the permission hook prompts on that shape everywhere, worktree included, because `$` expands inside double quotes; rewrite it as a single-quoted message per `running-commands.md`, which auto-approves in a worktree. Outside a worktree, replace a Relay command's `git add -A` with explicit paths: the files you changed in this session, plus any Relay docs under `.relay/` and `requirements/` that are modified, deleted, or new, even when another session or I edited them. List those with `git -C <repo root> status --porcelain --untracked-files=all -- .relay requirements`, which names each file inside a new folder rather than the folder and auto-approves where `ls-files` would prompt, and stage the path after each status code with `git -C <repo root> add`, since the paths are relative to the root. Name each file on the `git add` line, never a directory like `requirements` or `requirements/notebooks`. The hook prompts on whole-tree and directory staging outside a worktree, so `-A` or a directory would stop for approval, while the named-file form goes to the auto-mode classifier, which treats a Relay commit phase as one I asked for.


## During a parallel plan

During a `parallel plan`, every Relay command before `go` runs inside the worktree, so create the worktree before the first one rather than after planning. `execute-prd` and `verify-prd` are the ones that make this mandatory: both stage with `git add -A`, which in the main checkout would sweep other sessions' uncommitted work into your commit. After `go`, Relay commands run in the main checkout, and their commit phases fold into the code commit I ask for instead of making a commit of their own. The `go` patch already carries Relay doc changes, so a Relay-only commit would record the feature as implemented without its code. Expect `.relay/config.json`, `.relay/STATUS.md`, `.relay/planning/STATE.md`, and the `requirements/` index files to be where the `go` patch collides, because every session rewrites them, and the counters in `config.json` have no regenerator (`sync-docs` rebuilds `STATUS.md` and the stakeholder docs, not those). Resolve any merge conflicts you run into. `execute-prd` also backfills its commit hash into `.relay/epics/*/EXECUTION-*.json`; after `go` and cleanup that hash points at a deleted worktree branch, so tell me it's stale rather than fixing it up.
