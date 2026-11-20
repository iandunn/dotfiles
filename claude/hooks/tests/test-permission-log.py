#!/usr/bin/env python3
"""
Tests for log-permission-prompts.py and permission-prompt-report.py.
Run with: python3 test-permission-log.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOKS = Path(__file__).parent.parent
LOGGER = HOOKS / 'log-permission-prompts.py'
REPORT = HOOKS.parent / 'bin' / 'permission-prompt-report.py'

sys.path.insert(0, str(HOOKS))
spec = importlib.util.spec_from_file_location('log_permission_prompts', LOGGER)
logger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logger)


def payload(command):
    return {
        'session_id': 'session-1',
        'cwd': str(HOOKS),
        'hook_event_name': 'PermissionRequest',
        'tool_name': 'Bash',
        'tool_input': {'command': command},
    }


class LogTestCase(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.log = self.root / 'state' / 'log.jsonl'
        self.environment = {**os.environ, 'CLAUDE_PERMISSION_LOG': str(self.log)}

    def tearDown(self):
        self.directory.cleanup()

    def write_settings(self, groups):
        settings = self.root / 'settings.json'
        settings.write_text(json.dumps({'hooks': {'PreToolUse': groups}}))
        return settings

    def log_entries(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


class HookSelectionTest(LogTestCase):

    def hook(self, command):
        return {'type': 'command', 'command': command}

    def test_selects_this_folders_hooks_for_matching_tool(self):
        settings = self.write_settings([
            {'matcher': 'Bash', 'hooks': [self.hook('python3 ~/.claude/hooks/desktop-app-permissions.py')]},
            {'matcher': 'mcp__local-wp__wp_cli', 'hooks': [self.hook('python3 ~/.claude/hooks/command-allowlist-permissions.py')]},
        ])
        scripts, skipped = logger.matching_hook_scripts('Bash', settings)
        self.assertEqual([script.name for script in scripts], ['desktop-app-permissions.py'])
        self.assertEqual(skipped, [])

    def test_chrome_hook_is_skipped_but_reported(self):
        settings = self.write_settings([
            {'matcher': 'mcp__chrome-devtools__.*', 'hooks': [self.hook('python3 ~/.claude/hooks/chrome-mcp-permissions.py')]},
        ])
        self.assertEqual(
            logger.matching_hook_scripts('mcp__chrome-devtools__click', settings),
            ([], ['chrome-mcp-permissions.py']),
        )
        chrome_payload = {**payload(''), 'tool_name': 'mcp__chrome-devtools__click', 'tool_input': {}}
        self.assertEqual(
            logger.hook_reasons(chrome_payload, settings),
            [{'hook': 'chrome-mcp-permissions.py', 'reason': None, 'rerun': False}],
        )

    def test_unlisted_hook_in_folder_is_not_rerun(self):
        settings = self.write_settings([
            {'matcher': 'Bash', 'hooks': [self.hook('python3 ~/.claude/hooks/log-permission-prompts.py')]},
        ])
        self.assertEqual(
            logger.matching_hook_scripts('Bash', settings),
            ([], ['log-permission-prompts.py']),
        )

    def test_skips_scripts_outside_hooks_folder(self):
        outside = self.root / 'evil.py'
        outside.write_text('')
        settings = self.write_settings([
            {'matcher': 'Bash', 'hooks': [self.hook(f'python3 {outside}')]},
        ])
        self.assertEqual(logger.matching_hook_scripts('Bash', settings), ([], []))

    def test_skips_commands_that_are_not_a_plain_python_script(self):
        settings = self.write_settings([
            {'matcher': 'Bash', 'hooks': [
                self.hook('bash -c "rm -rf /"'),
                self.hook('python3 ~/.claude/hooks/desktop-app-permissions.py --extra'),
            ]},
        ])
        self.assertEqual(logger.matching_hook_scripts('Bash', settings), ([], []))

    def test_matcher_must_match_whole_tool_name(self):
        settings = self.write_settings([
            {'matcher': 'Bash', 'hooks': [self.hook('python3 ~/.claude/hooks/desktop-app-permissions.py')]},
        ])
        self.assertEqual(logger.matching_hook_scripts('BashOutput', settings), ([], []))

    def test_star_and_invalid_matchers(self):
        settings = self.write_settings([
            {'matcher': '*', 'hooks': [self.hook('python3 ~/.claude/hooks/desktop-app-permissions.py')]},
            {'matcher': '(', 'hooks': [self.hook('python3 ~/.claude/hooks/dangerous-command-shapes.py')]},
        ])
        scripts, _ = logger.matching_hook_scripts('Bash', settings)
        self.assertEqual([script.name for script in scripts], ['desktop-app-permissions.py'])

    def test_reasons_include_only_asking_hooks(self):
        settings = self.write_settings([
            {'matcher': 'Bash', 'hooks': [
                self.hook('python3 ~/.claude/hooks/desktop-app-permissions.py'),
                self.hook('python3 ~/.claude/hooks/dangerous-command-shapes.py'),
            ]},
        ])
        reasons = logger.hook_reasons(payload('code .'), settings)
        self.assertEqual([item['hook'] for item in reasons], ['desktop-app-permissions.py'])
        self.assertTrue(reasons[0]['reason'])

    def test_deny_is_not_an_ask(self):
        settings = self.write_settings([
            {'matcher': 'Bash', 'hooks': [self.hook('python3 ~/.claude/hooks/dangerous-command-shapes.py')]},
        ])
        self.assertEqual(logger.hook_reasons(payload('ls; ls'), settings), [])


class LoggerProcessTest(LogTestCase):

    def run_logger(self, stdin):
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(LOGGER)],
            input=stdin,
            capture_output=True,
            text=True,
            env=self.environment,
        )
        return result, time.monotonic() - started

    def wait_for_entries(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            entries = self.log_entries()
            if entries:
                return entries
            time.sleep(0.1)
        return []

    def test_logs_in_background_without_output(self):
        result, elapsed = self.run_logger(json.dumps(payload('code .')))
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.returncode, 0)
        # The hook returns before the hooks are re-run. The bound is loose for a busy machine.
        self.assertLess(elapsed, 3)

        [entry] = self.wait_for_entries()
        self.assertEqual(entry['event'], 'prompt')
        self.assertEqual(entry['tool_input'], {'command': 'code .'})
        self.assertIn('desktop-app-permissions.py', [item['hook'] for item in entry['hook_reasons']])

    def test_bad_payload_exits_cleanly(self):
        result, _ = self.run_logger('not json')
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.returncode, 0)

    def test_log_is_private(self):
        self.run_logger(json.dumps(payload('code .')))
        self.wait_for_entries()
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.log.parent.stat().st_mode & 0o777, 0o700)

    def test_symlinked_log_is_not_followed(self):
        import permission_log
        target = self.root / 'target.txt'
        target.write_text('original\n')
        self.log.parent.mkdir(parents=True)
        self.log.symlink_to(target)
        previous = os.environ.get('CLAUDE_PERMISSION_LOG')
        os.environ['CLAUDE_PERMISSION_LOG'] = str(self.log)
        try:
            with self.assertRaises(OSError):
                permission_log.append({'event': 'prompt'})
        finally:
            if previous is None:
                del os.environ['CLAUDE_PERMISSION_LOG']
            else:
                os.environ['CLAUDE_PERMISSION_LOG'] = previous
        self.assertEqual(target.read_text(), 'original\n')


class ReportTest(LogTestCase):

    def write_log(self, entries):
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log, 'w') as log:
            for entry in entries:
                log.write(json.dumps(entry) + '\n')

    def run_report(self, *arguments):
        return subprocess.run(
            [sys.executable, str(REPORT), '--log', str(self.log), *arguments],
            capture_output=True,
            text=True,
        ).stdout

    def prompt(self, command, hook_reasons, **fields):
        from datetime import datetime, timezone
        return {
            'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'event': 'prompt',
            'tool_name': 'Bash',
            'tool_input': {'command': command},
            'hook_reasons': hook_reasons,
            **fields,
        }

    def line_for(self, report, text):
        return next(line for line in report.splitlines() if text in line)

    def test_groups_by_normalized_reason(self):
        self.write_log([
            self.prompt('rm /a', [{'hook': 'file.py', 'reason': '`/a` is untracked'}]),
            self.prompt('rm /b', [{'hook': 'file.py', 'reason': '`/b` is untracked'}]),
            self.prompt('ln -s a b', []),
            self.prompt('ls', None),
        ])
        report = self.run_report()
        self.assertTrue(self.line_for(report, 'file.py: `...` is untracked').strip().startswith('2 '))
        self.assertIn('no hook in ~/.claude/settings.json asked', report)
        self.assertIn('reason unknown', report)

    def test_reasonless_prompts_group_by_program(self):
        self.write_log([
            self.prompt('git -C /repo worktree remove /repo/wt', []),
            self.prompt('git worktree add /repo/wt2', []),
            self.prompt('ln -s a b', []),
        ])
        report = self.run_report()
        self.assertTrue(self.line_for(report, '`git worktree`').strip().startswith('2 '))
        self.assertTrue(self.line_for(report, '`ln`').strip().startswith('1 '))

    def test_control_characters_are_escaped(self):
        self.write_log([
            self.prompt('\x1b[2Kcode .', [{'hook': 'x.py', 'reason': 'asks \x1b[1A'}]),
            self.prompt('\x1b[2Kln a b', []),
        ])
        report = self.run_report()
        self.assertNotIn('\x1b', report)
        self.assertIn('\\x1b[2Kcode .', report)

    def test_lone_surrogate_is_still_logged(self):
        import permission_log
        previous = os.environ.get('CLAUDE_PERMISSION_LOG')
        os.environ['CLAUDE_PERMISSION_LOG'] = str(self.log)
        try:
            permission_log.append({'event': 'prompt', 'tool_input': {'command': 'ls # \ud800'}})
        finally:
            if previous is None:
                del os.environ['CLAUDE_PERMISSION_LOG']
            else:
                os.environ['CLAUDE_PERMISSION_LOG'] = previous
        self.assertEqual(len(self.log_entries()), 1)

    def test_old_prompts_are_left_out(self):
        self.write_log([
            {**self.prompt('ln -s a b', []), 'ts': '2020-01-01T00:00:00+00:00'},
        ])
        self.assertIn('Prompts in the last 30 days: 0', self.run_report())

    def test_missing_log(self):
        self.assertIn('No log yet', self.run_report())


if __name__ == '__main__':
    unittest.main()
