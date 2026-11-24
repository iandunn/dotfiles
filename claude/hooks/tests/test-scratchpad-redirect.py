#!/usr/bin/env python3
"""
Tests for scratchpad-redirect.py.
Run with: python3 test-scratchpad-redirect.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'scratchpad-redirect.py'
SCRATCHPAD = (
    '/private/tmp/claude-501/-Users-me-project/'
    '397922ce-c8cd-4efa-8ef9-bc05912c07da/scratchpad'
)
PROJECT_TMP = '/Users/me/project/.claude/tmp'


def decision(tool_name, tool_input, cwd='/Users/me/project'):
    payload = json.dumps({'tool_name': tool_name, 'tool_input': tool_input, 'cwd': cwd})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)['hookSpecificOutput']


class TestDenied(unittest.TestCase):

    def assertDenied(self, tool_name, tool_input):
        output = decision(tool_name, tool_input)
        self.assertIsNotNone(output, f'expected deny for: {tool_input}')
        self.assertEqual(output['permissionDecision'], 'deny')

    def test_write_into_scratchpad(self):
        self.assertDenied('Write', {'file_path': f'{SCRATCHPAD}/notes.txt', 'content': 'x'})

    def test_bash_without_private_prefix(self):
        path = SCRATCHPAD.removeprefix('/private')
        self.assertDenied('Bash', {'command': f'mkdir -p {path}/yoast'})

    def test_bash_git_diff_no_index(self):
        command = f'git diff --no-index {SCRATCHPAD}/src /Users/me/project/src'
        self.assertDenied('Bash', {'command': command})

    def test_bash_quoted_scratchpad_itself(self):
        self.assertDenied('Bash', {'command': f'ls "{SCRATCHPAD}"'})

    def test_bash_scratchpad_before_delimiter(self):
        for suffix in (';', ')', '|', '`', '&', '>'):
            with self.subTest(suffix=suffix):
                self.assertDenied('Bash', {'command': f'echo $(ls {SCRATCHPAD}{suffix}'})

    def test_reason_names_project_tmp(self):
        output = decision('Write', {'file_path': f'{SCRATCHPAD}/x', 'content': ''})
        self.assertIn(f'{PROJECT_TMP}/', output['permissionDecisionReason'])


class TestPassed(unittest.TestCase):

    def assertPassed(self, tool_name, tool_input):
        output = decision(tool_name, tool_input)
        self.assertIsNone(output, f'expected no decision for: {tool_input}')

    def test_project_tmp(self):
        self.assertPassed('Write', {'file_path': f'{PROJECT_TMP}/x.txt', 'content': ''})

    def test_edit_in_scratchpad(self):
        edit = {'file_path': f'{SCRATCHPAD}/page/index.html', 'old_string': 'a', 'new_string': 'b'}
        self.assertPassed('Edit', edit)

    def test_move_out_to_project_tmp(self):
        self.assertPassed('Bash', {'command': f'mv {SCRATCHPAD}/shot.png {PROJECT_TMP}/'})

    def test_copy_out_to_relative_project_tmp(self):
        self.assertPassed('Bash', {'command': f'cp -R {SCRATCHPAD}/yoast .claude/tmp/'})

    def test_tmpdir_itself(self):
        self.assertPassed('Bash', {'command': 'ls /tmp/claude-501'})

    def test_sibling_of_scratchpad(self):
        for suffix in ('-old', '.bak', '2'):
            with self.subTest(suffix=suffix):
                self.assertPassed('Bash', {'command': f'ls {SCRATCHPAD}{suffix}'})

    def test_tool_results_dir(self):
        command = 'cat /private/tmp/claude-501/-Users-me-project/abc/tasks/x.output'
        self.assertPassed('Bash', {'command': command})

    def test_project_folder_named_scratchpad(self):
        write = {'file_path': '/Users/me/project/scratchpad/x.txt', 'content': ''}
        self.assertPassed('Write', write)

    def test_unparseable_payload(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input='not json',
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), '')


if __name__ == '__main__':
    unittest.main()
