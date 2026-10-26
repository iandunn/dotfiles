const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');

// Claude Code keeps a file per running session here, and keeps its `status` field current:
// `busy` while it works, `waiting` while a prompt or dialog needs an answer, and `idle`
// otherwise. That covers interrupts and failed tools, which no hook reports. The format is
// internal to Claude Code, though, so a release could change it.
const SESSIONS_DIR = path.join(os.homedir(), '.claude', 'sessions');

const POLL_INTERVAL_MS = 1000;
const PROCESS_ID_TIMEOUT_MS = 2000;

const SESSION_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const STATUS_COLORS = {
  busy: 'charts.orange',
  waiting: 'charts.red',
  idle: 'charts.green',
};

// Far left of the status bar, so the dots don't push the other items around as sessions come
// and go.
const BASE_PRIORITY = 10000;

let dots = [];
let items = [];
let refreshing = false;
let refreshAgain = false;
let disposed = false;

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

// A terminal that's still starting, or reconnecting after a reload, can take a while to report
// its process, and one that never does mustn't stall every refresh after it.
function processIdOf(terminal) {
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve(undefined), PROCESS_ID_TIMEOUT_MS);
  });
  return Promise.race([terminal.processId, timeout]).finally(() => clearTimeout(timer));
}

function isClaudeProcess(pid, processes) {
  const processInfo = processes.get(pid);
  return Boolean(processInfo) && path.basename(processInfo.command) === 'claude';
}

// Files from sessions that crashed are left behind and never cleaned up, so only files named
// after a live `claude` process are read.
function readLiveSessions(processes) {
  let files = [];
  try {
    files = fs.readdirSync(SESSIONS_DIR).filter((file) => /^\d+\.json$/.test(file));
  } catch (error) {
    return [];
  }

  const sessions = [];
  for (const file of files) {
    if (!isClaudeProcess(Number(file.slice(0, -'.json'.length)), processes)) {
      continue;
    }
    try {
      const session = JSON.parse(fs.readFileSync(path.join(SESSIONS_DIR, file), 'utf8'));
      const isValid = Number.isInteger(session.pid)
        && SESSION_ID_PATTERN.test(session.sessionId)
        && session.kind === 'interactive';

      if (isValid && isClaudeProcess(session.pid, processes)) {
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

async function buildDots() {
  const terminals = vscode.window.terminals;
  if (!terminals.length) {
    return [];
  }
  const shellPids = await Promise.all(terminals.map(processIdOf));
  const processes = await listProcesses();
  const shellPidSet = new Set(shellPids.filter(Boolean));

  const sessionsByShell = new Map();
  for (const session of readLiveSessions(processes)) {
    const shellPid = findShellPid(session.pid, processes, shellPidSet);
    // A shell can hold more than one session, like one suspended with Ctrl-Z, and the newest
    // is the one in the foreground.
    const existing = sessionsByShell.get(shellPid);
    if (shellPid && (!existing || session.startedAt > existing.startedAt)) {
      sessionsByShell.set(shellPid, session);
    }
  }

  const result = [];
  terminals.forEach((terminal, index) => {
    const session = shellPids[index] && sessionsByShell.get(shellPids[index]);
    if (session) {
      result.push({
        terminal,
        name: session.name || terminal.name,
        status: Object.hasOwn(STATUS_COLORS, session.status) ? session.status : 'unknown',
        waitingFor: session.waitingFor,
        active: terminal === vscode.window.activeTerminal,
      });
    }
  });
  return result;
}

function describe(dot) {
  if (dot.status === 'waiting') {
    return `${dot.name} (waiting: ${dot.waitingFor || 'input'})`;
  }
  return dot.status === 'unknown' ? dot.name : `${dot.name} (${dot.status})`;
}

// Status bar items can't be reordered after they're created, so they're rebuilt whenever
// anything changes, which is rare enough that the churn doesn't matter.
function render() {
  items.forEach((item) => item.dispose());
  items = dots.map((dot, index) => {
    const item = vscode.window.createStatusBarItem(
      `claudeTerminalStatus.${index}`,
      vscode.StatusBarAlignment.Left,
      BASE_PRIORITY - index
    );
    item.name = 'Claude Session';

    // The active terminal gets a ringed dot, whatever its state.
    if (dot.active) {
      item.text = '$(record)';
    } else {
      item.text = dot.status === 'unknown' ? '$(circle-outline)' : '$(circle-filled)';
    }
    if (Object.hasOwn(STATUS_COLORS, dot.status)) {
      item.color = new vscode.ThemeColor(STATUS_COLORS[dot.status]);
    }
    item.tooltip = describe(dot);
    item.command = {
      command: 'claudeTerminalStatus.show',
      title: 'Show Terminal',
      arguments: [dot.terminal],
    };
    item.show();
    return item;
  });
}

// A refresh requested while one is running is run once afterward, so the last change is never
// dropped.
async function refresh() {
  if (refreshing) {
    refreshAgain = true;
    return;
  }
  refreshing = true;
  try {
    do {
      refreshAgain = false;
      const next = await buildDots();
      const changed = next.length !== dots.length || next.some((dot, index) => (
        dot.terminal !== dots[index].terminal
        || dot.name !== dots[index].name
        || dot.status !== dots[index].status
        || dot.waitingFor !== dots[index].waitingFor
        || dot.active !== dots[index].active
      ));
      dots = next;
      if (changed && !disposed) {
        render();
      }
    } while (refreshAgain);
  } catch (error) {
    console.error('claude-terminal-status: refresh failed', error);
  } finally {
    refreshing = false;
  }
}

function activate(context) {
  const timer = setInterval(refresh, POLL_INTERVAL_MS);

  context.subscriptions.push(
    { dispose: () => clearInterval(timer) },
    {
      dispose: () => {
        disposed = true;
        items.forEach((item) => item.dispose());
      },
    },
    vscode.commands.registerCommand('claudeTerminalStatus.show', (terminal) => {
      // A dot can outlive its terminal by up to a poll.
      if (vscode.window.terminals.includes(terminal)) {
        terminal.show();
      }
    }),
    vscode.window.onDidOpenTerminal(() => refresh()),
    vscode.window.onDidCloseTerminal(() => refresh()),
    vscode.window.onDidChangeActiveTerminal(() => refresh())
  );

  refresh();
}

function deactivate() {}

module.exports = { activate, deactivate };
