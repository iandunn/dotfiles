#!/usr/bin/env python3
# Saves every iTerm window's tabs, splits, sizes, and the Claude Code session running in each pane,
# so the sessions can be resumed after a reboot kills them. Runs from iTerm's AutoLaunch folder.

import asyncio
import glob
import json
import os
import re
import subprocess
import time

import iterm2

SNAPSHOT_DIR = os.path.expanduser("~/.local/state/iterm-claude-snapshots")
INTERVAL_SECONDS = 60

# A snapshot taken while a shutdown is killing processes can be missing sessions, so earlier ones
# are kept whenever the set of sessions changes.
HISTORY_LIMIT = 20

# `claude-session-restore.py` reads the snapshots from this long before the last boot, so those are
# never pruned, however many changes come after the reboot.
SHUTDOWN_WINDOW_SECONDS = 180


def boot_time():
    output = subprocess.run(
        ["sysctl", "-n", "kern.boottime"], capture_output=True, text=True
    ).stdout
    return int(re.search(r"sec = (\d+)", output).group(1))


def claude_sessions_by_tty():
    output = subprocess.run(
        ["ps", "-axo", "pid=,tty=,comm="], capture_output=True, text=True
    ).stdout
    tty_by_pid = {}
    for line in output.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and os.path.basename(parts[2]) == "claude":
            tty_by_pid[int(parts[0])] = "/dev/" + parts[1]

    sessions = {}
    for path in glob.glob(os.path.expanduser("~/.claude/sessions/*.json")):
        try:
            with open(path) as file:
                data = json.load(file)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("sessionId"), str):
            continue
        tty = tty_by_pid.get(data.get("pid"))
        if tty and data.get("kind") == "interactive":
            sessions[tty] = {
                "session_id": data.get("sessionId"),
                "cwd": data.get("cwd"),
                "name": data.get("name", ""),
            }
    return sessions


def describe_layout(node):
    if isinstance(node, iterm2.Session):
        return {"pane": node.session_id}
    return {
        "vertical": node.vertical,
        "children": [describe_layout(child) for child in node.children],
    }


async def collect(app):
    claude_sessions = claude_sessions_by_tty()
    windows = []
    for window in app.terminal_windows:
        frame = await window.async_get_frame()
        tabs = []
        for tab in window.tabs:
            panes = []
            for session in tab.sessions:
                tty = await session.async_get_variable("tty")
                panes.append({
                    "pane": session.session_id,
                    "tty": tty,
                    "path": await session.async_get_variable("path"),
                    "columns": session.grid_size.width,
                    "rows": session.grid_size.height,
                    "claude": claude_sessions.get(tty),
                })
            tabs.append({"layout": describe_layout(tab.root), "panes": panes})
        windows.append({
            "window": window.window_id,
            "frame": {
                "x": frame.origin.x,
                "y": frame.origin.y,
                "width": frame.size.width,
                "height": frame.size.height,
            },
            "tabs": tabs,
        })
    return windows


def claude_ids(windows):
    return sorted(
        pane["claude"]["session_id"]
        for window in windows
        for tab in window["tabs"]
        for pane in tab["panes"]
        if pane["claude"]
    )


def prune_history():
    saved_times = {}
    for path in glob.glob(os.path.join(SNAPSHOT_DIR, "history-*.json")):
        match = re.search(r"history-(\d+)\.json$", path)
        if match:
            saved_times[path] = int(match.group(1))

    boot = boot_time()
    before_boot = [saved for saved in saved_times.values() if saved < boot]
    protected_after = max(before_boot) - SHUTDOWN_WINDOW_SECONDS if before_boot else None

    history = sorted(saved_times, key=saved_times.get)
    for old in history[:-HISTORY_LIMIT]:
        saved = saved_times[old]
        if protected_after is not None and protected_after <= saved < boot:
            continue
        os.remove(old)


def save(windows):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    latest = os.path.join(SNAPSHOT_DIR, "latest.json")

    try:
        with open(latest) as file:
            previous = json.load(file)
        previous_ids = claude_ids(previous["windows"])
        previous_saved = int(previous["saved"])
    except (OSError, ValueError, KeyError, TypeError):
        previous = None

    if previous and previous_ids != claude_ids(windows):
        archived = os.path.join(SNAPSHOT_DIR, "history-%d.json" % previous_saved)
        os.replace(latest, archived)
        prune_history()

    temporary = latest + ".tmp"
    with open(temporary, "w") as file:
        json.dump({"saved": time.time(), "windows": windows}, file, indent="\t")
    os.replace(temporary, latest)


async def main(connection):
    app = await iterm2.async_get_app(connection)
    while True:
        try:
            save(await collect(app))
        except Exception as error:
            print("claude-session-snapshot: %r" % error)
        await asyncio.sleep(INTERVAL_SECONDS)


iterm2.run_forever(main)
