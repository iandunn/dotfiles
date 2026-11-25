#!/usr/bin/env python3
"""
Tests for iterm-status-dot.py.
Run with: python3 test-iterm-status-dot.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'iterm-status-dot.py'
SESSION_ID = '93701BD3-0000-0000-0000-000000000000'
ITERM_ENV = {
    'TERM_PROGRAM': 'iTerm.app',
    'ITERM_SESSION_ID': 'w0t0p0:' + SESSION_ID,
    'CLAUDE_CODE_DISABLE_TERMINAL_TITLE': '1',
    'CLAUDE_CODE_ENTRYPOINT': 'cli',
    'TMUX': '',
}


class ItermStatusDotTest(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.log = Path(self.directory.name) / 'calls.log'
        # A stand-in for `it2` that logs the calls that change a tab, so the tests never touch a real
        # iTerm tab. `get-status` reports the dot color in `FAKE_DOT_COLOR`.
        self.fake_it2 = Path(self.directory.name) / 'it2'
        self.fake_it2.write_text(
            '#!/bin/sh\n'
            'if [ "$2" = get-status ]; then\n'
            '\tprintf \'{"dot_color": "%%s"}\' "$FAKE_DOT_COLOR"\n'
            '\texit 0\n'
            'fi\n'
            'printf "%%s\\n" "$*" >> %s\n' % self.log
        )
        self.fake_it2.chmod(0o755)

    def tearDown(self):
        self.directory.cleanup()

    def run_hook(self, event, env=ITERM_ENV):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env={**os.environ, **env, 'ITERM_STATUS_DOT_IT2': str(self.fake_it2)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def it2_calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def assertDot(self, event_name, color, **fields):
        self.run_hook({'hook_event_name': event_name, **fields})
        self.assertEqual(
            self.it2_calls(),
            ['session set-status --session %s --status  --dot-color %s' % (SESSION_ID, color)],
        )

    def test_prompt_sets_working_dot(self):
        self.assertDot('UserPromptSubmit', '#ff9500')

    def test_permission_prompt_sets_approval_dot(self):
        self.assertDot('PermissionRequest', '#ff3b30')

    def test_finished_tool_sets_working_dot(self):
        self.assertDot('PostToolUse', '#ff9500')

    def test_stop_sets_done_dot(self):
        self.assertDot('Stop', '#00d75f', background_tasks=[], session_crons=[])

    def test_stop_with_background_task_sets_background_dot(self):
        self.assertDot('Stop', '#af52de', background_tasks=[{'id': 'b1'}])

    def test_stop_with_scheduled_wakeup_sets_background_dot(self):
        self.assertDot('Stop', '#af52de', session_crons=[{'id': 'c1'}])

    def test_failed_tool_sets_working_dot(self):
        self.assertDot('PostToolUseFailure', '#ff9500')

    def test_idle_notification_sets_done_dot(self):
        self.assertDot('Notification', '#00d75f', notification_type='idle_prompt')

    def test_idle_notification_leaves_background_dot(self):
        self.run_hook(
            {'hook_event_name': 'Notification', 'notification_type': 'idle_prompt'},
            {**ITERM_ENV, 'FAKE_DOT_COLOR': '#AF52DE'},
        )
        self.assertEqual(self.it2_calls(), [])

    def test_other_notification_leaves_dot(self):
        self.run_hook({'hook_event_name': 'Notification', 'notification_type': 'permission_prompt'})
        self.assertEqual(self.it2_calls(), [])

    def test_compaction_leaves_dot(self):
        self.run_hook({'hook_event_name': 'SessionStart', 'source': 'compact'})
        self.assertEqual(self.it2_calls(), [])

    def test_session_start_titles_tab(self):
        output = self.run_hook({
            'hook_event_name': 'SessionStart',
            'source': 'resume',
            'session_title': 'Foot\x1ber fix',
        })
        self.assertEqual(json.loads(output), {'terminalSequence': '\x1b]0;Footer fix\x07'})
        self.assertEqual(
            self.it2_calls(),
            ['session set-status --session %s --status  --dot-color #00d75f' % SESSION_ID],
        )

    def test_session_end_hands_title_back(self):
        output = self.run_hook({'hook_event_name': 'SessionEnd'})
        self.assertEqual(json.loads(output), {'terminalSequence': '\x1b]0;\x07'})
        self.assertEqual(self.it2_calls(), [])

    def test_does_nothing_outside_iterm(self):
        output = self.run_hook(
            {'hook_event_name': 'SessionStart', 'session_title': 'Footer'},
            {**ITERM_ENV, 'TERM_PROGRAM': 'vscode'},
        )
        self.assertEqual(output, '')
        self.assertEqual(self.it2_calls(), [])

    def test_does_nothing_while_claude_code_reports_status(self):
        output = self.run_hook(
            {'hook_event_name': 'UserPromptSubmit'},
            {**ITERM_ENV, 'CLAUDE_CODE_DISABLE_TERMINAL_TITLE': ''},
        )
        self.assertEqual(output, '')
        self.assertEqual(self.it2_calls(), [])

    def test_does_nothing_in_an_app_launched_from_iterm(self):
        self.run_hook(
            {'hook_event_name': 'UserPromptSubmit'},
            {**ITERM_ENV, 'CLAUDE_CODE_ENTRYPOINT': 'claude-vscode'},
        )
        self.assertEqual(self.it2_calls(), [])

    def test_does_nothing_inside_tmux(self):
        self.run_hook({'hook_event_name': 'UserPromptSubmit'}, {**ITERM_ENV, 'TMUX': '/tmp/tmux,1,0'})
        self.assertEqual(self.it2_calls(), [])


if __name__ == '__main__':
    unittest.main()
