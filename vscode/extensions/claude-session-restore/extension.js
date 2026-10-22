const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');

const SESSIONS_DIR = path.join(os.homedir(), '.claude', 'sessions');
const STATE_KEY = 'savedSessions';
const POLL_INTERVAL_MS = 5000;

// The session ID is typed into a shell, so anything that isn't a plain UUID is rejected.
const SESSION_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

// Quitting VS Code kills every terminal, and the snapshot has to survive that. So a session is
// only forgotten when it's gone for longer than a shutdown takes, which the extension host
// never lives long enough to see.
const MISSES_BEFORE_FORGETTING = 2;
const CLOSE_GRACE_MS = 5000;

// A resume that hasn't started by then failed, like when its transcript was deleted, so the
// session is forgotten rather than reopened as a dead terminal on every restart.
const RESUME_TIMEOUT_MS = 60000;

// Terminal -> { sessionId, misses } for terminals seen running Claude in this window.
const tracked = new Map();

// Sessions this window already reopened, so a second Restore doesn't open them twice before
// they've written their own session files.
const restored = new Set();

let workspaceState = null;
let polling = false;

function getSaved() {
  return workspaceState.get(STATE_KEY, []);
}

function setSaved(sessions) {
  if (JSON.stringify(sessions) === JSON.stringify(getSaved())) {
    return Promise.resolve();
  }
  return workspaceState.update(STATE_KEY, sessions);
}

function forget(sessionIds) {
  const remaining = getSaved().filter((session) => !sessionIds.includes(session.sessionId));
  return setSaved(remaining);
}

function listProcesses() {
  return new Promise((resolve) => {
    execFile('ps', ['-axo', 'pid=,ppid=,comm='], (error, stdout) => {
      const processes = new Map();
      if (error) {
        resolve(processes);
        return;
      }
      for (const line of stdout.split('\n')) {
        const match = line.trim().match(/^(\d+)\s+(\d+)\s+(.+)$/);
        if (match) {
          processes.set(Number(match[1]), { ppid: Number(match[2]), command: match[3] });
        }
      }
      resolve(processes);
    });
  });
}

// Claude Code keeps a file per running session in `~/.claude/sessions`. Files from sessions
// that crashed are left behind, so the PID has to still belong to a `claude` process.
function readLiveSessions(processes) {
  let files = [];
  try {
    files = fs.readdirSync(SESSIONS_DIR).filter((file) => file.endsWith('.json'));
  } catch (error) {
    return [];
  }

  const sessions = [];
  for (const file of files) {
    try {
      const session = JSON.parse(fs.readFileSync(path.join(SESSIONS_DIR, file), 'utf8'));
      const processInfo = processes.get(session.pid);
      const isValid = Number.isInteger(session.pid)
        && SESSION_ID_PATTERN.test(session.sessionId)
        && typeof session.cwd === 'string'
        && session.kind === 'interactive';

      if (isValid && processInfo && path.basename(processInfo.command) === 'claude') {
        sessions.push(session);
      }
    } catch (error) {
      // Half-written or unreadable; the next poll will pick it up.
    }
  }
  return sessions;
}

// `claude` is normally a direct child of the terminal's shell, but this allows for a wrapper,
// or for `exec claude` replacing the shell outright.
function findShellPid(pid, processes, shellPids) {
  if (shellPids.has(pid)) {
    return pid;
  }
  let current = processes.get(pid);
  for (let depth = 0; current && depth < 5; depth++) {
    if (shellPids.has(current.ppid)) {
      return current.ppid;
    }
    current = processes.get(current.ppid);
  }
  return null;
}

async function poll() {
  const terminals = vscode.window.terminals;
  if (!terminals.length) {
    return;
  }
  const shellPids = await Promise.all(terminals.map((terminal) => terminal.processId));
  const processes = await listProcesses();
  const shellPidSet = new Set(shellPids);

  const sessionsByShell = new Map();
  for (const session of readLiveSessions(processes)) {
    const shellPid = findShellPid(session.pid, processes, shellPidSet);
    if (shellPid) {
      sessionsByShell.set(shellPid, session);
    }
  }

  // Terminals that closed while this poll was waiting are handled by `onDidCloseTerminal`.
  const openTerminals = new Set(vscode.window.terminals);

  let saved = [...getSaved()];
  terminals.forEach((terminal, index) => {
    if (!openTerminals.has(terminal)) {
      return;
    }

    const session = sessionsByShell.get(shellPids[index]);
    const previous = tracked.get(terminal);

    if (session) {
      const entry = { sessionId: session.sessionId, cwd: session.cwd, name: session.name || '' };

      // `/clear` starts a new session ID in the same terminal, so it takes over the old slot.
      const previousId = previous ? previous.sessionId : null;
      const position = saved.findIndex(
        (item) => item.sessionId === session.sessionId || item.sessionId === previousId
      );
      if (position === -1) {
        saved.push(entry);
      } else {
        saved[position] = entry;
      }
      tracked.set(terminal, { sessionId: session.sessionId, misses: 0 });
    } else if (previous) {
      // Claude exited, but the terminal is still open.
      previous.misses++;
      if (previous.misses >= MISSES_BEFORE_FORGETTING) {
        saved = saved.filter((item) => item.sessionId !== previous.sessionId);
        tracked.delete(terminal);
      }
    }
  });

  await setSaved(saved);
}

async function pollOnce() {
  if (polling) {
    return;
  }
  polling = true;
  try {
    await poll();
  } catch (error) {
    console.error('claude-session-restore: poll failed', error);
  } finally {
    polling = false;
  }
}

async function forgetIfNotResumed(sessionId) {
  restored.delete(sessionId);
  const processes = await listProcesses();
  const isRunning = readLiveSessions(processes).some((session) => session.sessionId === sessionId);
  if (!isRunning) {
    await forget([sessionId]);
  }
}

async function restore() {
  const processes = await listProcesses();
  const running = new Set(readLiveSessions(processes).map((session) => session.sessionId));
  const toRestore = getSaved().filter(
    (session) => !running.has(session.sessionId) && !restored.has(session.sessionId)
  );

  if (!toRestore.length) {
    vscode.window.showInformationMessage('There are no saved Claude sessions to restore.');
    return;
  }

  const skipped = [];
  for (const session of toRestore) {
    // Checked again here, because saved state from an older version could hold anything.
    if (!SESSION_ID_PATTERN.test(session.sessionId)) {
      skipped.push(session);
      continue;
    }

    // A worktree that was cleaned up has no folder to resume in.
    if (!fs.existsSync(session.cwd)) {
      skipped.push(session);
      continue;
    }

    restored.add(session.sessionId);
    const name = session.name || 'claude';
    const terminal = vscode.window.createTerminal({ name, cwd: session.cwd });
    terminal.sendText(`claude --resume ${session.sessionId}`);
    setTimeout(() => forgetIfNotResumed(session.sessionId), RESUME_TIMEOUT_MS);
  }

  if (skipped.length) {
    await forget(skipped.map((session) => session.sessionId));
    const names = skipped.map((session) => session.name || session.sessionId).join(', ');
    vscode.window.showWarningMessage(
      `These sessions couldn't be restored, so they were removed: ${names}`
    );
  }
}

function activate(context) {
  workspaceState = context.workspaceState;

  const timer = setInterval(pollOnce, POLL_INTERVAL_MS);

  context.subscriptions.push(
    { dispose: () => clearInterval(timer) },
    vscode.commands.registerCommand('claudeSessionRestore.restore', restore),
    vscode.window.onDidCloseTerminal((terminal) => {
      const previous = tracked.get(terminal);
      tracked.delete(terminal);
      if (previous) {
        setTimeout(() => forget([previous.sessionId]), CLOSE_GRACE_MS);
      }
    })
  );

  pollOnce();
}

function deactivate() {}

module.exports = { activate, deactivate };
