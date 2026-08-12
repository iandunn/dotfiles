#!/usr/bin/env python3
"""
Tests for worktree-command-permissions.py.
Run with: python3 test-worktree-command-permissions.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


class CpTest(unittest.TestCase):
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

    def test_npm_install_no_longer_gated(self):
        """npm install stays on its settings.json ask rule, not this hook."""
        out, code = run('npm install lodash', cwd='/tmp')
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))


def git(cwd, *args):
    subprocess.run(
        ['git', '-c', 'commit.gpgsign=false', *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )


class LinkedWorktreeTest(unittest.TestCase):
    """Exercises the allow paths against real linked worktrees, not stubs."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='worktree-hook-test-')
        cls.main_tree = os.path.join(cls.temp, 'repo')
        cls.worktree = os.path.join(cls.main_tree, '.claude', 'worktrees', 'feature')
        cls.rogue_worktree = os.path.join(cls.temp, 'rogue')
        cls.outside = os.path.join(cls.temp, 'outside.txt')

        os.makedirs(cls.main_tree)
        Path(cls.outside).write_text('not ours\n')
        git(cls.main_tree, 'init', '-b', 'main')
        git(cls.main_tree, 'config', 'user.email', 'test@example.com')
        git(cls.main_tree, 'config', 'user.name', 'Test')
        Path(cls.main_tree, 'tracked.txt').write_text('hello\n')
        git(cls.main_tree, 'add', 'tracked.txt')
        git(cls.main_tree, 'commit', '-m', 'initial')
        os.makedirs(os.path.dirname(cls.worktree))
        git(cls.main_tree, 'worktree', 'add', cls.worktree, '-b', 'feature')
        # A linked worktree OUTSIDE .claude/worktrees/, like one made by hand.
        git(cls.main_tree, 'worktree', 'add', cls.rogue_worktree, '-b', 'rogue')

        Path(cls.worktree, 'a.log').write_text('tracked log\n')
        os.symlink(cls.outside, os.path.join(cls.worktree, 'link-out'))
        git(cls.worktree, 'add', 'a.log', 'link-out')
        Path(cls.worktree, 'untracked-scratch.txt').write_text('only copy\n')
        Path(cls.worktree, 'b.tmp').write_text('untracked\n')
        os.symlink(cls.temp, os.path.join(cls.worktree, 'dir-out'))

        os.mkdir(os.path.join(cls.worktree, 'sub'))
        Path(cls.worktree, 'sub', 'collide.txt').write_text('untracked, in the way\n')
        Path(cls.worktree, 'collide.txt').write_text('wants to land on the above\n')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp, ignore_errors=True)

    def assertInWorktree(self, expected, command):
        out, code = run(command, cwd=self.worktree)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')

    def assertInMainTree(self, expected, command):
        out, code = run(command, cwd=self.main_tree)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')

    def assertInRogueWorktree(self, expected, command):
        out, code = run(command, cwd=self.rogue_worktree)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')

    def test_cp_in_worktree_allowed(self):
        self.assertInWorktree(ALLOW, 'cp tracked.txt copy.txt')

    def test_git_add_in_worktree_allowed(self):
        self.assertInWorktree(ALLOW, 'git add tracked.txt')

    def test_git_commit_in_worktree_allowed(self):
        self.assertInWorktree(ALLOW, 'git commit -m "wip"')

    def test_git_add_in_main_tree_asks(self):
        self.assertInMainTree(ASK, 'git add tracked.txt')

    def test_git_commit_in_main_tree_asks(self):
        self.assertInMainTree(ASK, 'git commit -m "wip"')

    def test_git_add_retargeted_with_dash_c_asks(self):
        """-C would stage in another tree while cwd still looks like a worktree."""
        self.assertInWorktree(ASK, f'git -C {self.main_tree} add tracked.txt')

    def test_git_commit_retargeted_with_git_dir_asks(self):
        self.assertInWorktree(ASK, f'git --git-dir={self.main_tree}/.git commit -m x')

    def test_git_commit_with_config_override_asks(self):
        self.assertInWorktree(ASK, 'git -c core.hooksPath=/tmp/evil commit -m x')

    def test_git_commit_tree_not_gated(self):
        """`commit-tree` is a different subcommand and must not match `commit`."""
        out, code = run('git commit-tree abc123', cwd=self.worktree)
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))

    def test_git_status_not_gated(self):
        out, code = run('git status', cwd=self.worktree)
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))

    def test_rm_relative_tracked_file_allowed(self):
        self.assertInWorktree(ALLOW, 'rm tracked.txt')

    def test_rm_absolute_tracked_file_allowed(self):
        self.assertInWorktree(ALLOW, f'rm {self.worktree}/tracked.txt')

    def test_rm_glob_of_tracked_files_allowed(self):
        """The hook expands the glob itself and checks every match."""
        self.assertInWorktree(ALLOW, 'rm *.log')

    def test_rm_after_double_dash_allowed(self):
        self.assertInWorktree(ALLOW, 'rm -- tracked.txt')

    def test_rm_with_command_prefix_allowed(self):
        """CLAUDE.md uses `command rm` to bypass the `rm -i` alias."""
        self.assertInWorktree(ALLOW, 'command rm tracked.txt')

    def test_rm_tracked_symlink_allowed(self):
        """Deleting a link removes the link, not its target, so containment holds."""
        self.assertInWorktree(ALLOW, 'rm link-out')

    def test_rm_untracked_file_asks(self):
        """An untracked file is the only copy of that work; git cannot restore it."""
        self.assertInWorktree(ASK, 'rm untracked-scratch.txt')

    def test_rm_glob_matching_untracked_asks(self):
        self.assertInWorktree(ASK, 'rm *.tmp')

    def test_rm_glob_matching_nothing_asks(self):
        """bash passes an unmatched pattern through literally, so the hook cannot verify it."""
        self.assertInWorktree(ASK, 'rm *.nope')

    def test_rm_mixed_tracked_and_untracked_asks(self):
        self.assertInWorktree(ASK, 'rm tracked.txt untracked-scratch.txt')

    def test_rm_in_main_tree_asks(self):
        self.assertInMainTree(ASK, 'rm tracked.txt')

    def test_rm_in_rogue_worktree_asks(self):
        """Linked worktrees outside .claude/worktrees/ are not sanctioned."""
        self.assertInRogueWorktree(ASK, 'rm tracked.txt')

    def test_git_add_in_rogue_worktree_asks(self):
        self.assertInRogueWorktree(ASK, 'git add tracked.txt')

    def test_cp_in_rogue_worktree_asks(self):
        self.assertInRogueWorktree(ASK, 'cp tracked.txt copy.txt')

    def test_rm_parent_traversal_asks(self):
        self.assertInWorktree(ASK, 'rm ../outside.txt')

    def test_rm_absolute_path_outside_asks(self):
        self.assertInWorktree(ASK, f'rm {self.outside}')

    def test_rm_through_symlinked_directory_asks(self):
        """A contained-looking parent that is a link out must not pass."""
        self.assertInWorktree(ASK, 'rm dir-out/outside.txt')

    def test_rm_recursive_asks(self):
        self.assertInWorktree(ASK, 'rm -rf subdir')

    def test_rm_empty_dir_flag_asks(self):
        """`rm -d` is `rmdir`, which settings.json denies outright."""
        self.assertInWorktree(ASK, 'rm -d subdir')

    def test_rm_command_substitution_asks(self):
        self.assertInWorktree(ASK, 'rm $(cat targets.txt)')

    def test_rm_tilde_expansion_asks(self):
        self.assertInWorktree(ASK, 'rm ~/inside.txt')

    def test_rm_without_operands_asks(self):
        self.assertInWorktree(ASK, 'rm -f')

    def test_rm_unbalanced_quotes_asks(self):
        self.assertInWorktree(ASK, 'rm "unclosed')

    def test_mv_rename_tracked_allowed(self):
        self.assertInWorktree(ALLOW, 'mv tracked.txt renamed.txt')

    def test_mv_untracked_source_allowed(self):
        """Moving relocates content rather than destroying it; sources need no tracking."""
        self.assertInWorktree(ALLOW, 'mv untracked-scratch.txt scratch-renamed.txt')

    def test_mv_overwriting_tracked_dest_allowed(self):
        self.assertInWorktree(ALLOW, 'mv a.log tracked.txt')

    def test_mv_overwriting_untracked_dest_asks(self):
        """The destination is the only copy of something; replacing it silently loses it."""
        self.assertInWorktree(ASK, 'mv tracked.txt untracked-scratch.txt')

    def test_mv_into_directory_allowed(self):
        self.assertInWorktree(ALLOW, 'mv tracked.txt sub/')

    def test_mv_into_directory_with_untracked_collision_asks(self):
        self.assertInWorktree(ASK, 'mv collide.txt sub/')

    def test_mv_into_symlinked_out_directory_asks(self):
        """A contained-looking dir that resolves outside would carry the file out."""
        self.assertInWorktree(ASK, 'mv tracked.txt dir-out/')

    def test_mv_source_outside_asks(self):
        self.assertInWorktree(ASK, f'mv {self.outside} pulled-in.txt')

    def test_mv_dest_outside_asks(self):
        self.assertInWorktree(ASK, f'mv tracked.txt {self.temp}/escaped.txt')

    def test_mv_target_directory_flag_asks(self):
        """GNU -t moves the destination into a flag and defeats the last-operand rule."""
        self.assertInWorktree(ASK, 'mv -t sub tracked.txt')

    def test_mv_glob_sources_allowed(self):
        self.assertInWorktree(ALLOW, 'mv *.log sub/')

    def test_mv_glob_matching_nothing_asks(self):
        self.assertInWorktree(ASK, 'mv *.nope sub/')

    def test_mv_single_operand_asks(self):
        self.assertInWorktree(ASK, 'mv tracked.txt')

    def test_mv_multiple_sources_to_file_dest_asks(self):
        self.assertInWorktree(ASK, 'mv tracked.txt a.log combined.txt')

    def test_mv_with_command_prefix_allowed(self):
        self.assertInWorktree(ALLOW, 'command mv tracked.txt renamed-again.txt')

    def test_mv_in_main_tree_asks(self):
        self.assertInMainTree(ASK, 'mv tracked.txt elsewhere.txt')

    def test_mv_in_rogue_worktree_asks(self):
        self.assertInRogueWorktree(ASK, 'mv tracked.txt elsewhere.txt')

    def test_cp_overwriting_untracked_dest_asks(self):
        self.assertInWorktree(ASK, 'cp tracked.txt untracked-scratch.txt')

    def test_cp_overwriting_tracked_dest_allowed(self):
        """Sources are only read, so an untracked source is fine; the dest is recoverable."""
        self.assertInWorktree(ALLOW, 'cp untracked-scratch.txt tracked.txt')

    def test_cp_into_directory_allowed(self):
        self.assertInWorktree(ALLOW, 'cp tracked.txt sub/')

    def test_cp_into_directory_with_untracked_collision_asks(self):
        self.assertInWorktree(ASK, 'cp collide.txt sub/')

    def test_cp_into_symlinked_out_directory_asks(self):
        self.assertInWorktree(ASK, 'cp tracked.txt dir-out/')

    def test_cp_source_outside_asks(self):
        self.assertInWorktree(ASK, f'cp {self.outside} pulled-in.txt')

    def test_cp_dest_outside_asks(self):
        self.assertInWorktree(ASK, f'cp tracked.txt {self.temp}/escaped.txt')

    def test_cp_recursive_to_fresh_dest_allowed(self):
        """Nothing exists at the landing, so nothing can be replaced, however deep."""
        self.assertInWorktree(ALLOW, 'cp -R sub sub-copy')

    def test_cp_recursive_onto_existing_landing_asks(self):
        self.assertInWorktree(ASK, 'cp -R a.log tracked.txt')

    def test_cp_glob_sources_allowed(self):
        self.assertInWorktree(ALLOW, 'cp *.log sub/')

    def test_cp_long_flag_asks(self):
        self.assertInWorktree(ASK, 'cp --recursive sub sub-copy')

    def test_chained_git_commit_asks(self):
        """An allow spans the whole line, so operators must force a prompt."""
        self.assertInWorktree(ASK, 'git commit -m "x" && git push')

    def test_chained_cp_asks(self):
        self.assertInWorktree(ASK, 'cp a.log b.log; ls')

    def test_redirected_rm_asks(self):
        self.assertInWorktree(ASK, 'rm tracked.txt > out.txt')

    def test_chained_worktree_remove_asks(self):
        self.assertInWorktree(ASK, 'git worktree remove .claude/worktrees/feature && echo done')

    def test_dollar_in_commit_message_asks(self):
        self.assertInWorktree(ASK, 'git commit -m "costs $5"')


class ClaudeTmpExemptionTest(unittest.TestCase):
    """Scratch cleanup under .claude/tmp/ is settings.json's turf; the hook stays silent."""

    def assertSilent(self, command):
        out, code = run(command, cwd='/tmp')
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertIsNone(decision(out), f'expected silence for: {command}')

    def test_rm_tmp_file_silent(self):
        self.assertSilent('rm .claude/tmp/scratch.txt')

    def test_rm_f_multiple_tmp_files_silent(self):
        self.assertSilent('rm -f .claude/tmp/a.png .claude/tmp/b.log')

    def test_command_rm_tmp_file_silent(self):
        self.assertSilent('command rm .claude/tmp/scratch.txt')

    def test_mv_sweep_into_tmp_silent(self):
        self.assertSilent('mv scratch.txt .claude/tmp/')

    def test_mv_sweep_to_tmp_filename_silent(self):
        self.assertSilent('mv scratch.txt .claude/tmp/scratch.txt')

    def test_cp_into_tmp_silent(self):
        self.assertSilent('cp debug.png .claude/tmp/')

    def test_rm_tmp_path_escaping_upward_not_exempt(self):
        """Traversal in an operand defeats the textual prefix, so no silence."""
        out, _ = run('rm .claude/tmp/../../important.txt', cwd='/tmp')
        self.assertEqual(decision(out), ASK)

    def test_rm_mixed_tmp_and_other_not_exempt(self):
        out, _ = run('rm .claude/tmp/a.txt other.txt', cwd='/tmp')
        self.assertEqual(decision(out), ASK)

    def test_rm_absolute_tmp_path_not_exempt(self):
        """The allow rules are relative-only, so the exemption is too."""
        out, _ = run('rm /Users/x/project/.claude/tmp/a.txt', cwd='/tmp')
        self.assertEqual(decision(out), ASK)


if __name__ == '__main__':
    unittest.main()
