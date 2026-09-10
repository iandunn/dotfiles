#!/usr/bin/env python3
"""
Tests for file-command-permissions.py.
Run with: python3 test-file-command-permissions.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'file-command-permissions.py'
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

        os.mkdir(os.path.join(cls.main_tree, 'sub-fixture'))
        Path(cls.main_tree, 'sub-fixture', 'fixture.txt').write_text('lives in main\n')

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

    def test_git_status_allowed(self):
        self.assertInWorktree(ALLOW, 'git status')

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

    def test_cp_source_outside_allowed(self):
        """cp only reads its sources, so pulling a fixture in from elsewhere is safe."""
        self.assertInWorktree(ALLOW, f'cp {self.outside} pulled-in.txt')

    def test_cp_recursive_from_main_tree_into_worktree_allowed(self):
        self.assertInWorktree(ALLOW, f'cp -R {self.main_tree}/sub-fixture sub-fixture')

    def test_cp_source_outside_onto_untracked_dest_asks(self):
        """A free source still cannot land on the only copy of something."""
        self.assertInWorktree(ASK, f'cp {self.outside} untracked-scratch.txt')

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

    def test_multi_paragraph_commit_message_allowed(self):
        """Newlines inside the -m argument are one quoted string, not a second command."""
        self.assertInWorktree(
            ALLOW,
            'git commit -m "Docs: Correct the quality\n\nThe pipeline writes at 95, not 92."',
        )

    def test_newline_outside_quotes_asks(self):
        self.assertInWorktree(ASK, 'git add a.log\ngit push')

    def test_semicolon_inside_quotes_allowed(self):
        self.assertInWorktree(ALLOW, 'git commit -m "Hooks: Fix the guard; it scanned raw text"')

    def test_redirect_inside_quotes_allowed(self):
        self.assertInWorktree(ALLOW, 'git commit -m "Hooks: Prefer > over >> when truncating"')

    def test_backtick_inside_single_quotes_allowed(self):
        """The commit convention backticks code references, so single quotes must carry them."""
        self.assertInWorktree(ALLOW, "git commit -m 'Hooks: Rewrite `has_shell_operators`'")

    def test_dollar_inside_single_quotes_allowed(self):
        self.assertInWorktree(ALLOW, "git commit -m 'Costs $5 to run'")

    def test_backtick_inside_double_quotes_asks(self):
        self.assertInWorktree(ASK, 'git commit -m "Hooks: Rewrite `whoami`"')

    def test_ansi_c_quoting_asks(self):
        """`$'...'` is caught because its `$` is read while still unquoted."""
        self.assertInWorktree(ASK, "git commit -m $'first\\nsecond'")

    def test_escaped_dollar_inside_double_quotes_allowed(self):
        self.assertInWorktree(ALLOW, 'git commit -m "Costs \\$5 to run"')

    def test_unterminated_quote_asks(self):
        self.assertInWorktree(ASK, 'git commit -m "never closed')

    def test_trailing_backslash_asks(self):
        self.assertInWorktree(ASK, 'git add a.log \\')

    def test_line_continuation_asks(self):
        """Bash joins the lines before parsing, so `rm \\` plus a newline runs whatever follows."""
        self.assertInWorktree(ASK, 'rm \\\n -rf a.log')
        self.assertInWorktree(ASK, 'git add a.log \\\n b.log')
        self.assertInWorktree(ASK, 'git commit -m "Hooks: Add \\\n a test"')

    def test_command_substitution_outside_quotes_asks(self):
        self.assertInWorktree(ASK, 'git add $(ls)')


class BranchDeleteTest(unittest.TestCase):
    """Deleting a worktree branch is allowed only when HEAD already holds its content."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='branch-delete-test-')
        cls.repo = os.path.join(cls.temp, 'repo')
        os.makedirs(cls.repo)
        git(cls.repo, 'init', '-b', 'main')
        git(cls.repo, 'config', 'user.email', 'test@example.com')
        git(cls.repo, 'config', 'user.name', 'Test')
        Path(cls.repo, 'base.txt').write_text('base\n')
        git(cls.repo, 'add', 'base.txt')
        git(cls.repo, 'commit', '-m', 'initial')

        # A branch whose two commits `go` collapsed into one differently-shaped
        # commit on main: patch-ids cannot match, but the content is all there.
        git(cls.repo, 'branch', 'worktree-squashed')
        git(cls.repo, 'checkout', 'worktree-squashed')
        Path(cls.repo, 'feature.txt').write_text('first half\n')
        git(cls.repo, 'add', 'feature.txt')
        git(cls.repo, 'commit', '-m', 'first half')
        Path(cls.repo, 'feature.txt').write_text('first half\nsecond half\n')
        git(cls.repo, 'add', 'feature.txt')
        git(cls.repo, 'commit', '-m', 'second half')
        git(cls.repo, 'checkout', 'main')
        Path(cls.repo, 'feature.txt').write_text('first half\nsecond half\n')
        git(cls.repo, 'add', 'feature.txt')
        git(cls.repo, 'commit', '-m', 'squashed patch from the worktree')

        # A branch carrying work that never landed anywhere.
        git(cls.repo, 'branch', 'worktree-unlanded')
        git(cls.repo, 'checkout', 'worktree-unlanded')
        Path(cls.repo, 'orphan.txt').write_text('only copy\n')
        git(cls.repo, 'add', 'orphan.txt')
        git(cls.repo, 'commit', '-m', 'work that never landed')
        git(cls.repo, 'checkout', 'main')

        # A non-worktree branch whose content IS on HEAD, to prove the name gate.
        git(cls.repo, 'branch', 'feature/real-work')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp, ignore_errors=True)

    def assertInRepo(self, expected, command):
        out, code = run(command, cwd=self.repo)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')

    def test_squashed_branch_allowed(self):
        """The case `go` actually produces: content identical, patch-ids different."""
        self.assertInRepo(ALLOW, 'git branch -D worktree-squashed')

    def test_unlanded_branch_asks(self):
        self.assertInRepo(ASK, 'git branch -D worktree-unlanded')

    def test_non_worktree_branch_asks(self):
        """Even fully-contained content does not license deleting a real branch."""
        self.assertInRepo(ASK, 'git branch -D feature/real-work')

    def test_unknown_branch_asks(self):
        self.assertInRepo(ASK, 'git branch -D worktree-never-existed')

    def test_multiple_branches_ask(self):
        self.assertInRepo(ASK, 'git branch -D worktree-squashed worktree-unlanded')

    def test_lowercase_delete_flag_gated(self):
        self.assertInRepo(ALLOW, 'git branch -d worktree-squashed')

    def test_long_delete_flag_gated(self):
        self.assertInRepo(ASK, 'git branch --delete worktree-unlanded')

    def test_force_cluster_gated(self):
        self.assertInRepo(ASK, 'git branch -fD worktree-unlanded')

    def test_branch_listing_not_gated(self):
        out, code = run('git branch --list', cwd=self.repo)
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))

    def test_branch_creation_not_gated(self):
        out, code = run('git branch new-thing', cwd=self.repo)
        self.assertEqual(code, 0)
        self.assertIsNone(decision(out))

    def test_chained_branch_delete_asks(self):
        self.assertInRepo(ASK, 'git branch -D worktree-squashed && echo done')


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

    def test_mv_sweep_into_tmp_decided_by_the_hook(self):
        """`mv` into scratch is the hook's alone, so a relative dest is not silent."""
        out, _ = run('mv scratch.txt .claude/tmp/', cwd='/tmp')
        self.assertEqual(decision(out), ALLOW)

    def test_mv_sweep_to_tmp_filename_decided_by_the_hook(self):
        out, _ = run('mv scratch.txt .claude/tmp/scratch.txt', cwd='/tmp')
        self.assertEqual(decision(out), ALLOW)

    def test_cp_into_tmp_silent(self):
        self.assertSilent('cp debug.png .claude/tmp/')

    def test_rm_tmp_path_escaping_upward_not_exempt(self):
        """Traversal in an operand defeats the textual prefix, so no silence."""
        out, _ = run('rm .claude/tmp/../../important.txt', cwd='/tmp')
        self.assertEqual(decision(out), ASK)

    def test_rm_mixed_tmp_and_other_not_exempt(self):
        out, _ = run('rm .claude/tmp/a.txt other.txt', cwd='/tmp')
        self.assertEqual(decision(out), ASK)

    def test_rm_absolute_tmp_path_elsewhere_not_exempt(self):
        """Silence is relative-only, and this scratch belongs to another directory."""
        out, _ = run('rm /Users/x/project/.claude/tmp/a.txt', cwd='/tmp')
        self.assertEqual(decision(out), ASK)


class AbsoluteClaudeTmpTest(unittest.TestCase):
    """An absolutely-spelled sweep into the cwd's own .claude/tmp/ is allowed by the hook.

    Silence cannot serve here: settings.json's `.claude/tmp/` rules are literal
    prefixes that no absolute path matches.
    """

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.mkdtemp(prefix='worktree-hook-abs-tmp-')
        cls.project = os.path.realpath(os.path.join(cls.temp, 'project'))
        cls.scratch = os.path.join(cls.project, '.claude', 'tmp')
        cls.other_scratch = os.path.join(
            os.path.realpath(cls.temp), 'other', '.claude', 'tmp')

        os.makedirs(cls.scratch)
        os.makedirs(cls.other_scratch)
        Path(cls.scratch, 'preview.py').write_text('scratch\n')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp, ignore_errors=True)

    def assertInProject(self, expected, command):
        out, code = run(command, cwd=self.project)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')

    def test_absolute_mv_out_of_a_worktree_into_own_scratch_allowed(self):
        """The reported failure: absolute paths, cwd in the main checkout."""
        source = os.path.join(
            self.project, '.claude', 'worktrees', 'pipeline', '.claude', 'tmp', 'preview.py')
        self.assertInProject(
            ALLOW, f'mv {source} {os.path.join(self.scratch, "preview.py")}')

    def test_absolute_rm_inside_own_scratch_allowed(self):
        self.assertInProject(ALLOW, f'rm {os.path.join(self.scratch, "preview.py")}')

    def test_absolute_cp_into_own_scratch_allowed(self):
        self.assertInProject(ALLOW, f'cp shot.png {os.path.join(self.scratch, "shot.png")}')

    def test_scratch_directory_itself_allowed(self):
        """Parity with the relative rules, which exempt the directory too."""
        self.assertInProject(ALLOW, f'rm -rf {self.scratch}')

    def test_absolute_mv_into_another_directorys_scratch_asks(self):
        dest = os.path.join(self.other_scratch, 'preview.py')
        self.assertInProject(ASK, f'mv preview.py {dest}')

    def test_absolute_rm_outside_own_scratch_asks(self):
        self.assertInProject(ASK, f'rm {os.path.join(self.project, "important.txt")}')

    def test_expandable_operand_in_own_scratch_asks(self):
        """Single quotes get it past the operator guard, so the operand check must catch it."""
        self.assertInProject(ASK, f"rm '{os.path.join(self.scratch, '$NAME.txt')}'")


class MvIntoScratchSourceTest(unittest.TestCase):
    """`mv` into scratch deletes its source, so only agent-produced sources sweep freely."""

    @classmethod
    def setUpClass(cls):
        # The fixture cannot live under the OS temp directory: every path there
        # qualifies as an agent-produced source, which is the distinction under
        # test. This repository's own scratch directory is outside it.
        parent = Path(__file__).resolve().parents[3] / '.claude' / 'tmp'
        parent.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.mkdtemp(prefix='mv-scratch-source-test-', dir=parent)
        cls.project = os.path.realpath(os.path.join(cls.temp, 'project'))
        cls.scratch = os.path.join(cls.project, '.claude', 'tmp')
        cls.outside = os.path.join(os.path.realpath(cls.temp), 'documents')

        os.makedirs(cls.scratch)
        os.makedirs(cls.outside)

        git(cls.project, 'init', '-b', 'main')
        git(cls.project, 'config', 'user.email', 'test@example.com')
        git(cls.project, 'config', 'user.name', 'Test')
        Path(cls.project, 'tracked.php').write_text('<?php\n')
        git(cls.project, 'add', 'tracked.php')
        git(cls.project, 'commit', '-m', 'initial')

        Path(cls.project, 'stray-output.json').write_text('{}\n')
        Path(cls.outside, 'taxes.pdf').write_text('mine\n')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp, ignore_errors=True)

    def assertInProject(self, expected, command):
        out, code = run(command, cwd=self.project)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')

    def test_untracked_file_in_the_project_sweeps(self):
        self.assertInProject(ALLOW, f'mv stray-output.json {self.scratch}/')

    def test_os_temp_source_sweeps(self):
        """The Chrome MCP can only write a screenshot to the OS temp directory."""
        capture = os.path.join(tempfile.gettempdir(), 'shot.png')
        self.assertInProject(ALLOW, f'mv {capture} {self.scratch}/')

    def test_file_outside_the_project_asks(self):
        """The displacement case: a file of the user's, not scratch of the agent's."""
        self.assertInProject(ASK, f'mv {self.outside}/taxes.pdf {self.scratch}/')

    def test_tracked_file_asks(self):
        """Moving a tracked file into scratch changes the repository; that is not cleanup."""
        self.assertInProject(ASK, f'mv tracked.php {self.scratch}/')

    def test_mixed_sources_ask(self):
        self.assertInProject(
            ASK, f'mv stray-output.json {self.outside}/taxes.pdf {self.scratch}/')

    def test_target_directory_flag_asks(self):
        """GNU `-t` names the destination as a flag value, so the last operand is a source."""
        self.assertInProject(ASK, f'mv -t stray-dir/ {self.scratch}/preview.py')

    def test_relative_destination_takes_the_same_path(self):
        """The settings rules are gone, so a relative dest cannot route around this."""
        self.assertInProject(ASK, f'mv {self.outside}/taxes.pdf .claude/tmp/')


class DecisionTest(unittest.TestCase):
    """Runs the hook against a command line and checks the verdict it emits."""

    def assertDecision(self, expected, command):
        out, code = run(command)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {command}')


class GitReadOnlySubcommandTest(DecisionTest):
    """A read-only subcommand is safe only with no global option beyond `-C` and no program-running argument."""

    def test_diff_allowed(self):
        self.assertDecision(ALLOW, 'git -C /some/repo diff HEAD~1 HEAD')

    def test_bare_status_allowed(self):
        self.assertDecision(ALLOW, 'git -C /some/repo status')

    def test_multi_word_subcommand_allowed(self):
        self.assertDecision(ALLOW, 'git -C /some/repo stash list')
        self.assertDecision(ALLOW, 'git -C /some/repo remote get-url origin')

    def test_multi_word_prefix_alone_not_gated(self):
        """`stash` and `remote` have writing forms, so only the listed pairs are vouched for."""
        self.assertDecision(None, 'git -C /some/repo stash drop')
        self.assertDecision(None, 'git -C /some/repo remote add upstream x')

    def test_config_override_after_dash_c_asks(self):
        """The shape the old settings.json wildcard approved: an external diff driver runs."""
        self.assertDecision(ASK, 'git -C /some/repo -c diff.external=/bin/echo diff HEAD~1 HEAD')

    def test_config_override_before_dash_c_asks(self):
        self.assertDecision(ASK, 'git -c core.pager=/bin/echo -C /some/repo log -1')

    def test_exec_path_asks(self):
        self.assertDecision(ASK, 'git -C /some/repo --exec-path=/tmp/evil status')

    def test_doubled_dash_c_asks(self):
        self.assertDecision(ASK, 'git -C /some/repo -C /other/repo status')

    def test_without_dash_c_allowed(self):
        self.assertDecision(ALLOW, 'git diff HEAD~1 HEAD')
        self.assertDecision(ALLOW, 'git log --oneline -5')

    def test_config_override_without_dash_c_asks(self):
        self.assertDecision(ASK, 'git -c core.pager=/bin/echo diff HEAD~1 HEAD')

    def test_writing_subcommand_not_gated(self):
        self.assertDecision(None, 'git -C /some/repo push origin main')

    def test_chained_command_asks(self):
        self.assertDecision(ASK, 'git -C /some/repo status && rm -rf /some/repo')

    def test_output_option_asks(self):
        """`--output` is a diff option, so every subcommand that takes diff options writes with it."""
        self.assertDecision(ASK, 'git -C /some/repo diff --output=/tmp/x HEAD~1 HEAD')
        self.assertDecision(ASK, 'git log --output /tmp/x -1')
        self.assertDecision(ASK, 'git show --output=/tmp/x HEAD')
        self.assertDecision(ASK, 'git -C /some/repo stash list --output=/tmp/x')

    def test_output_indicator_option_allowed(self):
        """Only `--output` itself writes; the `--output-indicator-*` options are cosmetic."""
        self.assertDecision(ALLOW, 'git diff --output-indicator-new=+ HEAD~1 HEAD')

    def test_grep_open_in_pager_asks(self):
        self.assertDecision(ASK, 'git -C /some/repo grep -O/bin/echo boogie')
        self.assertDecision(ASK, 'git grep -nO boogie')
        self.assertDecision(ASK, 'git grep --open-files-in-pager=vim boogie')
        self.assertDecision(ASK, 'git grep --open-files-in-pager boogie')

    def test_abbreviated_long_option_asks(self):
        """Git accepts any unambiguous prefix of a long option, so the check must too."""
        self.assertDecision(ASK, 'git grep --open=/bin/echo boogie')
        self.assertDecision(ASK, 'git fetch --upl=/bin/echo origin')
        self.assertDecision(ASK, 'git diff --out=/tmp/x HEAD~1 HEAD')

    def test_grep_without_pager_allowed(self):
        self.assertDecision(ALLOW, 'git -C /some/repo grep -n boogie -- claude/CLAUDE.md')
        self.assertDecision(ALLOW, 'git grep --only-matching boogie')

    def test_fetch_upload_pack_asks(self):
        self.assertDecision(ASK, 'git -C /some/repo fetch --upload-pack=/bin/echo origin')
        self.assertDecision(ASK, 'git fetch --upload-pack /bin/echo origin')

    def test_fetch_non_remote_operand_asks(self):
        self.assertDecision(ASK, 'git -C /some/repo fetch .')
        self.assertDecision(ASK, 'git fetch /some/other/repo')
        self.assertDecision(ASK, "git fetch 'ext::sh -c echo%20INJECTED'")
        self.assertDecision(ASK, 'git fetch https://example.com/repo.git')

    def test_fetch_remote_name_allowed(self):
        self.assertDecision(ALLOW, 'git -C /some/repo fetch origin')
        self.assertDecision(ALLOW, 'git fetch --all --prune')
        self.assertDecision(ALLOW, 'git fetch origin main')


class BenignRedirectTest(DecisionTest):
    """A redirect to `/dev/null` or a file descriptor throws output away, so it can't reach past
    the gated command, and it's stripped before the arguments are read."""

    def test_redirects_to_dev_null_allowed(self):
        self.assertDecision(ALLOW, 'git status 2>/dev/null')
        self.assertDecision(ALLOW, 'git grep -n boogie -- . 2>&1')
        self.assertDecision(ALLOW, 'git log --oneline -5 >/dev/null')

    def test_stripped_before_fetch_reads_its_operands(self):
        """Left in the token list, `2>&1` would read as an operand that isn't a remote name."""
        self.assertDecision(ALLOW, 'git fetch origin 2>/dev/null')

    def test_redirect_to_a_real_file_asks(self):
        self.assertDecision(ASK, 'git diff > /tmp/out.txt')
        self.assertDecision(ASK, 'git status >/dev/null.bak')


if __name__ == '__main__':
    unittest.main()
