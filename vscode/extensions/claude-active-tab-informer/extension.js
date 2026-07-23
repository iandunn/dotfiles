const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const OUTPUT_DIR = path.join(os.homedir(), '.claude', 'active-vscode-tabs');

function getWorkspaceRoot() {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length ? folders[0].uri.fsPath : null;
}

// Only on-disk files; ignore diffs, webviews, untitled buffers, etc.
function getFilePath(tabInput) {
  if (tabInput && tabInput.uri && tabInput.uri.scheme === 'file') {
    return tabInput.uri.fsPath;
  }
  return null;
}

function collectState() {
  const workspaceRoot = getWorkspaceRoot();
  if (!workspaceRoot) {
    return null;
  }

  const tabs = [];
  for (const group of vscode.window.tabGroups.all) {
    for (const tab of group.tabs) {
      const filePath = getFilePath(tab.input);
      if (filePath && !tabs.includes(filePath)) {
        tabs.push(filePath);
      }
    }
  }

  const activeGroup = vscode.window.tabGroups.activeTabGroup;
  const activeTab = activeGroup ? activeGroup.activeTab : null;
  const active = activeTab ? getFilePath(activeTab.input) : null;

  return { workspaceRoot, active, tabs, updated: Date.now() };
}

// Filename is a stable hash of the workspace root; the hook matches by the
// workspaceRoot field inside, not by this name.
function stateFileFor(workspaceRoot) {
  const hash = crypto.createHash('md5').update(workspaceRoot).digest('hex').slice(0, 16);
  return path.join(OUTPUT_DIR, hash + '.json');
}

let writeTimer = null;
function scheduleWrite() {
  if (writeTimer) {
    clearTimeout(writeTimer);
  }
  writeTimer = setTimeout(writeState, 100);
}

function writeState() {
  const state = collectState();
  if (!state) {
    return;
  }
  try {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    fs.writeFileSync(stateFileFor(state.workspaceRoot), JSON.stringify(state), 'utf8');
  } catch (error) {
    console.error('claude-active-tab-informer: failed to write state', error);
  }
}

function removeState() {
  const workspaceRoot = getWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  try {
    fs.unlinkSync(stateFileFor(workspaceRoot));
  } catch (error) {
    // Already gone, or never written; nothing to do.
  }
}

function activate(context) {
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(scheduleWrite),
    vscode.window.tabGroups.onDidChangeTabs(scheduleWrite),
    vscode.workspace.onDidChangeWorkspaceFolders(scheduleWrite)
  );
  writeState();
}

function deactivate() {
  removeState();
}

module.exports = { activate, deactivate };
