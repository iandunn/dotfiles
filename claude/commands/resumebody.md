---
description: Find a past session by what was said in it, not just by its title
argument-hint: [query - no quotes or special characters]
allowed-tools: Bash(bash /Users/iandunn/dotfiles/claude/bin/claude-session-search.sh:*), Bash(jq:*), Read
---

<resumebody-instructions>

Everything below is injected into the transcript as one user block on every run, which would otherwise make each search match all previous searches. `claude-session-search.sh` skips blocks starting with the line above, so keep it first. It filters that block only, not the session -- other work done in this session stays findable.

# Find a past session by its contents

`/resume` only matches a session's title, git branch, tag, and PR number, so a conversation that changed topic after its title was generated is invisible to it. This searches what was actually typed.

Search term: `$ARGUMENTS`

## Step 1: check the term before running anything

The term is passed to a shell, so validate it first. Allowed characters are letters, digits, spaces, and `- _ . /` only.

If it contains anything else -- quotes, backticks, `$`, `;`, `|`, `&`, `<`, `>`, parentheses, or a backslash -- **stop**. Run nothing. Tell the user those characters can't be used in a search term, name the ones you found, and suggest a plain-text term instead. Do not try to escape or strip them.

## Step 2: run the search

```
bash /Users/iandunn/dotfiles/claude/bin/claude-session-search.sh '<term>'
```

Scoped to the current project by default. Add `--all-projects` only when the user asks for it, and `--limit 0` when they ask to see the rest.

With no term at all, run it with no argument to list the most recent sessions in this project.

## Step 3: report the results as separate paragraphs

One entry per session, in the order the script returned them, separated by a blank line:

```
[2026-08-05] `3a5c63d2-b1b8-4fe1-b65d-9b9bd9df6599` -- **Automate Finder window size with defaults** -- Asked why Contexts stopped responding to Option-Tab; traced it to VS Code leaking macOS secure input mode, which blocks third-party event taps.

[2026-07-22] `d0befd2e-0328-4c8b-bf9d-dd7f23c129a3` -- **(untitled)** -- Asked how to script window placement; no conclusion recorded.
```

**Do not start these lines with `-`, `*`, or `+`.** That makes them a markdown list, and the terminal renderer collapses list items to tight spacing no matter how the source is spaced -- blank lines in the source are simply discarded. Verified by reading a transcript back: the blank lines were emitted and still rendered tight. Each entry has to be its own paragraph for the gap to survive, and a paragraph can't begin with a list marker.

Rules for the sentence:

- The date is the script's `last active:` value for that session, unchanged.

- One sentence covering the general prompt and the final solution. The `asked:` lines give the question, the `answered:` lines give the resolution. Keep it under about 30 words -- a sentence that wraps to three lines defeats the point of scanning the list.

- If a session covered several separate topics, add one more sentence per topic. Nothing else.

- Use the title verbatim from the `title:` field, including `(untitled)`. Don't improve it or substitute your own.

- If the `answered:` lines don't actually show a resolution, say the session discussed it without a recorded conclusion. Don't invent one.

Do not rank the results, recommend one, or say which is most likely -- the ordering is by raw mention count and is not a relevance judgment. The user wants every plausible candidate and will choose. Don't drop a session for looking unrelated.

No preamble, no summary paragraph, no analysis afterward. The entries and the two footers below are the whole response.

## Step 4: warning and footers

If the script printed a `Warning:` line, repeat it as the first line of your response, before the list. It means the search silently widened to every project, and the user needs to know that rather than discover it from the results.

If the script printed `Showing N of M`, add:

```
M matching sessions in this project; N shown. Ask for the rest if you don't see it.
```

Then always close with one line stating the scope from the script's `Scope:` header, and that `--all-projects` will widen it -- so it's there when nothing in the list is the right session.

## If the results look wrong

Only what the user typed is searched, so a term that appeared solely in tool output, a pasted file, or a system reminder won't match. That filter is deliberate, but it means a real conversation can be missed. When nothing fits, say so plainly rather than presenting a weak match, and offer:

- a distinctive fragment of phrasing instead of a topic word

- `--all-projects`

- `~/.claude/history.jsonl`, which records every prompt across every project as `{display, sessionId, project, timestamp}` and is worth a `jq` pass when a transcript has since been trimmed

To resume one, the user runs `/resume <session-id>`, which switches in place in this terminal. Mention it once, at the end, not per bullet.
