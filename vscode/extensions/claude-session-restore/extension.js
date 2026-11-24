const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');
const { execFile } = require('child_process');

const SESSIONS_DIR = path.join(os.homedir(), '.claude', 'sessions');
const PROJECTS_DIR = path.join(os.homedir(), '.claude', 'projects');
const STATE_KEY = 'savedSessions';
const POLL_INTERVAL_MS = 5000;

// The session ID is typed into a shell, so anything that isn't a plain UUID is rejected.
const SESSION_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

// The folder is typed into a shell too, and a control character would act as a key like Enter
// that quoting can't neutralize.
const CONTROL_CHARACTER_PATTERN = /[\x00-\x1f\x7f]/;
const WORKTREE_NAME_PATTERN = /^[A-Za-z0-9._][A-Za-z0-9._\/-]*$/;

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

// Session ID -> transcript path, so the projects folder isn't searched again on every poll.
const transcripts = new Map();

// Session ID -> when its transcript was last searched for and not found. A new session has none
// until its first message, and searching every folder on every poll would block the host.
const missingTranscripts = new Map();
const MISSING_TRANSCRIPT_RETRY_MS = 30000;

// Session ID -> { since, delay, next, running } for searching other transcripts for a session's
// records. Each search reads whole transcripts, so it runs in the background, the delay between
// searches doubles, and only transcripts modified since the last one can hold new records.
const recordSearches = new Map();
const RECORD_SEARCH_MAX_DELAY_MS = 2 * 60 * 1000;
const UNKNOWN_START_LOOKBACK_MS = 14 * 24 * 60 * 60 * 1000;

// Only POSIX shells, because `shellQuote` isn't safe in shells like fish. This also rules out a
// program that replaced the shell with `exec`, which has the shell's PID and no children.
const SHELLS = new Set(['bash', 'zsh', 'sh']);

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

function clearCaches(sessionId) {
  transcripts.delete(sessionId);
  missingTranscripts.delete(sessionId);
  recordSearches.delete(sessionId);
}

function forget(sessionIds) {
  sessionIds.forEach(clearCaches);
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

// Claude Code names a transcript's folder after the folder the session was launched in.
function projectFolderName(folder) {
  return folder.replace(/[^a-zA-Z0-9]/g, '-');
}

function transcriptIdOf(transcript) {
  return path.basename(transcript, '.jsonl');
}

function modifiedTime(file) {
  try {
    return fs.statSync(file).mtimeMs;
  } catch (error) {
    return 0;
  }
}

// A session has no transcript until its first message, and `--resume` can't open it before then.
// The transcript is usually in the folder named after the session's current folder, so that's
// checked on every poll, and the slower searches are rate limited.
function hasTranscript(session) {
  const cached = transcripts.get(session.sessionId);
  if (cached && fs.existsSync(cached)) {
    return true;
  }
  transcripts.delete(session.sessionId);

  const likely = path.join(
    PROJECTS_DIR, projectFolderName(session.cwd), `${session.sessionId}.jsonl`
  );
  if (fs.existsSync(likely)) {
    transcripts.set(session.sessionId, likely);
    return true;
  }

  const lastMissed = missingTranscripts.get(session.sessionId) || 0;
  if (Date.now() - lastMissed < MISSING_TRANSCRIPT_RETRY_MS) {
    return false;
  }
  const [found] = findTranscripts(session.sessionId);
  if (found) {
    transcripts.set(session.sessionId, found);
    missingTranscripts.delete(session.sessionId);
    return true;
  }
  missingTranscripts.set(session.sessionId, Date.now());
  searchForRecords(session);
  return false;
}

// A session can write to another transcript without ever writing its own, like after `/clear`
// followed by `/resumebody`. Once one holds its records, the session can be resumed, and the
// restore works out which transcript to resume.
function searchForRecords(session) {
  const search = recordSearches.get(session.sessionId)
    || { since: session.startedAt, delay: MISSING_TRANSCRIPT_RETRY_MS, next: 0, running: false };
  if (search.running || Date.now() < search.next || !Number.isFinite(search.since)) {
    return;
  }
  const searchStarted = Date.now();
  const inProgress = { ...search, running: true };
  recordSearches.set(session.sessionId, inProgress);
  indexRecords(new Map([[session.sessionId, search.since]]))
    .then((index) => {
      // Forgotten while the search ran, like when its terminal closed.
      if (recordSearches.get(session.sessionId) !== inProgress) {
        return;
      }
      const [found] = index.has(session.sessionId) ? index.get(session.sessionId).keys() : [];
      if (found) {
        transcripts.set(session.sessionId, found);
        missingTranscripts.delete(session.sessionId);
        recordSearches.delete(session.sessionId);
        return;
      }
      recordSearches.set(session.sessionId, {
        since: searchStarted,
        delay: Math.min(search.delay * 2, RECORD_SEARCH_MAX_DELAY_MS),
        next: searchStarted + search.delay,
        running: false,
      });
    })
    .catch(() => recordSearches.delete(session.sessionId));
}

// Session ID -> transcript -> the time of the newest record that session wrote there, from every
// transcript modified since the earliest of `bounds` (session ID -> time). Records hold the ID
// of the session that wrote them as `session_id`, which can differ from the transcript's ID, like
// after `/clear` followed by `/resumebody`.
async function indexRecords(bounds) {
  const index = new Map();
  const finiteBounds = [...bounds.values()].filter(Number.isFinite);
  if (!finiteBounds.length) {
    return index;
  }
  const since = Math.min(...finiteBounds);

  let folders = [];
  try {
    folders = fs.readdirSync(PROJECTS_DIR);
  } catch (error) {
    return index;
  }
  for (const folder of folders) {
    let files = [];
    try {
      files = fs.readdirSync(path.join(PROJECTS_DIR, folder));
    } catch (error) {
      continue;
    }
    for (const file of files) {
      const transcript = path.join(PROJECTS_DIR, folder, file);
      const isTranscript = file.endsWith('.jsonl')
        && SESSION_ID_PATTERN.test(transcriptIdOf(transcript));
      if (isTranscript && modifiedTime(transcript) >= since) {
        await readRecords(transcript, bounds, index);
      }
    }
  }
  return index;
}

const RECORD_SESSION_PATTERN = /"session_id":"([0-9a-f-]{36})"/g;

async function readRecords(transcript, bounds, index) {
  const transcriptId = transcriptIdOf(transcript);
  const stream = fs.createReadStream(transcript, 'utf8');
  const lines = readline.createInterface({ input: stream, crlfDelay: Infinity });
  try {
    for await (const line of lines) {
      // Parsing every line of every recent transcript would be slow. Every match is checked,
      // because a nested object can hold a `session_id` ahead of the record's own.
      const mentionsSession = [...line.matchAll(RECORD_SESSION_PATTERN)]
        .some((match) => bounds.has(match[1]));
      if (!mentionsSession) {
        continue;
      }
      try {
        const entry = JSON.parse(line);
        const time = Date.parse(entry.timestamp);
        // An ID can be reused by a later process, like after `--resume`, and records from before
        // this session started belong to an earlier one.
        const isRecord = bounds.has(entry.session_id)
          && entry.sessionId === transcriptId
          && Number.isFinite(time)
          && time >= bounds.get(entry.session_id);
        if (!isRecord) {
          continue;
        }
        const sessionRecords = index.get(entry.session_id) || new Map();
        sessionRecords.set(transcript, Math.max(time, sessionRecords.get(transcript) || 0));
        index.set(entry.session_id, sessionRecords);
      } catch (error) {
        // A line that isn't JSON isn't a record.
      }
    }
  } catch (error) {
    // Unreadable, like when it was deleted mid-read.
  } finally {
    lines.close();
    stream.destroy();
  }
}

// The earliest time each session could have written a record, so `indexRecords` can skip older
// transcripts. A session saved without its start time is looked for over a fixed window.
function recordBounds(sessions) {
  const bounds = new Map();
  for (const session of sessions) {
    const startedAt = Number.isFinite(session.startedAt)
      ? session.startedAt
      : Date.now() - UNKNOWN_START_LOOKBACK_MS;
    bounds.set(session.sessionId, startedAt);
  }
  return bounds;
}

// The session's transcripts, best first. The best holds the session's newest record, because
// that's where its latest work is, and the session's own transcript wins a tie. The session's own
// transcript also counts as written when the file was, because a process started with `--resume`
// writes its records under a different `session_id`.
function rankTranscripts(sessionId, index) {
  const records = index.get(sessionId) || new Map();
  const own = findTranscripts(sessionId);
  const scored = own.map((transcript) => ({
    transcript,
    time: Math.max(records.get(transcript) || 0, modifiedTime(transcript)),
  }));
  for (const [transcript, time] of records) {
    if (!own.includes(transcript)) {
      scored.push({ transcript, time });
    }
  }
  // A stable sort keeps the session's own transcripts ahead of others with the same time.
  return scored
    .sort((first, second) => second.time - first.time)
    .map((item) => item.transcript);
}

// The IDs of the transcripts that live sessions are writing to, which `--resume` takes.
function liveTranscriptIds(sessions, index) {
  const ids = new Set();
  for (const session of sessions) {
    const [best] = rankTranscripts(session.sessionId, index);
    if (best) {
      ids.add(transcriptIdOf(best));
    }
  }
  return ids;
}

// Every transcript for the session, newest first. A session can have copies in several project
// folders, like when it was resumed from a different folder, and the newest has its latest state.
function findTranscripts(sessionId) {
  let folders = [];
  try {
    folders = fs.readdirSync(PROJECTS_DIR);
  } catch (error) {
    return [];
  }

  const found = [];
  for (const folder of folders) {
    const transcript = path.join(PROJECTS_DIR, folder, `${sessionId}.jsonl`);
    try {
      found.push({ transcript, modified: fs.statSync(transcript).mtimeMs });
    } catch (error) {
      // Not in this folder.
    }
  }
  return found
    .sort((first, second) => second.modified - first.modified)
    .map((item) => item.transcript);
}

// Returns the folder to resume the session from, the worktree to pass to `--worktree`, and the
// path of a worktree that can't be resumed automatically, so the user can check it by hand.
//
// `--resume` only finds a transcript from the folder the session was launched in, which the
// transcript's folder is named after. The candidates are the launch folder that the worktree
// record holds, the worktree itself, which Claude Code can move the transcript to when a session
// enters one, and the first `cwd` in the transcript and its parents.
//
// Resuming without `--worktree` takes the session out of its worktree, so the worktree from the
// last `worktree-state` record is passed along, the same as the command Claude Code prints on
// exit. `--worktree` only looks in `.claude/worktrees` under the folder Claude Code starts in,
// so a worktree anywhere else, like one in a nested repository, can't be passed.
//
// With `allowFallback`, the first `cwd` is used when no candidate matches.
async function readResumeTarget(transcript, allowFallback = true) {
  const { cwd, worktree } = await readTranscript(transcript);
  const folderName = path.basename(path.dirname(transcript));
  const validWorktree = worktree
    && typeof worktree.worktreeName === 'string'
    && WORKTREE_NAME_PATTERN.test(worktree.worktreeName)
    && typeof worktree.worktreePath === 'string'
    && path.isAbsolute(worktree.worktreePath)
    ? worktree
    : null;

  const candidates = [];
  if (validWorktree) {
    if (typeof validWorktree.originalCwd === 'string') {
      candidates.push(validWorktree.originalCwd);
    }
    candidates.push(validWorktree.worktreePath);
  }
  for (let candidate = cwd; candidate; candidate = path.dirname(candidate)) {
    candidates.push(candidate);
    if (candidate === path.dirname(candidate)) {
      break;
    }
  }
  const root = candidates.find(
    (candidate) => path.isAbsolute(candidate) && projectFolderName(candidate) === folderName
  ) || (allowFallback ? cwd : null);

  if (!validWorktree || !root || validWorktree.worktreePath === root) {
    return { root, worktreeName: null, lostWorktree: null };
  }
  const expectedPath = path.join(root, '.claude', 'worktrees', validWorktree.worktreeName);
  if (validWorktree.worktreePath === expectedPath && fs.existsSync(expectedPath)) {
    return { root, worktreeName: validWorktree.worktreeName, lostWorktree: null };
  }
  return { root, worktreeName: null, lostWorktree: validWorktree.worktreePath };
}

async function readTranscript(transcript) {
  let cwd = null;
  let worktree = null;
  const stream = fs.createReadStream(transcript, 'utf8');
  const lines = readline.createInterface({ input: stream, crlfDelay: Infinity });
  try {
    for await (const line of lines) {
      // Most lines hold neither, and parsing every line of a long transcript is slow.
      if (cwd && !line.includes('"worktree-state"')) {
        continue;
      }
      try {
        const entry = JSON.parse(line);
        if (!cwd && typeof entry.cwd === 'string' && path.isAbsolute(entry.cwd)) {
          cwd = entry.cwd;
        }
        if (entry.type === 'worktree-state') {
          worktree = entry.worktreeSession;
        }
      } catch (error) {
        // A line that isn't JSON can't hold either.
      }
    }
  } catch (error) {
    // Unreadable; the caller skips the session.
  } finally {
    lines.close();
    stream.destroy();
  }
  return { cwd, worktree };
}

function shellQuote(value) {
  return `'${value.replace(/'/g, `'\\''`)}'`;
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

    if (session && !hasTranscript(session)) {
      // Keep whatever this terminal had saved until the new session can be resumed.
      return;
    }

    if (session) {
      // VS Code reopens terminals in the same order after a restart, so the index finds the
      // reopened terminal that this session should resume in.
      const entry = {
        sessionId: session.sessionId,
        name: session.name || '',
        terminalIndex: index,
      };
      // The restore only looks for the session's records in transcripts written since then.
      if (Number.isFinite(session.startedAt)) {
        entry.startedAt = session.startedAt;
      }

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
      if (previousId && previousId !== session.sessionId) {
        clearCaches(previousId);
      }
      tracked.set(terminal, { sessionId: session.sessionId, misses: 0 });
    } else if (previous) {
      // Claude exited, but the terminal is still open.
      previous.misses++;
      if (previous.misses >= MISSES_BEFORE_FORGETTING) {
        saved = saved.filter((item) => item.sessionId !== previous.sessionId);
        clearCaches(previous.sessionId);
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

// Terminal index -> terminal, for terminals whose shell isn't running anything. Those are the
// ones VS Code reopened after a restart, with fresh shells in place of the sessions. A terminal
// someone has typed in is left alone, since the command would be appended to whatever's there.
async function findIdleTerminals(processes) {
  const terminals = vscode.window.terminals;
  const shellPids = await Promise.all(terminals.map((terminal) => terminal.processId));
  const busyShells = new Set([...processes.values()].map((processInfo) => processInfo.ppid));

  const idle = new Map();
  terminals.forEach((terminal, index) => {
    const shell = processes.get(shellPids[index]);
    const isIdleShell = shell
      && SHELLS.has(path.basename(shell.command).replace(/^-/, ''))
      && !busyShells.has(shellPids[index]);

    if (isIdleShell && !terminal.state.isInteractedWith && !tracked.has(terminal)) {
      idle.set(index, terminal);
    }
  });
  return idle;
}

async function restore() {
  const processes = await listProcesses();
  const liveSessions = readLiveSessions(processes);
  const running = new Set(liveSessions.map((session) => session.sessionId));
  const toRestore = getSaved().filter(
    (session) => !running.has(session.sessionId) && !restored.has(session.sessionId)
  );

  if (!toRestore.length) {
    vscode.window.showInformationMessage('There are no saved Claude sessions to restore.');
    return;
  }

  // Claimed before anything is awaited, so running Restore again meanwhile can't pick them up.
  toRestore.forEach((session) => restored.add(session.sessionId));

  // One pass over the recent transcripts finds where the saved and live sessions last wrote.
  const index = await indexRecords(recordBounds([...toRestore, ...liveSessions]));
  const targets = await Promise.all(toRestore.map((session) => resolveTarget(session, index)));
  const ready = targets.filter((target) => target.root);
  const skipped = targets.filter((target) => !target.root).map((target) => target.session);
  skipped.forEach((session) => restored.delete(session.sessionId));

  // Checked after reading the transcripts, which can take seconds, and again right before
  // typing, so text someone starts typing meanwhile isn't run with the command appended.
  const currentProcesses = await listProcesses();
  const idleTerminals = await findIdleTerminals(currentProcesses);
  const liveNow = readLiveSessions(currentProcesses);
  const resumedMeanwhile = new Set(liveNow.map((liveSession) => liveSession.sessionId));
  const transcriptsInUse = liveTranscriptIds(liveNow, index);
  for (const { session, transcriptId, root, worktreeName } of ready) {
    if (resumedMeanwhile.has(session.sessionId)) {
      continue;
    }
    if (transcriptsInUse.has(transcriptId)) {
      // The poll saves the session that's writing it in its own slot.
      if (transcriptId !== session.sessionId) {
        await forget([session.sessionId]);
      }
      continue;
    }
    // Two saved sessions can lead to the same transcript, which only one process should resume.
    transcriptsInUse.add(transcriptId);
    const worktreeOption = worktreeName ? `--worktree ${shellQuote(worktreeName)} ` : '';
    const command = `claude ${worktreeOption}--resume ${transcriptId}`;
    const reopened = idleTerminals.get(session.terminalIndex);
    if (reopened && !reopened.state.isInteractedWith) {
      idleTerminals.delete(session.terminalIndex);
      reopened.sendText(`cd ${shellQuote(root)} && ${command}`);
    } else {
      const name = session.name || 'claude';
      vscode.window.createTerminal({ name, cwd: root }).sendText(command);
    }
    setTimeout(() => forgetIfNotResumed(session.sessionId), RESUME_TIMEOUT_MS);
  }

  const lostWorktrees = ready.filter((target) => target.lostWorktree);
  if (lostWorktrees.length) {
    const details = lostWorktrees
      .map((target) => `${target.session.name || target.session.sessionId}: ${target.lostWorktree}`)
      .join('\n');
    vscode.window.showWarningMessage(
      'These sessions were resumed outside the worktree they were in. Check each worktree for '
        + 'uncommitted work before continuing in the session.',
      { modal: true, detail: details }
    );
  }

  if (skipped.length) {
    await forget(skipped.map((session) => session.sessionId));
    const names = skipped.map((session) => session.name || session.sessionId).join(', ');
    vscode.window.showWarningMessage(
      `These sessions couldn't be restored, so they were removed: ${names}`
    );
  }
}

// Finds a usable folder to resume the session's best transcript from. Among copies of that
// transcript, one whose folder name matches a candidate is preferred over guessing from the first
// `cwd` of a newer one. Other transcripts are older work, so they're never resumed in its place.
async function resolveTarget(session, index) {
  // Checked again here, because saved state from an older version could hold anything.
  if (!SESSION_ID_PATTERN.test(session.sessionId)) {
    return { session, root: null };
  }
  const ranked = rankTranscripts(session.sessionId, index);
  if (!ranked.length) {
    return { session, root: null };
  }
  const transcriptId = transcriptIdOf(ranked[0]);
  const copies = ranked.filter((transcript) => transcriptIdOf(transcript) === transcriptId);
  for (const allowFallback of [false, true]) {
    for (const transcript of copies) {
      const target = await readResumeTarget(transcript, allowFallback);
      const isUsable = target.root
        && fs.existsSync(target.root)
        && !CONTROL_CHARACTER_PATTERN.test(target.root);
      if (isUsable) {
        return { session, transcriptId, ...target };
      }
    }
  }
  return { session, root: null };
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
