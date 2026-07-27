#!/usr/bin/env python3
"""
Tests for worktree-command-permissions.py.
Run with: python3 test-worktree-command-permissions.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'worktree-command-permissions.py'
ALLOW = 'allow'
ASK = 'ask'


def run(command, cwd=None):
    """Run the hook with a command string, return (stdout, returncode)."""
    payload = {'tool_input': {'command': command}}
    if cwd is not None:
        payload['cwd'] = cwd
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip(), result.returncode


def decision(stdout):
    """Parse the permissionDecision from hook output, or None if no output."""
    if not stdout:
        return None
    return json.loads(stdout)['hookSpecificOutput']['permissionDecision']


class WorktreeRemoveTest(unittest.TestCase):

    def assertDecision(self, expected, command):
        out, code = run(command)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')

    def test_plain_remove_allowed(self):
        self.assertDecision(ALLOW, 'git worktree remove .worktrees/feature')

    def test_absolute_path_allowed(self):
        self.assertDecision(ALLOW, 'git worktree remove /Users/x/repo/.worktrees/feature')

    def test_extra_whitespace_allowed(self):
        self.assertDecision(ALLOW, 'git  worktree   remove  .worktrees/feature')

    def test_long_force_asks(self):
        self.assertDecision(ASK, 'git worktree remove --force .worktrees/feature')

    def test_short_force_asks(self):
        self.assertDecision(ASK, 'git worktree remove -f .worktrees/feature')

    def test_force_after_path_asks(self):
        self.assertDecision(ASK, 'git worktree remove .worktrees/feature --force')

    def test_doubled_force_asks(self):
        self.assertDecision(ASK, 'git worktree remove -f -f .worktrees/feature')

    def test_clustered_force_asks(self):
        """Short-flag clusters must be inspected, not compared whole."""
        self.assertDecision(ASK, 'git worktree remove -vf .worktrees/feature')

    def test_unbalanced_quotes_ask(self):
        """An unparseable command must fall back to a prompt, never an allow."""
        self.assertDecision(ASK, 'git worktree remove "unclosed')

    def test_force_inside_path_is_not_a_flag(self):
        """A path merely containing 'force' is not a force flag."""
        self.assertDecision(ALLOW, 'git worktree remove .worktrees/force-refactor')

    def test_worktree_add_not_gated(self):
        """Only `remove` is handled here; `add` falls through to settings rules."""
        out, code = run('git worktree add -b x .worktrees/x')
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))

    def test_worktree_list_not_gated(self):
        out, code = run('git worktree list')
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))


class CpAndNpmTest(unittest.TestCase):
    """The cwd-based gate: allowed only inside a linked worktree."""

    def test_cp_in_main_checkout_asks(self):
        out, _ = run('cp a b', cwd=str(Path(__file__).parent))
        self.assertEqual(decision(out), ASK)

    def test_cp_outside_repo_asks(self):
        out, _ = run('cp a b', cwd='/tmp')
        self.assertEqual(decision(out), ASK)

    def test_unrelated_command_not_gated(self):
        out, code = run('ls -la')
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))


if __name__ == '__main__':
    unittest.main()
