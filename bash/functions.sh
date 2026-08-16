_complete_ssh_hosts ()
{
	# this has a bug where hosts need to have multiple hostnames in order to work
	# see https://chatgpt.com/c/6824adea-296c-8006-ae12-f7df5a7e56eb

    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"

    local hosts_from_known_hosts
    hosts_from_known_hosts=$(cut -f 1 -d ' ' ~/.ssh/known_hosts 2>/dev/null | \
                             sed -e 's/,.*//g' | \
                             grep -v '^\[' | \
                             grep -v '^#' | \
                             uniq)

    local hosts_from_config
    hosts_from_config=$(grep -i '^Host ' ~/.ssh/config 2>/dev/null | \
                        awk '{for (i=2;i<=NF;i++) print $i}' | \
                        grep -v '[*?]')

    local comp_ssh_hosts
    comp_ssh_hosts=$(echo -e "${hosts_from_known_hosts}\n${hosts_from_config}" | sort -u)

    COMPREPLY=( $(compgen -W "${comp_ssh_hosts}" -- "$cur") )
    return 0
}

_wp_complete() {
	local OLD_IFS="$IFS"
	local cur=${COMP_WORDS[COMP_CWORD]}

	IFS=$'\n';  # want to preserve spaces at the end
	local opts="$(wp cli completions --line="$COMP_LINE" --point="$COMP_POINT")"

	if [[ "$opts" =~ \<file\>\s* ]]
	then
		COMPREPLY=( $(compgen -f -- $cur) )
	elif [[ $opts = "" ]]
	then
		COMPREPLY=( $(compgen -f -- $cur) )
	else
		COMPREPLY=( ${opts[*]} )
	fi

	IFS="$OLD_IFS"
	return 0
}

# Prints a section header, to help make script output more readable
section() {
    printf "\n\033[1;33;40m%s \033[0m\n" "$1"
}

success_message() {
	printf "\n\033[1;32;40m%s \033[0m\n" "$1"
}

error_message() {
	printf "\n\033[1;31;40m%s \033[0m\n" "$1"
}

warning_message() {
	printf "\n\033[1;33;40m%s \033[0m\n" "$1"
}

info_message() {
	printf "\n\033[1;34;40m%s \033[0m\n" "$1"
}

# Remove hard line wraps when copying from narrow terminal windows, and
# strip leading quote/pipe markers (e.g. "▎", "|", ">") left by wrapped blockquotes
#
# A wrapper that hard-splits an over-long token (a URL, a long chained expression) leaves
# nothing in the text to distinguish that break from a break between two words, so every
# join gets a space and the suspect junctions are reported on stderr instead of guessed
# at. A stray space inside a token is loud; a swallowed space between two URLs is silent.
#
# "|" and ">" are also legitimate shell syntax (pipes, sed delimiters, redirects), and a
# wrap can land one at the start of a continuation line, so those two are only treated as
# quote markers when the line looks like part of a quote block: an adjacent line is also
# marked, the marker is followed by whitespace, and the line isn't a markdown table row.
# "▎" is decorative-only and always stripped. Every "|"/">" strip is reported on stderr.
#
# Lives here rather than in aliases/ because it needs per-line logic and a stderr channel
# that stays out of the clipboard.
unwrap() {
	pbpaste | perl -CSD -e '
		use utf8;

		local $/;
		my $text = <STDIN>;

		# Terminal copies pad every line to the window width with trailing spaces;
		# stripping them first keeps the wrap-column estimate honest.
		$text =~ s/[ \t]+$//mg;
		$text =~ s/^[ \t]+//mg;

		my @lines = split /\n/, $text, -1;
		my @looks_quoted = map { /^[▎|>]/ ? 1 : 0 } @lines;
		my $stripped_ambiguous = 0;

		for my $i (0 .. $#lines) {
			if ($lines[$i] =~ /^▎/) {
				$lines[$i] =~ s/^[▎|>]+[ \t]*//;
				next;
			}

			next unless $lines[$i] =~ /^[|>]+([ \t]|$)/;
			next if $lines[$i] =~ /^\|/ and $lines[$i] =~ /\|$/;

			my $neighbor_marked = ($i > 0 and $looks_quoted[$i - 1])
				|| ($i < $#lines and $looks_quoted[$i + 1]);
			next unless $neighbor_marked;

			$lines[$i] =~ s/^[|>]+[ \t]*//;
			$stripped_ambiguous++;
		}

		$text = join("\n", @lines);

		my @suspect;
		my @chunks = split /(\n{2,})/, $text;

		for my $chunk (@chunks) {
			next if $chunk =~ /^\n*$/;

			my @chunk_lines = split /\n/, $chunk, -1;
			my $wrap_column = 0;

			for my $line (@chunk_lines) {
				$wrap_column = length($line) if length($line) > $wrap_column;
			}

			for my $i (1 .. $#chunk_lines) {
				my ($tail) = $chunk_lines[$i - 1] =~ /(\S+)$/;
				my ($head) = $chunk_lines[$i] =~ /^(\S+)/;

				# A wrapper only hard-splits a token that is itself longer than the
				# wrap column, and only on a line that reached that column. The column
				# is estimated per paragraph rather than across the whole paste, which
				# over-reports rather than under-reports: a spurious warning costs a
				# line of noise, a missed one costs a silently wrong paste.
				next unless defined $tail and defined $head;
				next unless length($chunk_lines[$i - 1]) == $wrap_column;
				next unless length($tail) + length($head) > $wrap_column;

				push @suspect, substr($tail, -25) . "  <-JOINED->  " . substr($head, 0, 25);
			}

			$chunk = join(" ", grep { length } @chunk_lines);
		}

		print join("", @chunks);

		if ($stripped_ambiguous) {
			printf STDERR "\033[1;33;40munwrap: stripped a leading \"|\" or \">\" from %d line(s) as a quote marker; if this was shell syntax, re-copy and fix by hand\033[0m\n", $stripped_ambiguous;
		}
		if (@suspect) {
			printf STDERR "\033[1;33;40munwrap: %d join(s) may fall inside a token rather than between words:\033[0m\n", scalar @suspect;
			printf STDERR "  %s\n", $_ for @suspect;
		}
	' | pbcopy
}

# find all files in the current folder and below, then grep each of them for the given string
# this could _almost_ be an alias, but then $QUERY would have to be at the end of the command, so you couldn't remove the binary files
#
# TODO this could maybe be replaced by `grep -R` or `rgrep`. Need to test.
function findgrep {
	echo "use ripgrep instead"
	exit

	local QUERY=$1
	local MATCHES=$(find . -type f ! -name "*.svn*" ! -name "*.git*" -follow |xargs grep --ignore-case --line-number --no-messages $QUERY)
	# ! -path '*/.svn/*' ! -path '*/.git/*' might be better ?
	local OUTPUT=$(printf '%s\n' "${MATCHES[@]}" | grep -v "Binary file")
	# also add build, vendor, etc folders to exclude?

	printf '%s\n' "${OUTPUT[@]}"
}

# especiallly helpful when git and svn checked out side by side, like w/ gutenberg plugin
function svn_rm_untracked {
	local FILES=$(svn status | egrep '^\?' | awk '{print $2}')

	 rm -rf ${FILES[@]}
}

# todo describe
function wordcamp_diff() {
	exit
	# not done yet

	local args=($@)
	local rest=(${args[@]:1:${#args[@]}})
	local WP_CONTENT="/Users/ian/vhosts/virtual-machines/vvv-personal/www/wordcamp.dev/public_html/wp-content"

	local GIT_DIRS=(
		"mu-plugins"
		"mu-plugins-private/wporg-mu-plugins"
		"plugins-meta"
		"themes-meta"
		"wp-super-cache-plugins"
	)

	local SVN_DIRS=(
		"plugins-external"
		"themes-external"
	)

	for i in "${GIT_DIRS[@]}"
	do :
		git -C $WP_CONTENT/$i stat
	done

	for i in "${SVN_DIRS[@]}"
	do :
		svn stat "$WP_CONTENT/$i" |prune-svn-stat
	done
}

# Bump svn:externals in the current directory
#
# $1 - The plugin/theme slug
# $2 - The version to bump to
# $3 - "local" if you want to only make the change locally, short-circuiting the diff/commit/deploy process.
#      This is useful when you want to update several externals in a row, then commit them all at once.
#
# Examples:
# svn_bump_ext akismet 3.2
# svn_bump_ext twentyfifteen 1.6 local
#
function svn_bump_ext {
	svn_bump_ext_update_property $1 $2

	if [[ 'local' == $3 ]]; then
		return
	fi

	printf "Fetching latest externals...\n\n"
	svn up
	printf "\nDone fetching, you can test the new externals now."

	svn_bump_ext_commit $1 $2
}

# svn-bump-ext helper for updating svn:externals
#
# $1 - The plugin/theme slug
# $2 - The version to bump to
function svn_bump_ext_update_property {
	# Use printf to avoid adding a trailing newline
	printf %s "$(svn propget svn:externals)" > externals.tmp

	local search="$1/(tags/)?(.*)/"
	local replace="$1/\1$2/"

	# The space is a valid delimiter, just like / or @, but improves readability
	eval "sed -i '' -E 's $search $replace ' externals.tmp"

	svn propset svn:externals -F externals.tmp .
	rm -f externals.tmp
}

# svn-bump-ext helper for diff / commit / deploy
#
# $1 - The plugin/theme slug
# $2 - The version to bump to
function svn_bump_ext_commit {
	printf "\nExternal differences:\n\n"
	svn diff --depth empty

	printf "\nCommit and deploy the changes? [y/n]: "
	read commit

	if [[ 'y' != $commit ]]; then
		printf "\nAborting, did not commit.\n"
		return
	fi

	message="Externals: Bump \`$1\` to \`$2\`"
	printf "\nCommit message: [$message]: "
	read new_message

	# Enter and "y" both mean that the user wants to accept the default message
	if [[ "" != $new_message && "y" != $new_message ]]; then
		message=$new_message
	fi

	eval "svn ci --depth empty -m '$message'"

	printf "\nDeploying...\n"
	eval "deploy"
}


# Convert a stereo recording to mono
#
# See https://iandunn.name/2017/06/04/dropping-quicktime-recording-from-stereo-to-mono/
#
# $1 - The input filename
function qtmono {
	basename=$(basename "$1")
	filename="${basename%.*}"
	extension="${basename##*.}"

	ffmpeg -i $1 -codec:v copy -af pan="mono: c0=FL" $filename-mono.$extension
}

# Sync canonical Git repos with legacy/deploy SVN repos
function sync {
	current_folder=$(pwd)
	printf "\n"

	case "$current_folder" in
		*wordcamp.test* )
			php /Users/iandunn/vhosts/localhost/wordcamp.test/public_html/bin/php/multiple-use/miscellaneous/sync-svn-with-git.php
		;;

		*themes/wporg-news* )
			ssh wordpress.org '$SYNCPATH/news.sh'
		;;

		*wporg-mu-plugins* )
			echo "Sync script broken until https://github.com/WordPress/wporg-mu-plugins/pull/175 merged"
			#ssh wordpress.org '$SYNCPATH/wporg-mu-plugins.sh'
		;;

		*wporg-5ftf* )
			ssh wordpress.org '$SYNCPATH/5ftf.sh'
		;;

		* )
			printf "Couldn't detect repo to sync.\n"
		;;
	esac
}

# Deploy the site that corresponds to the current directory
# $1 For w.org, the role to deploy. Otherwise unused.
function deploy {
	current_folder=$(pwd)
	printf "\n"

	# w.org sandbox
	if [[ 'iandunn.dev.ord.wordpress.org' = $(hostname) ]]; then
		case "$current_folder" in
			*wordcamp* )
				echo "Updating everything"
				svnup $WORDCAMP_PATH

				if ! $WORDCAMP_PATH/bin/php/multiple-use/miscellaneous/wpcut; then
					printf "\n\nERROR: Aborting deploy. Make 'wpcut' pass and then retry.\n\n"
					return
				else
					echo "Command succeeded, continue"
				fi

				deploy-wordcamp.sh
			;;

			*wporg* )
				echo "Updating everything"
				svnup $WPORGPATH

				printf "\n"
				deploy-dotorg.sh $1
			;;

			*api* | *buddypress* | *planet* )
				deploy-dotorg.sh $1
			;;

			* )
				echo "Couldn't detect site to deploy."
			;;
		esac;

		return
	fi

	# local sandbox
	case "$current_folder" in
		*wordcamp.test* )
			ssh wordcamp.org 'deploy-wordcamp.sh'
		;;

		*themes/wporg-news* )
			ssh wordpress.org 'deploy-dotorg.sh'
		;;

		*wporg-mu-plugins* )
			ssh wordpress.org 'deploy-dotorg.sh'
		;;

		*i18n-tools* )
			ssh wordpress.org 'deploy-dotorg.sh'
		;;

		*wp15.wordpress.test* )
			ssh -t wp15.wordpress.net 'svn up ~/wp15.wordpress.net'
		;;

		*wordpressfoundation.test* )
			ssh -t wordpressfoundation.org 'svn up ~/public_html/'
		;;

		*iandunn.localhost* )
			bash /Users/iandunn/vhosts/localhost/iandunn.localhost/bin/deploy.sh
		;;

		*regolith.iandunn.localhost* )
			bash /Users/iandunn/vhosts/localhost/regolith.iandunn.localhost/bin/deploy.sh
		;;

		* )
			printf "Couldn't detect site to deploy.\n"
		;;
	esac
}

# Wrapper for phpmd to avoid having to specify report type and config file.
#
# $1 - The file/folder to analyize
function phpmd {
	env phpmd $1 text ~/vhosts/localhost/wordcamp.test/phpmd.xml.dist
}

# Run composer commands from subfolder without prompt
#
# When running `composer update`, etc, it obnoxiously complains that you're not in the root folder, and makes you
# confirm that you want to execute the commands based on the `composer.json` in the root. That only exists for
# back-compat due to a (IMO) poor design decision. See https://github.com/composer/composer/issues/6426.
#
# This function works around that inconvenience so that you're not prompted if you're in a known project.
function composer {
	current_folder=$(pwd)

	case "$current_folder" in
		*wordcamp.test* )
			env composer "$@" -d /Users/iandunn/vhosts/localhost/wordcamp.test/
		;;

		* )
			env composer "$@"
		;;
	esac
}

# run a request against all w.org web heads
# must be ran on sandbox, must use http
function check_all_wporg_web_heads {
	local query_string = $1

	for i in $(seq 1 5); do
		curl "http://web$i.ord.wordpress.org$query_string" -I -H 'Host: wordpress.org';
	 done
}

# copy a new dev process template to the given filename in the current repo's _notes folder
# call this when starting a new task so you have an intentional approach
function devnote {
	local dir="$PWD"
	local template="$HOME/dotfiles/docs/development-process-and-tips.md"
	local ext="md"
	local filename
	local target
	local dest

	# Find nearest _notes directory
	while [ "$dir" != "/" ]; do
		if [ -d "$dir/_notes" ]; then
			target="$dir/_notes"
			break
		fi

		dir="$(dirname "$dir")"
	done

	if [ -z "$target" ]; then
		printf "\nError: No \`_notes\` directory found in parent tree.\n" >&2
		return 1
	fi

	# Prompt for filename
	printf "\n"
	read -p "Enter a filename (without extension): " filename

	if [ -z "$filename" ]; then
		printf "\nError: No filename entered." >&2
		return 1
	fi

	dest="$target/$filename.$ext"

	if [ -e "$dest" ]; then
		printf "\nError: File $filename.$ext already exists in $target. No files were modified.\n" >&2
		return 1
	fi

	cp "$template" "$dest"
	printf "\nCopied to $dest\n"
}


listening() {
	[ -z "$1" ] && {
		echo "usage: listening <port>"
		return 1
	}

	pid=$(lsof -ti:"$1") || return

	lsof -i:"$1"
	echo ""
	ps -fp "$pid"
}


# todo is there a way to integrate this with autocomple so can `git co tru` and it'll show fzf list of `trunk`, `truncate/foo`, etc?
# but then if there's only 1 match it'll just autocomplete it
#
# Resolves a branch name from a query using local exact match, single fuzzy match, remote fallback, then fzf.
# Outputs the resolved branch name, or nothing if nothing was selected.
_git_resolve_branch() {
	local query="$1"
	local branches

	if [[ "$query" == "-" ]]; then
		echo "-"
		return
	fi

	# TODO allow autocompleet `git co dev<tab>` should complete to `develop`

	branches=$(git branch --no-color | tr -d ' *')

	# If it's a filename, skip checkout.
	if [[ -e "$query" ]]; then
		# also support if it's a branch and then a filename like git co trunk composer.lock
		git checkout "$query"
		return
	fi

	# Skip fuzzy search when there's an exact match
	if echo "$branches" | grep --color=never -qx "$query"; then
		echo "$query"
		return
	fi

	if [[ -n "$query" ]]; then
		local matches count

		# Single fuzzy local match
		matches=$(echo "$branches" | grep --color=never -i "$query")
		count=$(echo "$matches" | grep --color=never -c .)

		if [[ "$count" -eq 1 ]]; then
			echo "$matches"
			return
		fi

		# Remote branch fallback — avoids fzf showing 0 results for untracked remote branches
		local remote_match
		remote_match=$(git ls-remote origin "refs/heads/$query" 2>/dev/null | awk '{print $2}' | sed 's|refs/heads/||')
		if [[ -n "$remote_match" ]]; then
			echo "$remote_match"
			return
		fi
	fi

	local branch
	branch=$(echo "$branches" | fzf --exact --query="$query")
	[[ -n "$branch" ]] && echo "$branch"
}

git_fuzzy_switch() {
	local branch
	branch=$(_git_resolve_branch "$1")

	if [[ "$branch" == "-" ]]; then
		git switch -
	elif [[ -n "$branch" ]]; then
		git switch "$branch"
	fi
}

git_fuzzy_merge() {
	local branch
	branch=$(_git_resolve_branch "$1")

	[[ -n "$branch" && "$branch" != "-" ]] && git merge "$branch"
}

# Force Claude to open in the root folder of a project
#
# Claude annoying treats the folder it was launched from as the project root. If the root is ~/local-sites/core/
# and that's where the CLAUDE.md file is, but you launch claude from ~/local-sites/core/app/public/wp-content or
# ~/local-sites/core/app/public/wp-content/mu-plugins, then it'll created .claude/settings.local.json files in
# those subdirectories, and have separate conversation history from each other and from the project root.
#
# This scans for a CLAUDE.md at the project root and launches claude from there. $HOME also has a global CLAUDE.md,
# though, so this stops before that, to avoid $HOME being treated as a project root.
#
# This assumes that all projects should have a CLAUDE.md file at the root folder that identifies it as a project
# and provides project-specific instructions.
#
# claude_project_root() walks up from $1 (default $PWD) and outputs the folder that owns the winning CLAUDE.md,
# or nothing if there isn't one. claude() below is the wrapper that launches from it.
#
# Which CLAUDE.md wins when several are stacked:
#   - A git repo that carries its own CLAUDE.md is a self-contained project, so the nearest one wins. That's how
#     a standalone repo parked inside a Local site (~/local-sites/misc/app/public/foo) becomes its
#     own root rather than resolving to the site folder.
#   - `wp-content` and `mu-plugins` are excluded from that. They're the site's own git repo rather than an
#     independent project, and the personal CLAUDE.md above them (e.g. ~/local-sites/10up/bar/) holds the
#     context that matters.
#   - Otherwise the highest one wins, which covers a vendored plugin that ships a CLAUDE.md without being a repo
#     of its own, like `wp-content/plugins/safe-svg`. Claude Code reads nested CLAUDE.md files for context,
#     so the lower ones are still loaded.
#
# ~/local-sites/ acts as a stop boundary like $HOME — it has a shared CLAUDE.md that provides context for all
# local sites, but shouldn't itself be treated as a project root.
#
# A directory holding the global CLAUDE.md itself isn't a project root either. Stopping before $HOME isn't
# enough, because ~/CLAUDE.md is a symlink to ~/dotfiles/claude/CLAUDE.md, so the walk would otherwise treat
# ~/dotfiles/claude/ as a root. -ef compares the resolved files.
#
# TODO If the `wp-content`/`mu-plugins` exception list has to keep growing, switch to marker files instead: a
# `.claude-walker-stop` in ~/local-sites, ~/local-sites/misc/app/public, etc, that halts the walk. That moves
# the layout knowledge next to the folders it describes, and would replace the hardcoded stop boundaries too.
claude_project_root() {
	local dir="${1:-$PWD}"
	local root=""
	local local_sites="$HOME/local-sites"

	while [[ "$dir" != "$HOME" && "$dir" != "$local_sites" && "$dir" != "/" ]]; do
		if [[ -f "$dir/CLAUDE.md" ]] && ! [[ "$dir/CLAUDE.md" -ef "$HOME/CLAUDE.md" ]]; then
			root="$dir"

			# -e rather than -d so worktrees and submodules count, where .git is a file.
			if [[ -e "$dir/.git" ]]; then
				case "${dir##*/}" in
					wp-content | mu-plugins )
					;;

					* )
						break
					;;
				esac
			fi
		fi

		dir="$(dirname "$dir")"
	done

	printf '%s' "$root"
}

# See claude_project_root() above for how the root folder is chosen.
function claude() {
	local root
	root="$(claude_project_root)"

	if [[ -z "$root" ]]; then
		printf "\n⚠️ No project root found, launching from current folder\n\n" >&2
		command claude "$@"
	elif [[ "$root" == "$PWD" ]]; then
		command claude "$@"
	else
		printf "\n⚠️ Project root found at %s, launching from that folder\n\n" "$root" >&2
		cd "$root" && command claude "$@"
	fi
}

runbeep() {
	local cmd=("$@")
	local status

	"${cmd[@]}"
	status=$?

	afplay /System/Library/Sounds/Funk.aiff

	if [[ $status -eq 0 ]]; then
		osascript -e "display notification \"Done: ${cmd[*]}\" with title \"Success\""
	else
		osascript -e "display notification \"Failed (exit $status): ${cmd[*]}\" with title \"Failed\""
	fi

	return $status
}

git_main_branch() {
	# todo this doesn't work w/ publix b/c vip has master set as main branch even though we treat trunk as main?
	# maybe affects williams too. no it works for williams. why?
	git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
}

# Write every running Claude Code session to a Markdown file, so they can be restarted after quitting
# VS Code or rebooting. Claude keeps the conversations on disk, but nothing restarts the processes, and
# `claude --resume` needs a session ID that isn't visible anywhere in the terminal.
#
# `~/.claude/sessions/<pid>.json` is Claude's own registry of running sessions. Entries stick around
# after a session exits, so the PID is the only reliable liveness signal.
save_active_claude_sessions() {
	local now
	local timestamp

	# todo don't save empty sessions. ones that were opeened but no prompts yet, or that were finished weth /new or /clear

	# One `date` call so the filename and the header can't straddle a second boundary. Timestamped
	# because the snapshot taken right before a reboot is the one worth keeping.
	now="$(date '+%Y-%m-%d %H:%M:%S')"
	timestamp="${now//[: ]/-}"

	local report="$HOME/Downloads/active-claude-sessions-$timestamp.md"
	local registry="$HOME/.claude/sessions"

	if [[ ! -d "$registry" ]]; then
		error_message "error: $registry not found."
		return 1
	fi

	local rows=()
	local file

	for file in "$registry"/*.json; do
		[[ -e "$file" ]] || continue

		local pid
		pid="$(basename "$file" .json)"

		command ps -p "$pid" -o pid= > /dev/null 2>&1 || continue

		local cwd session_id name
		# Herestring rather than process substitution because git's `!` aliases source this file with
		# `/bin/sh`, and bash in POSIX mode can't parse `< <(...)` -- a syntax error there breaks every
		# function in the file, not just this one.
		IFS=$'\t' read -r cwd session_id name <<< "$(
			jq -r 'select(.kind == "interactive") | [.cwd, .sessionId, .name] | @tsv' "$file" 2>/dev/null
		)"

		# Skips background and one-shot `--print` sessions, which have nothing to reopen.
		[[ -n "$session_id" ]] || continue

		# The transcript lives under a mangled copy of the project path, so find it by session ID instead
		# of trying to reproduce the mangling.
		local transcripts=("$HOME/.claude/projects"/*/"$session_id.jsonl")
		local title=""

		if [[ -e "${transcripts[0]}" ]]; then
			title="$(jq -r 'select(.type == "ai-title") | .aiTitle' "${transcripts[0]}" 2>/dev/null | tail -1)"

			# A session that hasn't earned a title yet still has the prompt that started it, which beats
			# falling through to a derived name like `dmv-a8`.
			if [[ -z "$title" ]]; then
				title="$(
					jq -r 'select(.type == "last-prompt") | .lastPrompt' "${transcripts[0]}" 2>/dev/null \
						| tail -1 | tr '\n' ' ' | cut -c1-90
				)"
			fi
		fi

		rows+=("$cwd"$'\t'"${title:-$name}"$'\t'"$session_id")
	done

	if [[ ${#rows[@]} -eq 0 ]]; then
		warning_message "No running Claude sessions found."
		return 0
	fi

	{
		printf '# Active Claude sessions\n\n'
		printf 'Saved %s. Open a terminal in each folder and run the commands below.\n' "$now"

		local current_cwd=""
		local cwd title session_id

		while IFS=$'\t' read -r cwd title session_id; do
			if [[ "$cwd" != "$current_cwd" ]]; then
				printf '\n\n## %s\n\n`cd %s`\n\n' "${cwd##*/}" "$cwd"
				current_cwd="$cwd"
			fi

			printf -- '- %s\n  `claude --resume %s`\n' "$title" "$session_id"
		done <<< "$(printf '%s\n' "${rows[@]}" | sort)" # Herestring for the same `/bin/sh` reason as above.

		printf '\n'
	} > "$report"

	success_message "Saved ${#rows[@]} sessions to $report"
}

git_archive_stale_branches() {
	local cutoff_date
	local main_branch
	local branches
	local current_branch

	cutoff_date=$(date -d '3 months ago' '+%Y-%m-%d' 2>/dev/null || date -v-3m '+%Y-%m-%d')

	main_branch=$(git_main_branch)

	if [[ -z "$main_branch" ]]; then
		error_message "error: origin/HEAD is not set."
		return 1
	fi

	current_branch=$(git symbolic-ref --short HEAD 2>/dev/null)

	if [[ $(git status --porcelain) ]]; then
		error_message "error: working tree is not clean. Stash or commit changes before pruning." >&2
		return 1
	fi

	if [[ "$current_branch" != "$main_branch" ]]; then
		info_message "Switching to $main_branch..."
		git switch "$main_branch"
	fi

	local skip_branches="dev|develop|development|preprod|retainer|st|staging|uat|it"

	branches=$(git for-each-ref --format='%(refname:short) %(committerdate:short)' refs/heads \
		| awk -v cutoff="$cutoff_date" -v main="$main_branch" -v skip="$skip_branches" \
			'$2 < cutoff && $1 != main && $1 !~ ("^(" skip ")$") {print $1}')

	if [[ -z "$branches" ]]; then
		info_message "No stale branches found (older than 3 months)."
		return 0
	fi

	info_message "Found stale branches (no commits since $cutoff_date):"
	echo "$branches" | sed 's/^/  /'
	echo

	while IFS= read -r branch; do
		local last_commit

		last_commit=$(git log -1 --format='%ci (%cr)' "$branch")

		echo "Branch: $branch"
		echo "Last commit: $last_commit"
		printf "Keep this branch? [y/N] "
		read -r response </dev/tty

		case "$response" in
			[yY]|[yY][eE][sS])
				echo "Keeping $branch."
				;;

			*)
				local diff_output
				local safe_name

				diff_output=$(git diff "$main_branch"..."$branch")

				if [[ -z "$diff_output" ]]; then
					warning_message "⚠️ diff against $main_branch is empty — branch may already be merged or changes reverted. Skipping deletion." >&2
					echo
					continue
				fi

				safe_name=$(echo "$branch" | tr '/' '_')

				local diff_file="./${safe_name}.diff"

				mkdir -p "$diff_dir"
				echo "Saving diff to ./${diff_file}..."
				echo "$diff_output" > "$diff_file"

				git branch -D "$branch"
				;;
		esac
		echo
	done <<< "$branches"

	success_message "Done."
}
