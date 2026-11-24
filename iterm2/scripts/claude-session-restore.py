#!/usr/bin/env python3
# Resumes the Claude Code sessions that were running in iTerm before the last reboot, using the
# snapshots that `claude-session-snapshot.py` saves. Run it from iTerm's Scripts menu after iTerm
# has reopened its windows.

import asyncio
import datetime
import glob
import json
import os
import re
import shlex
import subprocess
import time

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
WORKTREE_NAME_PATTERN = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._/-]*")

# Ctrl-U and Ctrl-K clear anything already typed on either side of the cursor, so the command
# isn't mixed into it.
CLEAR_LINE = "\x15\x0b"

# A shutdown can kill some sessions before the last snapshot is taken, so sessions from snapshots
# shortly before it are included too.
SHUTDOWN_WINDOW_SECONDS = 180

# Claude Code checks whether the terminal supports status reporting once, while it starts up, and
# a session that starts in a background tab, or alongside several others, can fail that check.
# Each one gets its tab brought to the front and time to finish starting before the next one.
RESUME_DELAY_SECONDS = 3


def log(message):
    with open(LOG, "a") as file:
        file.write(message + "\n")


def boot_time():
    output = subprocess.run(
        ["sysctl", "-n", "kern.boottime"], capture_output=True, text=True
    ).stdout
    return int(re.search(r"sec = (\d+)", output).group(1))


def running_sessions():
    """Returns session ID -> start time for every running Claude Code session."""
    output = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True).stdout
    claude_pids = set()
    for line in output.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and os.path.basename(parts[1]) == "claude":
            claude_pids.add(int(parts[0]))

    running = {}
    for path in glob.glob(os.path.expanduser("~/.claude/sessions/*.json")):
        try:
            with open(path) as file:
                data = json.load(file)
        except (OSError, ValueError):
            continue
        if (
            isinstance(data, dict)
            and data.get("pid") in claude_pids
            and isinstance(data.get("sessionId"), str)
        ):
            running[data["sessionId"]] = data.get("startedAt")
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


def read_transcript(path):
    """Returns the first `cwd` in the transcript and its last `worktree-state` record."""
    cwd = None
    worktree = None
    # A crash can cut a transcript off in the middle of a character.
    with open(path, encoding="utf-8", errors="replace") as file:
        for line in file:
            # Most lines hold neither, and parsing every line of a long transcript is slow.
            if cwd and '"worktree-state"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            entry_cwd = entry.get("cwd")
            if not cwd and isinstance(entry_cwd, str) and os.path.isabs(entry_cwd):
                cwd = entry_cwd
            if entry.get("type") == "worktree-state":
                worktree = entry.get("worktreeSession")
    return cwd, worktree


def read_resume_target(path, allow_fallback=True):
    """Returns the folder to resume from, the worktree to pass to `--worktree`, and the path of a
    worktree that can't be resumed automatically, so the user can check it by hand.

    `--resume` only finds a transcript from the folder the session was launched in, which the
    transcript's folder is named after. The candidates are the launch folder that the worktree
    record holds, the worktree itself, which Claude Code can move the transcript to when a
    session enters one, and the first `cwd` in the transcript and its parents.

    Resuming without `--worktree` takes the session out of its worktree, so the worktree from the
    last `worktree-state` record is passed along, the same as the command Claude Code prints on
    exit. `--worktree` only looks in `.claude/worktrees` under the folder Claude Code starts in,
    so a worktree anywhere else, like one in a nested repository, can't be passed.

    With `allow_fallback`, the first `cwd` is used when no candidate matches.
    """
    cwd, worktree = read_transcript(path)
    folder_name = os.path.basename(os.path.dirname(path))
    is_valid_worktree = (
        isinstance(worktree, dict)
        and isinstance(worktree.get("worktreeName"), str)
        and WORKTREE_NAME_PATTERN.fullmatch(worktree["worktreeName"])
        and isinstance(worktree.get("worktreePath"), str)
        and os.path.isabs(worktree["worktreePath"])
    )

    candidates = []
    if is_valid_worktree:
        if isinstance(worktree.get("originalCwd"), str):
            candidates.append(worktree["originalCwd"])
        candidates.append(worktree["worktreePath"])
    candidate = cwd
    while candidate:
        candidates.append(candidate)
        if candidate == os.path.dirname(candidate):
            break
        candidate = os.path.dirname(candidate)
    root = next(
        (
            candidate
            for candidate in candidates
            if os.path.isabs(candidate)
            and re.sub(r"[^a-zA-Z0-9]", "-", candidate) == folder_name
        ),
        cwd if allow_fallback else None,
    )

    if not is_valid_worktree or not root or worktree["worktreePath"] == root:
        return root, None, None
    expected_path = os.path.join(root, ".claude", "worktrees", worktree["worktreeName"])
    if worktree["worktreePath"] == expected_path and os.path.isdir(expected_path):
        return root, worktree["worktreeName"], None
    return root, None, worktree["worktreePath"]


def modified_time(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def transcript_id_of(path):
    return os.path.basename(path)[: -len(".jsonl")]


def is_time(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


RECORD_SESSION_PATTERN = re.compile(r'"session_id":"([0-9a-f-]{36})"')
UNKNOWN_START_LOOKBACK_SECONDS = 14 * 24 * 60 * 60


def index_records(bounds):
    """Returns session ID -> transcript -> the time (in milliseconds) of the newest record that
    session wrote there, from every transcript modified since the earliest of `bounds` (session ID
    -> time).

    Records hold the ID of the session that wrote them as `session_id`, which can differ from the
    transcript's ID, like after `/clear` followed by `/resumebody`.
    """
    index = {}
    times = [time for time in bounds.values() if is_time(time)]
    if not times:
        return index
    since = min(times)
    for path in glob.glob(TRANSCRIPTS % "*"):
        transcript_id = transcript_id_of(path)
        if not SESSION_ID_PATTERN.fullmatch(transcript_id) or modified_time(path) * 1000 < since:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as file:
                for line in file:
                    # Parsing every line of every recent transcript would be slow. Every match is
                    # checked, because a nested object can hold a `session_id` ahead of the
                    # record's own.
                    if not any(
                        match.group(1) in bounds
                        for match in RECORD_SESSION_PATTERN.finditer(line)
                    ):
                        continue
                    try:
                        entry = json.loads(line)
                        record_time = datetime.datetime.fromisoformat(
                            entry["timestamp"].replace("Z", "+00:00")
                        ).timestamp() * 1000
                    except (ValueError, TypeError, KeyError, AttributeError):
                        continue
                    # An ID can be reused by a later process, like after `--resume`, and records
                    # from before this session started belong to an earlier one.
                    if (
                        isinstance(entry, dict)
                        and entry.get("session_id") in bounds
                        and entry.get("sessionId") == transcript_id
                        and record_time >= bounds[entry["session_id"]]
                    ):
                        records = index.setdefault(entry["session_id"], {})
                        records[path] = max(record_time, records.get(path, 0))
        except OSError:
            continue
    return index


def record_bounds(sessions):
    """Returns the earliest time each session (session ID -> start time) could have written a
    record, so `index_records` can skip older transcripts. A session saved without its start time
    is looked for over a fixed window."""
    unknown_start = (time.time() - UNKNOWN_START_LOOKBACK_SECONDS) * 1000
    return {
        session_id: started_at if is_time(started_at) else unknown_start
        for session_id, started_at in sessions.items()
    }


def rank_transcripts(session_id, index):
    """Returns the session's transcripts, best first.

    The best holds the session's newest record, because that's where its latest work is, and the
    session's own transcript wins a tie. The session's own transcript also counts as written when
    the file was, because a process started with `--resume` writes its records under a different
    `session_id`.
    """
    records = index.get(session_id, {})
    own = sorted(glob.glob(TRANSCRIPTS % session_id), key=modified_time, reverse=True)
    scored = [(max(records.get(path, 0), modified_time(path) * 1000), path) for path in own]
    scored += [(time, path) for path, time in records.items() if path not in own]
    # A stable sort keeps the session's own transcripts ahead of others with the same time.
    return [path for _, path in sorted(scored, key=lambda item: item[0], reverse=True)]


def resume_target(session_id, index):
    """Returns `read_resume_target()` for the best transcript with a usable folder, plus the
    transcript's ID for `--resume`, or None when there's no transcript at all.

    A session can have copies of a transcript in several project folders, like when it was
    resumed from a different folder. A copy whose folder name matches a candidate is preferred
    over guessing from the first `cwd` of a newer one. Other transcripts are older work, so
    they're never resumed in its place.
    """
    ranked = rank_transcripts(session_id, index)
    if not ranked:
        return None
    transcript_id = transcript_id_of(ranked[0])
    copies = [path for path in ranked if transcript_id_of(path) == transcript_id]
    for allow_fallback in (False, True):
        for path in copies:
            try:
                root, worktree_name, lost_worktree = read_resume_target(path, allow_fallback)
            except OSError:
                continue
            if root and os.path.isdir(root) and not CONTROL_CHARACTER_PATTERN.search(root):
                return root, worktree_name, lost_worktree, transcript_id
    return None, None, None, None


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
    lost_worktrees = []
    skipped = {}
    used_panes = set()

    # One pass over the recent transcripts finds where the saved and running sessions last wrote.
    saved_sessions = {}
    for snapshot in recent:
        for _, _, _, pane in claude_panes(snapshot):
            session_id = pane["claude"].get("session_id")
            if isinstance(session_id, str) and SESSION_ID_PATTERN.fullmatch(session_id):
                saved_sessions[session_id] = pane["claude"].get("started_at")
    running = running_sessions()
    index = index_records(record_bounds({**saved_sessions, **running}))
    targets = {}

    # Sessions that are running or already resumed, and the transcripts they're writing to.
    done = set(running)
    transcripts_in_use = set()
    for session_id in running:
        ranked = rank_transcripts(session_id, index)
        if ranked:
            transcripts_in_use.add(transcript_id_of(ranked[0]))

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
                if session_id not in targets:
                    targets[session_id] = resume_target(session_id, index)
                target = targets[session_id]
                if target is None:
                    reason = "no transcript"
                elif target[0] is None:
                    reason = "no usable project folder in the transcript"
                else:
                    root, worktree_name, lost_worktree, transcript_id = target
                    if transcript_id in transcripts_in_use:
                        skipped.pop(session_id, None)
                        continue

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

            worktree_option = "--worktree %s " % shlex.quote(worktree_name) if worktree_name else ""
            command = "cd %s && claude %s--resume %s\n" % (
                shlex.quote(root), worktree_option, transcript_id
            )
            await session.async_activate(select_tab=True, order_window_front=True)
            # With Broadcast Input on, the text would also reach panes the shell check never saw.
            await session.async_send_text(CLEAR_LINE + command, suppress_broadcast=True)
            await asyncio.sleep(RESUME_DELAY_SECONDS)
            used_panes.add(session.session_id)
            done.add(session_id)
            transcripts_in_use.add(transcript_id)
            skipped.pop(session_id, None)
            resumed.append("%s (by %s)" % (label, matched_by))
            if lost_worktree:
                lost_worktrees.append("%s: %s" % (label, lost_worktree))

    summary = "Resumed %d sessions: %s." % (len(resumed), "; ".join(resumed))
    if lost_worktrees:
        summary += (
            "\n\nThese sessions were resumed outside the worktree they were in. Check each"
            " worktree for uncommitted work before continuing in the session: "
            + "; ".join(lost_worktrees)
        )
    if skipped:
        summary += "\n\nSkipped: " + "; ".join(skipped.values())
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
