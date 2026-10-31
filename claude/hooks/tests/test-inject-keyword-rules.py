#!/usr/bin/env python3
"""
Tests for inject-keyword-rules.py.
Run with: python3 test-inject-keyword-rules.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'inject-keyword-rules.py'


def injected_context(prompt):
    """Run the hook with a prompt, return the injected context, or None if it stayed silent."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({'prompt': prompt}),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f'non-zero exit for: {prompt}\n{result.stderr}')
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)['hookSpecificOutput']['additionalContext']


class InjectKeywordRulesTest(unittest.TestCase):

    def assertInjects(self, prompt, heading):
        context = injected_context(prompt)
        self.assertIsNotNone(context, f'expected rules for: {prompt}')
        self.assertIn(heading, context)

    def test_hold_injects_hold_rules(self):
        self.assertInjects('hold. the commit message is wrong', '## Hold / Resume')

    def test_resume_injects_hold_rules(self):
        self.assertInjects('Resume', '## Hold / Resume')

    def test_pplan_injects_parallel_plan_rules(self):
        self.assertInjects('pplan add a setting for the timeout', '## Parallel Plan')

    def test_parallel_plan_phrase_injects_rules(self):
        self.assertInjects('this is a parallel plan', '## Parallel Plan')

    def test_bare_go_injects_parallel_plan_rules(self):
        self.assertInjects('go', '## Parallel Plan')

    def test_go_with_a_caveat_injects_parallel_plan_rules(self):
        self.assertInjects('go but keep the old function name', '## Parallel Plan')
        self.assertInjects('Go, and then clean up the worktree', '## Parallel Plan')

    def test_go_ahead_is_silent(self):
        self.assertIsNone(injected_context('go ahead and fix it'))
        self.assertIsNone(injected_context('go, ahead'))

    def test_go_live_is_silent(self):
        self.assertIsNone(injected_context('go-live is friday'))

    def test_go_mid_sentence_is_silent(self):
        self.assertIsNone(injected_context("let's go with option 2"))

    def test_go_on_a_later_line_is_silent(self):
        self.assertIsNone(injected_context('run these:\ngo test ./...'))

    def test_resume_at_end_of_sentence_injects_hold_rules(self):
        self.assertInjects('blah blah. resume.', '## Hold / Resume')
        self.assertInjects('blah blah.resume', '## Hold / Resume')

    def test_resume_inside_a_name_is_silent(self):
        self.assertIsNone(injected_context('/relay-eng:resume-work 123'))
        self.assertIsNone(injected_context('resume.pdf is attached'))

    def test_notifications_are_silent(self):
        self.assertIsNone(injected_context('<task-notification>\ngo\nhold</task-notification>'))
        self.assertIsNone(injected_context('<agent-message from="x">resume</agent-message>'))

    def test_word_starting_with_go_is_silent(self):
        self.assertIsNone(injected_context('good catch, fix it'))

    def test_both_keywords_inject_both_files(self):
        context = injected_context('pplan this, then hold')
        self.assertIn('## Hold / Resume', context)
        self.assertIn('## Parallel Plan', context)

    def test_word_containing_hold_is_silent(self):
        self.assertIsNone(injected_context('replace the placeholder text'))

    def test_unrelated_prompt_is_silent(self):
        self.assertIsNone(injected_context('fix the failing test'))

    def test_invalid_payloads_are_silent(self):
        for payload in ('not json', '[]', '"go"'):
            result = subprocess.run(
                [sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(result.stdout.strip(), '', payload)


if __name__ == '__main__':
    unittest.main()
