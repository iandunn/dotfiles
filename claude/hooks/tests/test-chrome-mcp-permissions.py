#!/usr/bin/env python3
"""
Tests for chrome-mcp-permissions.py's navigation gate.
Run with: python3 test-chrome-mcp-permissions.py

Every run writes the session usage-gate marker first, so the hook short-circuits
that gate instead of shelling out to `claude -p "/usage"` for several seconds.
The pre-authorization cases read the real project matrix rather than a fixture,
since the point is that the shipped PRE_AUTHORIZED_SITE_MATRICES entry resolves.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

SCRIPT = Path(__file__).parent.parent / 'chrome-mcp-permissions.py'
ALLOW = 'allow'
ASK = 'ask'
SESSION_ID = 'test-chrome-mcp-permissions'
MARKER_DIR = Path(tempfile.gettempdir()) / 'claude-chrome-mcp-usage-gate'

PROJECT_ROOT = Path('~/local-sites/misc/app/public/browser-extensions/slash-to-search').expanduser()
SITE_MATRIX = PROJECT_ROOT / 'test/sites.json'


def run(url, cwd):
    """Run the hook as a new_page call, return (stdout, returncode)."""
    MARKER_DIR.mkdir(parents=True, exist_ok=True)
    (MARKER_DIR / f'{SESSION_ID}.marker').write_text('gated')

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({
            'tool_name': 'mcp__chrome-devtools__new_page',
            'tool_input': {'url': url},
            'session_id': SESSION_ID,
            'cwd': str(cwd),
        }),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip(), result.returncode


def decision(stdout):
    """Parse the permissionDecision from hook output, or None if no output."""
    if not stdout:
        return None
    return json.loads(stdout)['hookSpecificOutput']['permissionDecision']


def a_matrix_url():
    """A URL from the real site matrix, so the test can't drift from its contents."""
    with open(SITE_MATRIX) as matrix_file:
        return json.load(matrix_file)['sites'][0]['url']


class GateTestCase(unittest.TestCase):

    def assertDecision(self, expected, url, cwd):
        out, code = run(url, cwd)
        self.assertEqual(code, 0, f'non-zero exit for: {url}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {url} in {cwd}')


class NavigationGateTest(GateTestCase):

    def test_local_host_allowed(self):
        self.assertDecision(ALLOW, 'http://misc.localwp.test/', Path.home())

    def test_about_blank_allowed(self):
        self.assertDecision(ALLOW, 'about:blank', Path.home())

    def test_external_host_asks(self):
        self.assertDecision(ASK, 'https://example.com/', Path.home())


@unittest.skipUnless(SITE_MATRIX.is_file(), f'{SITE_MATRIX} not present')
class PreAuthorizedSiteMatrixTest(GateTestCase):

    def test_matrix_host_allowed_inside_project(self):
        self.assertDecision(ALLOW, a_matrix_url(), PROJECT_ROOT)

    def test_matrix_host_allowed_from_subdirectory(self):
        self.assertDecision(ALLOW, a_matrix_url(), PROJECT_ROOT / 'src')

    def test_any_path_on_a_matrix_host_allowed(self):
        """Matching is per-host: the gate can't re-prompt on in-site navigation."""
        host = urlparse(a_matrix_url()).hostname
        self.assertDecision(ALLOW, f'https://{host}/some/deep/page?q=x', PROJECT_ROOT)

    def test_host_outside_matrix_asks(self):
        self.assertDecision(ASK, 'https://example.com/', PROJECT_ROOT)

    def test_matrix_host_asks_outside_project(self):
        self.assertDecision(ASK, a_matrix_url(), PROJECT_ROOT.parent)

    def test_sibling_directory_asks(self):
        """A sibling whose name merely starts with the root's is not inside it."""
        sibling = PROJECT_ROOT.parent / f'{PROJECT_ROOT.name}-untrusted'
        self.assertDecision(ASK, a_matrix_url(), sibling)


if __name__ == '__main__':
    unittest.main(verbosity=2)
