#!/usr/bin/env bash
#
# Closes THIS Claude session's isolated chrome-devtools-mcp Chrome -- and only
# that. A parallel session's isolated browser and the personal Chrome are left
# alone, because neither descends from this session's `claude` process.
#
# The model runs this on "close the browser" (see ~/CLAUDE.md > Chrome MCP).
# Run it with the command sandbox DISABLED: it needs ps/kill (process-info),
# which the sandbox blocks at the OS level. It is allow-listed by exact path in
# settings.json, so the `kill` it runs internally is not subject to the Bash
# kill/pkill denials -- those gate the model's own commands, not the internals
# of a reviewed script.
#
# Scoping: tools and scripts run as descendants of the session's `claude`
# process, so we walk up from our own parent to find that claude PID, then kill
# only Chrome main processes whose ancestry leads back to it.

set -uo pipefail

ppid_of() { ps -o ppid= -p "$1" 2>/dev/null | tr -d ' '; }

is_claude() {
  case "$(ps -o command= -p "$1" 2>/dev/null)" in
    claude | claude\ * | */claude | */claude\ *) return 0 ;;
    *) return 1 ;;
  esac
}

descends_from_session() {
  local p
  p=$(ppid_of "$1")
  while [ -n "$p" ] && [ "$p" != "0" ] && [ "$p" != "1" ]; do
    [ "$p" = "$session_claude" ] && return 0
    p=$(ppid_of "$p")
  done
  return 1
}

session_claude=""
cur=$PPID
while [ -n "$cur" ] && [ "$cur" != "0" ] && [ "$cur" != "1" ]; do
  if is_claude "$cur"; then
    session_claude="$cur"
    break
  fi
  cur=$(ppid_of "$cur")
done

if [ -z "$session_claude" ]; then
  echo "close-isolated-chrome: could not find this session's claude process; not killing anything." >&2
  exit 1
fi

killed=0
while IFS= read -r pid; do
  [ -n "$pid" ] || continue
  descends_from_session "$pid" || continue
  udd=$(ps -o command= -p "$pid" 2>/dev/null | grep -oE -- "--user-data-dir=[^ ]+")
  if kill "$pid" 2>/dev/null; then
    echo "closed this session's isolated Chrome (pid $pid)${udd:+ [$udd]}"
    killed=1
  fi
done < <(ps -eo pid=,command= | awk '/MacOS\/Google Chrome/ && !/--type=/ {print $1}')

[ "$killed" = "0" ] && echo "no isolated Chrome for this session (nothing to close)"
exit 0
