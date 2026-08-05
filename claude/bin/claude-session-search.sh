#!/bin/bash
#
# Search past Claude Code sessions by what was actually said in them, and print the matches for the
# /resumebody command to summarize.
#
# Claude's own `/resume` picker only matches a session's title, git branch, tag, and PR number (checked
# against 2.1.222), so a conversation that changed topic after its title was generated can't be found by
# the thing it was mostly about.
#
# Two stages, because one isn't enough: `rg` over the raw transcripts is a fast shortlist, then `jq` keeps
# only the sessions where the term appears in something the user typed. Without that second stage most hits
# are tool output, pasted files, and system reminders. The tradeoff is that a term which only ever appeared
# in pasted content won't match.
#
# Scoped to the current project by default, since that's nearly always the one being asked about. The
# project root comes from claude_project_root() rather than a copy of its rules, so the wp-content and
# mu-plugins exceptions can't drift apart from the `claude` launcher's idea of a root.
#
# Usage: claude-session-search.sh [--all-projects] [--limit N] [query]
#        --limit 0 lists every match. No query lists the most recently modified sessions instead.

set -uo pipefail

projects="$HOME/.claude/projects"
all_projects=0
limit=10
max_snippets=3
max_answers=2
snippet_length=240

# Unit separator, not tab. Tab counts as IFS whitespace even when IFS is set to nothing else, so `read`
# silently collapses empty leading fields and every column after one shifts left.
unit=$'\037'

# A second separator for the snippet lists, so folding them into one field can't collide with the split.
snippet_break=$'\036'

while [[ $# -gt 0 ]]; do
	case "$1" in
		--all-projects )
			all_projects=1
			shift
		;;

		--limit )
			limit="${2:-10}"
			shift 2
		;;

		* )
			break
		;;
	esac
done

query="$*"

if [[ ! -d "$projects" ]]; then
	printf 'error: %s not found.\n' "$projects" >&2
	exit 1
fi

# The launch folder is already the project root -- the `claude` wrapper cd's there before starting -- so
# there's nothing to resolve, just something to confirm. A folder with no CLAUDE.md isn't a project, and
# scoping to it would quietly search almost nothing.
#
# $HOME is excluded because ~/CLAUDE.md is a symlink to the global one, not a project's. Scoping to $HOME
# would also prefix-match every project underneath it.
scope_label="all projects"
search_roots=("$projects")
scope_warning=""

if [[ $all_projects -eq 0 ]]; then
	if [[ ! -f "$PWD/CLAUDE.md" ]]; then
		scope_warning="$PWD has no CLAUDE.md, so it isn't a project. Searching all projects instead."
		all_projects=1
	elif [[ "$PWD/CLAUDE.md" -ef "$HOME/CLAUDE.md" ]]; then
		scope_warning="$PWD only has the global CLAUDE.md, so it isn't a project. Searching all projects instead."
		all_projects=1
	fi
fi

# Transcripts live under a mangled copy of the launch folder, where `/`, `.`, and space all become `-`.
# Matching the mangled root as a prefix also picks up sessions launched from a subfolder of the project,
# which happens whenever `claude` starts inside wp-content.
if [[ $all_projects -eq 0 ]]; then
	scope_label="$PWD"
	mangled="${PWD//[.\/ ]/-}"
	search_roots=()

	for dir in "$projects"/*/; do
		name="${dir%/}"
		name="${name##*/}"

		if [[ "$name" == "$mangled" || "$name" == "$mangled"-* ]]; then
			search_roots+=("${dir%/}")
		fi
	done

	if [[ ${#search_roots[@]} -eq 0 ]]; then
		printf 'Scope: %s\n\n' "$scope_label"
		printf 'No sessions have ever been recorded for this project.\n'
		exit 0
	fi
fi

# Only text the user actually typed. Tool results are `tool_result` items rather than `text` ones, so they
# never reach this, which is what keeps the search off its own output.
#
# `<resumebody-instructions>` is the first line of the /resumebody command file, whose whole body gets
# injected into the transcript as one user block on every run. Excluding blocks that *start* with it drops
# that boilerplate without dropping the session: a real prompt that merely mentions the marker doesn't begin
# with it, and any other work in that session stays searchable.
prompts='select(.type == "user") | (.message.content? // empty) | (if type == "string" then . else (map(select(.type == "text") | .text) | join("\n")) end) | select(type == "string" and length > 0) | select(startswith("<command-") or startswith("<local-command-") or startswith("<resumebody-instructions>") | not)'

# Assistant text too, so a one-sentence summary can say how the question was resolved and not just what
# was asked. Only the lines mentioning the query are kept, so this stays cheap.
answers='select(.type == "assistant") | (.message.content? // empty) | (if type == "string" then . else (map(select(.type == "text") | .text) | join("\n")) end) | select(type == "string" and length > 0)'

# `reduce inputs` rather than `-s` so a 20MB transcript doesn't get slurped into memory whole. A custom
# title from /rename outranks the generated one, matching how Claude itself resolves it.
#
# Emitted as two lines rather than one delimited line so the separator can't end up as an invisible control
# character in this file. The title is flattened first, because a title taken from a prompt can be
# multi-line and would otherwise split into two records.
metadata='reduce inputs as $entry ({};
	if $entry.type == "custom-title" then .custom = $entry.customTitle
	elif $entry.type == "ai-title" then .ai = $entry.aiTitle
	elif $entry.type == "last-prompt" then .last = $entry.lastPrompt
	elif (.cwd | not) and ($entry.cwd) then .cwd = $entry.cwd
	else . end
) | [ ((.custom // .ai // .last // "") | gsub("[\\n\\r\\t]"; " ")), (.cwd // "") ] | .[]'

if [[ -n "$query" ]]; then
	matches="$(
		command rg --files-with-matches --fixed-strings --ignore-case \
			--glob '*.jsonl' -- "$query" "${search_roots[@]}" 2>/dev/null
	)"
else
	matches="$(
		fd --extension jsonl --type f . "${search_roots[@]}" --exec-batch stat -f '%m %N' {} 2>/dev/null \
			| sort -rn | head -n 40 | cut -d' ' -f2-
	)"
fi

if [[ -n "$scope_warning" ]]; then
	printf 'Warning: %s\n' "$scope_warning"
fi

printf 'Scope: %s\n\n' "$scope_label"

if [[ -z "$matches" ]]; then
	printf 'No transcript in this scope mentions "%s".\n' "$query"
	exit 0
fi

records=()

while IFS= read -r file; do
	[[ -n "$file" ]] || continue

	session_id="${file##*/}"
	session_id="${session_id%.jsonl}"

	# Subagent transcripts sit in the same folders as `agent-<id>.jsonl` and aren't resumable, so only
	# real session UUIDs get through. Cheaper here than after the jq passes, too.
	if [[ ! "$session_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
		continue
	fi

	hits=""
	found=""
	count=0

	if [[ -n "$query" ]]; then
		hits="$(
			jq -r "$prompts" "$file" 2>/dev/null \
				| command rg --fixed-strings --ignore-case -- "$query" 2>/dev/null \
				| head -n "$max_snippets" | cut -c1-"$snippet_length"
		)"

		[[ -n "$hits" ]] || continue

		count="$(
			jq -r "$prompts" "$file" 2>/dev/null \
				| command rg --count --fixed-strings --ignore-case -- "$query" 2>/dev/null
		)"
		count="${count:-0}"

		found="$(
			jq -r "$answers" "$file" 2>/dev/null \
				| command rg --fixed-strings --ignore-case -- "$query" 2>/dev/null \
				| head -n "$max_answers" | cut -c1-"$snippet_length"
		)"
	fi

	title=""
	cwd=""
	{ read -r title; read -r cwd; } <<< "$(jq -rn "$metadata" "$file" 2>/dev/null)"

	modified="$(stat -f '%Sm' -t '%Y-%m-%d' "$file" 2>/dev/null)"

	# Newlines inside the snippets would break the record apart, so they are folded here and restored as
	# separate lines on output.
	hits="$(printf '%s' "$hits" | tr '\n' "$snippet_break")"
	found="$(printf '%s' "$found" | tr '\n' "$snippet_break")"

	records+=("$(printf '%04d' "$count")$unit$modified$unit$session_id$unit${cwd:-unknown}$unit${title:-(untitled)}$unit$hits$unit$found")
done <<< "$matches"

if [[ ${#records[@]} -eq 0 ]]; then
	printf '"%s" only appears in tool output or pasted content, not in anything the user typed.\n' "$query"
	exit 0
fi

total=${#records[@]}

# Most mentions first, then most recent. This is a weak relevance signal on purpose -- ordering is not a
# recommendation, and /resumebody is told not to treat it as one.
sorted="$(printf '%s\n' "${records[@]}" | sort -r -t"$unit" -k1,1 -k2,2)"
shown=0

while IFS="$unit" read -r count modified session_id cwd title hits found; do
	if [[ $limit -gt 0 && $shown -ge $limit ]]; then
		break
	fi

	shown=$(( shown + 1 ))

	printf '## %s\n' "$session_id"
	printf 'title: %s\n' "$title"
	printf 'folder: %s\n' "$cwd"
	printf 'last active: %s\n' "$modified"

	if [[ -n "$query" ]]; then
		printf 'mentions: %s\n' "$((10#$count))"
	fi

	if [[ -n "$hits" ]]; then
		printf '%s' "$hits" | tr "$snippet_break" '\n' | command grep . | sed 's/^/asked: /'
	fi

	if [[ -n "$found" ]]; then
		printf '%s' "$found" | tr "$snippet_break" '\n' | command grep . | sed 's/^/answered: /'
	fi

	printf '\n'
done <<< "$sorted"

# The no-query listing is capped upstream, so $total is "how many were gathered" there rather than a true
# total. Saying "most recent" keeps that honest.
if [[ -z "$query" ]]; then
	printf 'Showing %d of the %d most recent sessions. Re-run with --limit 0 for the rest.\n' "$shown" "$total"
elif [[ $shown -lt $total ]]; then
	printf 'Showing %d of %d matching sessions. Re-run with --limit 0 for the rest.\n' "$shown" "$total"
else
	printf 'Showing all %d matching session(s).\n' "$total"
fi
