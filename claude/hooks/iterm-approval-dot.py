#!/usr/bin/env python3
"""
Turns the iTerm2 tab's status dot red while Claude Code waits on a permission prompt
(PermissionRequest hook).

iTerm2 draws every program's "waiting" status in the same blue as its new-output dot, and its
status colors aren't configurable, so this paints over Claude Code's own report. Hooks have no
controlling terminal, and `terminalSequence` doesn't allow OSC 21337, so the color goes through
iTerm2's API with `it2` instead. Claude Code's next status report, when the prompt is answered,
replaces it.
"""

import json
import os
import subprocess
import sys
import time

IT2 = "/Applications/iTerm.app/Contents/Resources/utilities/it2"
APPROVAL_COLOR = "#ff3b30"

# Claude Code reports its own "waiting" status around the time this hook runs, and whichever lands
# last wins. A detached process that doesn't hold up the prompt waits for that report and paints
# over it, and gives up if the prompt is answered first.
POLL_INTERVAL_SECONDS = 0.1
POLL_LIMIT_SECONDS = 5


def iterm_session_id():
    # Inside tmux the variable names the pane tmux runs in, not the one Claude Code is shown in.
    if os.environ.get("TERM_PROGRAM") != "iTerm.app" or os.environ.get("TMUX"):
        return None
    # The variable looks like `w2t8p0:93701BD3-...`, and the API wants the part after the colon.
    session_id = os.environ.get("ITERM_SESSION_ID", "").rpartition(":")[2]
    return session_id or None


def current_status(session_id):
    output = subprocess.run(
        [IT2, "session", "get-status", "--session", session_id],
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout
    return json.loads(output)


def apply(session_id):
    deadline = time.monotonic() + POLL_LIMIT_SECONDS
    while time.monotonic() < deadline:
        status = current_status(session_id)
        if status.get("status") == "waiting":
            if status.get("dot_color") != APPROVAL_COLOR:
                subprocess.run(
                    [
                        IT2, "session", "set-status",
                        "--session", session_id,
                        "--status", "waiting",
                        "--dot-color", APPROVAL_COLOR,
                        "--text-color", APPROVAL_COLOR,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
            return
        time.sleep(POLL_INTERVAL_SECONDS)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--apply":
        apply(sys.argv[2])
        return

    sys.stdin.read()
    session_id = iterm_session_id()
    if session_id and os.path.exists(IT2):
        subprocess.Popen(
            [sys.executable, __file__, "--apply", session_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A missing dot color must never interfere with the permission prompt itself.
        pass
