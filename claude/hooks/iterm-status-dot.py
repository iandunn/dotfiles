#!/usr/bin/env python3
"""
Shows Claude Code's status as a colored dot on the iTerm2 tab, without the status words.

iTerm2 3.7.8 and later draw a status's text in the tab subtitle whenever they draw its dot, except
when the status text is empty. In iTerm, `.bashrc` sets `CLAUDE_CODE_DISABLE_TERMINAL_TITLE`,
which stops Claude Code's own status reports, so this hook sends a dot with empty text for each
event instead. That variable also stops Claude Code from titling the tab, so this hook and
`name-session.js` set the title through `terminalSequence`.

Hooks have no controlling terminal, and `terminalSequence` doesn't allow OSC 21337, so the dot goes
through iTerm2's API with `it2`.
"""

import json
import os
import re
import subprocess
import sys

IT2 = os.environ.get(
    "ITERM_STATUS_DOT_IT2", "/Applications/iTerm.app/Contents/Resources/utilities/it2"
)

WORKING_COLOR = "#ff9500"
APPROVAL_COLOR = "#ff3b30"
DONE_COLOR = "#00d75f"
# The turn is over, but background work like a pipeline watch will wake Claude Code again.
BACKGROUND_COLOR = "#af52de"

DOT_COLORS = {
    "SessionStart": DONE_COLOR,
    "UserPromptSubmit": WORKING_COLOR,
    # Nothing fires between approving a tool and it starting, so the approval color lasts until one
    # of these fires when the tool finishes.
    "PostToolUse": WORKING_COLOR,
    "PostToolUseFailure": WORKING_COLOR,
    "PermissionRequest": APPROVAL_COLOR,
    "Stop": DONE_COLOR,
    "StopFailure": DONE_COLOR,
    # A turn interrupted with Esc, or by denying a permission prompt, ends without `Stop`. This is
    # the only later event that says Claude Code is waiting for a prompt.
    "Notification": DONE_COLOR,
}

# Compaction starts a session partway through a turn, so it doesn't mean Claude Code is idle.
IDLE_SESSION_SOURCES = {"startup", "resume", "clear"}

# A control character in a title would end the escape sequence early.
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def iterm_session_id():
    # Without the variable, Claude Code reports its own status, and a dot from here would fight it.
    # Inside tmux, `ITERM_SESSION_ID` names the pane tmux runs in, not the one Claude Code is shown
    # in. An app like VS Code that was launched from iTerm inherits iTerm's variables, so its
    # Claude Code extension would otherwise paint the dot on the tab it was launched from.
    if (
        os.environ.get("TERM_PROGRAM") != "iTerm.app"
        or os.environ.get("TMUX")
        or not os.environ.get("CLAUDE_CODE_DISABLE_TERMINAL_TITLE")
        or os.environ.get("CLAUDE_CODE_ENTRYPOINT") != "cli"
    ):
        return None
    # The variable looks like `w2t8p0:93701BD3-...`, and the API wants the part after the colon.
    session_id = os.environ.get("ITERM_SESSION_ID", "").rpartition(":")[2]
    return session_id or None


def current_dot_color(session_id):
    output = subprocess.run(
        [IT2, "session", "get-status", "--session", session_id],
        capture_output=True,
        text=True,
        timeout=2,
    ).stdout
    return (json.loads(output).get("dot_color") or "").lower()


def tab_title_sequence(title):
    return "\x1b]0;%s\x07" % CONTROL_CHARACTERS.sub("", title)


def main():
    event = json.load(sys.stdin)
    session_id = iterm_session_id()
    if not session_id:
        return

    event_name = event.get("hook_event_name")
    color = DOT_COLORS.get(event_name)
    if event_name == "Stop" and (event.get("background_tasks") or event.get("session_crons")):
        color = BACKGROUND_COLOR
    elif event_name == "Notification" and (
        event.get("notification_type") != "idle_prompt"
        or current_dot_color(session_id) == BACKGROUND_COLOR
    ):
        # Background work that will wake Claude Code again outranks a prompt that's gone idle.
        color = None
    elif event_name == "SessionStart" and event.get("source") not in IDLE_SESSION_SOURCES:
        color = None
    if color and os.path.exists(IT2):
        # Claude Code waits for the hook, so two events close together can't land out of order.
        subprocess.run(
            [
                IT2, "session", "set-status",
                "--session", session_id,
                "--status", "",
                "--dot-color", color,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )

    # `name-session.js` titles the tab on each prompt. A resumed session needs its title before
    # then, and an empty title on exit hands the tab back to iTerm's own naming.
    title = None
    if event_name == "SessionStart":
        title = event.get("session_title")
    elif event_name == "SessionEnd":
        title = ""
    if title is not None:
        print(json.dumps({"terminalSequence": tab_title_sequence(title)}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A missing dot must never interfere with the session itself.
        pass
