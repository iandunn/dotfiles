#!/usr/bin/env node

/*
 * UserPromptSubmit hook: injects the current VS Code window's open editor tabs
 * into context so any Claude Code instance can resolve "this file" and fuzzy
 * tab references, without needing the single per-window IDE socket.
 *
 * Reads the per-workspace state written by the "claude-active-tab-informer"
 * VS Code extension (~/dotfiles/vscode/extensions/claude-active-tab-informer).
 * Matches the window whose workspace root contains this session's cwd.
 * See ~/dotfiles/vscode/extensions/claude-active-tab-informer/extension.js.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const STATE_DIR = process.env.CLAUDE_ACTIVE_VSCODE_TABS_DIR || path.join(os.homedir(), '.claude', 'active-vscode-tabs');

function loadStates() {
  let files;
  try {
    files = fs.readdirSync(STATE_DIR).filter((f) => f.endsWith('.json'));
  } catch (error) {
    return [];
  }

  const states = [];
  for (const file of files) {
    try {
      states.push(JSON.parse(fs.readFileSync(path.join(STATE_DIR, file), 'utf8')));
    } catch (error) {
      // Skip unreadable/partial files.
    }
  }
  return states;
}

// Pick the window whose workspace root contains cwd; prefer the most specific
// (longest) root when workspaces are nested.
function pickState(states, cwd) {
  const matches = states.filter(
    (state) =>
      state.workspaceRoot &&
      (cwd === state.workspaceRoot || cwd.startsWith(state.workspaceRoot + path.sep))
  );
  matches.sort((a, b) => b.workspaceRoot.length - a.workspaceRoot.length);
  return matches[0] || null;
}

function buildContext(state) {
  const lines = [];
  lines.push('VS Code editor state for this workspace (' + state.workspaceRoot + '):');
  if (state.active) {
    lines.push('- Active tab (use this for "this file" / "the active file"): ' + state.active);
  }
  if (state.tabs && state.tabs.length) {
    lines.push('- Open tabs:');
    for (const tab of state.tabs) {
      lines.push('    ' + tab);
    }
  }
  lines.push('');
  lines.push(
    'When the user refers to a file by a short or fuzzy name (e.g. "sec review", ' +
      '"dast response"), match it against the open tabs above; if the match is ' +
      'ambiguous, ask. When you resolve such a reference, you may briefly remind the ' +
      'user - not every turn - that they can use @ to reference any file in the ' +
      'project (e.g. @path/to/file, or @file#L10-20 for a line range), not just ' +
      'files currently open in tabs.'
  );
  return lines.join('\n');
}

function emit(additionalContext) {
  if (additionalContext) {
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'UserPromptSubmit',
          additionalContext,
        },
      })
    );
  }
  process.exit(0);
}

let input = '';
process.stdin.on('data', (chunk) => {
  input += chunk;
});
process.stdin.on('end', () => {
  let cwd = process.cwd();
  try {
    const data = JSON.parse(input);
    if (data && typeof data.cwd === 'string') {
      cwd = data.cwd;
    }
  } catch (error) {
    // Fall back to process.cwd().
  }

  const state = pickState(loadStates(), cwd);
  if (!state) {
    emit(null);
    return;
  }
  emit(buildContext(state));
});
