---
name: relay-merge-sync
description: "Merges the trunk into feature branches in a Relay repo: resolves the Relay doc conflicts, commits the merge, pulls and publishes Relay Cloud, commits the sync state, and pushes. Given GitHub PR or GitLab MR numbers, it does that for each one in order and then merges it."
when_to_use: "Use when the user is merging a series of PRs or MRs, or updating a branch, in a repo with `.relay/` and `requirements/`. With no PR numbers, it finishes the merge already in progress on the current branch. Invoking this skill is the user's request to commit and push those branches, and, when PR numbers are given, to merge every one of them, but nothing else."
---

With no arguments, run steps 1-5 on the merge already in progress on the current branch. With a list of PR or MR numbers, follow **Batch mode** at the bottom, which wraps steps 1-5 around each one.

Run every step from the repo root, because `relay-site` looks for its project slug in the current directory and fails with "No project slug found" anywhere else. `git add`, `git commit`, `git push`, and `relay-site` all need `dangerouslyDisableSandbox: true` on the first attempt: the sandbox can't write `.git/index.lock`, reach the SSH agent for signing, or reach Relay Cloud.


## 1. Resolve the merge conflicts

Read `.git/MERGE_MSG` for the branch names and the conflicted files, then `git diff` for the hunks.

If any conflicted file is outside `.relay/` and `requirements/`, stop and tell the user which ones. Those conflicts are code and need a decision, so this skill doesn't resolve them.

The Relay conflicts are almost always the derived files that every PR rewrites: `requirements/index.md`, the domain and epic `index.md` files, `.relay/STATUS.md`, `.relay/planning/STATE.md`, and the `status` counters in `.relay/config.json`. Neither side is right on its own, because each side only knows about its own PRDs. Resolve them this way:

- Take the union of the facts. If one side added a PRD and the other side verified a different one, the result keeps both.

- Where both sides describe the same PRD, keep the more advanced state. Verified beats pending, and implemented beats planned.

- Recompute every count from the merged tree instead of picking a side's number. List the PRDs with `command rg -l "^status:" requirements --glob "*.prd.md"` and read each one's `status:` frontmatter.

- Keep the later `Last activity` date in `STATE.md`, and fold the other side's status into the `Status` line.

- Never take the merge base (`|||||||`) section. It's always the oldest state.

After editing, confirm `jq -e . .relay/config.json` parses and that `command rg -n "^(<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)" .relay requirements` finds nothing.


## 2. Commit the merge

Stage the resolved files by name, then run `git commit --no-edit` to keep git's merge message.

Skip the pre-commit code review and security review when every conflict was in Relay docs. The merged code was already reviewed in its own PR, and the docs carry no security risk. If step 1 stopped for code conflicts and the user resolved them, run both reviews over those hunks before committing.


## 3. Pull Relay Cloud

Run `relay-site pull`. When it reports incoming changes, check `git status` for conflicts and resolve them by the rules in step 1. Then stage the pulled files plus `requirements/.sync-state.json` by name and commit them with `docs: pull relay cloud changes`, followed by one sentence naming what came in. Skip the commit when the pull says the working copy is already in sync.


## 4. Publish

Run `relay-site publish`. When it changes `requirements/.sync-state.json`, commit that file with `docs: record relay sync state after publish`.

`publish` also rewrites `.relay/config.json` with the `domains` keys in a different order. Read the diff, and if it only moves keys, leave it uncommitted and mention it in one line. If it changes any value, tell the user.


## 5. Push

Run `git push`. Report the branch, and anything the user has to act on: code conflicts, a `config.json` value change, or a failed command with its output.


## Batch mode

The user's list of numbers is their approval to merge every PR in it, so don't confirm each merge. Don't wait for CI either. The checks have almost always passed already, and the user chose not to block on them.

Work through the list in the order given, because each merge changes the trunk that the next PR has to absorb. Stop the whole batch at the first PR that hits any of these, and report which PRs merged and which didn't:

- A conflict in any file outside `.relay/` and `requirements/`. Leave the merge in progress so the user can resolve it, then run this skill again with the PRs that are left.

- A PR that is closed, already merged, or a draft.

- Any command that fails. Report its full output.

Before the first PR, run `git status`. If the working tree has uncommitted changes, stop and tell the user. Checking out other branches would carry another session's work along with it, or refuse to switch.

Use `gh` when `git remote get-url origin` points at GitHub, and `glab` when it points at GitLab. `gh` and `glab` need `dangerouslyDisableSandbox: true` to reach the network.

For each PR:

1. Read the PR's head and base branches and its state, with `gh pr view <number> --json headRefName,baseRefName,state,isDraft` or `glab mr view <number> -F json`. In GitLab's JSON those fields are `source_branch`, `target_branch`, `state`, and `draft`.

2. Run `git fetch origin`, `git checkout <head>`, then `git merge --ff-only origin/<head>`, so the local branch has every commit already pushed to it.

3. Run `git merge --no-edit origin/<base>`. When it merges cleanly, git makes the merge commit itself, so skip ahead to step 3 of the main procedure. Otherwise do steps 1 and 2 of the main procedure.

4. Do steps 3-5 of the main procedure: pull Relay Cloud, publish, and push. Then, if `.relay/config.json` is still modified and its diff only moves keys, run `git restore .relay/config.json`, because the next `git checkout` refuses to switch with it dirty, and the next `publish` reorders it again anyway. The clean-tree check before the first PR guarantees that reorder is the only change in it. If the diff changes any value, stop the batch and tell the user.

5. Merge the PR with a merge commit: `gh pr merge <number> --merge` or `glab mr merge <number> --yes`. Don't pass a delete-branch flag. GitLab chooses the merge method from the project settings, so if the project is set to squash or fast-forward, stop before the first merge and tell the user.

Once the list is done, run `git fetch origin`, check out the base branch, and run `git merge --ff-only origin/<base>`, so the local trunk includes everything that was just merged. Report the merged PR numbers in one line.
