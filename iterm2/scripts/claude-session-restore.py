#!/usr/bin/env python3
# Resumes the Claude Code sessions that were running in iTerm before the last reboot, using the
# snapshots that `claude-session-snapshot.py` saves. Run it from iTerm's Scripts menu after iTerm
# has reopened its windows.

import glob
import json
import os
import re
import shlex
import subprocess

import iterm2

SNAPSHOT_DIR = os.path.expanduser("~/.local/state/iterm-claude-snapshots")
TRANSCRIPTS = os.path.expanduser("~/.claude/projects/*/%s.jsonl")
LOG = os.path.join(SNAPSHOT_DIR, "restore.log")
# Only POSIX shells, because `shlex.quote` isn't safe in shells like fish.
SHELLS = {"bash", "zsh", "sh"}
SESSION_ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# The command is typed as keystrokes, so a control character in a folder name would act as a key
# like Ctrl-C or Enter that quoting can't neutralize.
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")

# Ctrl-U and Ctrl-K clear anything already typed on either side of the cursor, so the command
# isn't mixed into it.
CLEAR_LINE = "\x15\x0b"

# A shutdown can kill some sessions before the last snapshot is taken, so sessions from snapshots
# shortly before it are included too.
SHUTDOWN_WINDOW_SECONDS = 180


def log(message):
    with open(LOG, "a") as file:
        file.write(message + "\n")


def boot_time():
    output = subprocess.run(
        ["sysctl", "-n", "kern.boottime"], capture_output=True, text=True
    ).stdout
    return int(re.search(r"sec = (\d+)", output).group(1))


def running_session_ids():
    output = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True).stdout
    claude_pids = set()
    for line in output.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and os.path.basename(parts[1]) == "claude":
            claude_pids.add(int(parts[0]))

    running = set()
    for path in glob.glob(os.path.expanduser("~/.claude/sessions/*.json")):
        try:
            with open(path) as file:
                data = json.load(file)
        except (OSError, ValueError):
            continue
        if data.get("pid") in claude_pids:
            running.add(data.get("sessionId"))
    return running


def load_snapshots_before(timestamp):
    snapshots = []
    for path in glob.glob(os.path.join(SNAPSHOT_DIR, "*.json")):
        try:
            with open(path) as file:
                snapshot = json.load(file)
        except (OSError, ValueError):
            continue
        saved = snapshot.get("saved") if isinstance(snapshot, dict) else None
        if isinstance(saved, (int, float)) and saved < timestamp and "windows" in snapshot:
            snapshots.append(snapshot)
    return sorted(snapshots, key=lambda snapshot: snapshot["saved"])


def claude_panes(snapshot):
    """Yields (window, tab index, pane index, pane) for every pane that was running Claude."""
    windows = snapshot.get("windows")
    for window in windows if isinstance(windows, list) else []:
        if not isinstance(window, dict) or not isinstance(window.get("tabs"), list):
            continue
        for tab_index, tab in enumerate(window["tabs"]):
            if not isinstance(tab, dict) or not isinstance(tab.get("panes"), list):
                continue
            for pane_index, pane in enumerate(tab["panes"]):
                if isinstance(pane, dict) and isinstance(pane.get("claude"), dict):
                    yield window, tab_index, pane_index, pane


# Worktree sessions report the worktree as their folder, but `--resume` only finds a transcript
# from the folder the session started in, which the transcript's first `cwd` records.
def project_root(session_id):
    for path in glob.glob(TRANSCRIPTS % session_id):
        try:
            with open(path) as file:
                for line in file:
                    try:
                        cwd = json.loads(line).get("cwd")
                    except ValueError:
                        continue
                    if cwd:
                        return cwd
        except OSError:
            continue
    return None


async def find_pane(app, window_frames, saved_window, tab_index, pane_index, pane_id):
    session = app.get_session_by_id(pane_id)
    if session:
        return session, "pane ID"

    # Fall back to the window with the same frame and tab count, then the same tab and pane order.
    # Several windows can share a frame, like maximized ones, and guessing could type into the
    # wrong pane, so a tie isn't matched.
    matches = [
        window
        for window in app.terminal_windows
        if window_frames.get(window.window_id) == saved_window.get("frame")
        and len(window.tabs) == len(saved_window["tabs"])
    ]
    if len(matches) != 1 or tab_index >= len(matches[0].tabs):
        return None, None
    sessions = matches[0].tabs[tab_index].sessions
    if pane_index < len(sessions):
        return sessions[pane_index], "position"
    return None, None


async def restore(connection):
    app = await iterm2.async_get_app(connection)

    snapshots = load_snapshots_before(boot_time())
    if not snapshots:
        return "There's no snapshot from before the last reboot."

    last_saved = snapshots[-1]["saved"]
    recent = [
        snapshot
        for snapshot in snapshots
        if snapshot["saved"] >= last_saved - SHUTDOWN_WINDOW_SECONDS
    ]

    window_frames = {}
    for window in app.terminal_windows:
        frame = await window.async_get_frame()
        window_frames[window.window_id] = {
            "x": frame.origin.x,
            "y": frame.origin.y,
            "width": frame.size.width,
            "height": frame.size.height,
        }

    # Newest snapshots first. A session skipped in one snapshot is tried again from an older one,
    # and only the reason from its newest attempt is reported.
    resumed = []
    skipped = {}
    done = running_session_ids()
    used_panes = set()
    for snapshot in reversed(recent):
        for saved_window, tab_index, pane_index, pane in claude_panes(snapshot):
            claude = pane["claude"]
            session_id = claude.get("session_id")
            session_id = session_id if isinstance(session_id, str) else ""
            label = str(claude.get("name") or session_id)
            if session_id in done:
                continue

            reason = None
            if not SESSION_ID_PATTERN.fullmatch(session_id):
                reason = "invalid session ID"
            else:
                root = project_root(session_id)
                if not isinstance(root, str) or not os.path.isdir(root):
                    reason = "no transcript or project folder"
                elif CONTROL_CHARACTER_PATTERN.search(root):
                    reason = "control character in project folder"

            if not reason:
                session, matched_by = await find_pane(
                    app, window_frames, saved_window, tab_index, pane_index, pane.get("pane")
                )
                if not session:
                    reason = "pane not found"
                elif session.session_id in used_panes:
                    reason = "pane already resumed another session"
                else:
                    job = (await session.async_get_variable("jobName") or "").lstrip("-")
                    if job not in SHELLS:
                        reason = "pane is running %s" % job

            if reason:
                skipped.setdefault(session_id, "%s (%s)" % (label, reason))
                continue

            command = "cd %s && claude --resume %s\n" % (shlex.quote(root), session_id)
            # With Broadcast Input on, the text would also reach panes the shell check never saw.
            await session.async_send_text(CLEAR_LINE + command, suppress_broadcast=True)
            used_panes.add(session.session_id)
            done.add(session_id)
            skipped.pop(session_id, None)
            resumed.append("%s (by %s)" % (label, matched_by))

    summary = "Resumed %d sessions: %s." % (len(resumed), "; ".join(resumed))
    if skipped:
        summary += " Skipped: " + "; ".join(skipped.values())
    return summary


async def main(connection):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    try:
        summary = await restore(connection)
    except Exception as error:
        summary = "Restore failed: %r" % error
    log(summary)
    await iterm2.Alert("Claude session restore", summary).async_run(connection)


iterm2.run_until_complete(main)
