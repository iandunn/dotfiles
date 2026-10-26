#!/usr/bin/env python3
"""
Tests for chrome-mcp-permissions.py's navigation gate.
Run with: python3 test-chrome-mcp-permissions.py

Every run writes the session usage-gate marker first, so the hook short-circuits
that gate instead of shelling out to `claude -p "/usage"` for several seconds.
The pre-authorization cases read the real project matrix rather than a fixture,
since the point is that the shipped PRE_AUTHORIZED_SITE_MATRICES entry resolves.
The `blockedSiteBrowser.sites` cases use fixture settings files under a throwaway HOME.
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


def run(url, cwd, tool_name='mcp__chrome-devtools__new_page', home=None, project_dir=None, extra_input=None):
    """Run the hook as a new_page call, return (stdout, returncode)."""
    MARKER_DIR.mkdir(parents=True, exist_ok=True)
    (MARKER_DIR / f'{SESSION_ID}.marker').write_text('gated')

    # A test run inside a Claude Code session inherits that session's project.
    env = dict(os.environ)
    env.pop('CLAUDE_PROJECT_DIR', None)
    if home:
        env['HOME'] = str(home)
    if project_dir:
        env['CLAUDE_PROJECT_DIR'] = str(project_dir)

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({
            'tool_name': tool_name,
            'tool_input': {**({} if url is None else {'url': url}), **(extra_input or {})},
            'session_id': SESSION_ID,
            'cwd': str(cwd),
        }),
        capture_output=True,
        text=True,
        env=env,
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

    def assertDecision(self, expected, url, cwd, **run_options):
        out, code = run(url, cwd, **run_options)
        self.assertEqual(code, 0, f'non-zero exit for: {url}')
        self.assertEqual(decision(out), expected, f'wrong decision for: {url} in {cwd}')


class NavigationGateTest(GateTestCase):

    def test_local_host_allowed(self):
        self.assertDecision(ALLOW, 'http://misc.localwp.test/', Path.home())

    def test_about_blank_allowed(self):
        self.assertDecision(ALLOW, 'about:blank', Path.home())

    def test_external_host_asks(self):
        self.assertDecision(ASK, 'https://example.com/', Path.home())

    def test_backslash_before_a_local_host_asks(self):
        """Chrome opens evil.com here, while urlparse reads the host as localhost."""
        self.assertDecision(ASK, 'http://evil.com\\@localhost/', Path.home())

    def test_non_http_scheme_asks(self):
        self.assertDecision(ASK, 'javascript://localhost/%0aalert(1)', Path.home())


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


BLOCKED_SITE_TOOL = 'mcp__blocked-site-browser__new_page'


def write_settings(path, sites):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'blockedSiteBrowser': {'sites': sites}}))


class BlockedSiteListTest(GateTestCase):
    """Uses a throwaway HOME, so the real global list and trust config can't change
    the results."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name).resolve()
        self.project = self.home / 'project'
        self.untrusted = self.home / 'untrusted'
        write_settings(self.home / '.claude/settings.json', ['https://www.homedepot.com/'])
        write_settings(self.project / '.claude/settings.json', ['https://www.crescentelectric.com/'])
        write_settings(self.project / '.claude/settings.local.json', ['www.lowes.com', {'url': 'https://www.ebay.com/'}, 42])
        write_settings(self.untrusted / '.claude/settings.json', ['https://www.crescentelectric.com/'])
        self.trust(self.project)

    def tearDown(self):
        self.temp_dir.cleanup()

    def trust(self, *directories):
        (self.home / '.claude.json').write_text(json.dumps({
            'projects': {str(d): {'hasTrustDialogAccepted': True} for d in directories},
        }))

    def assertListed(self, expected, url, project_dir=None, tool_name=BLOCKED_SITE_TOOL, extra_input=None):
        self.assertDecision(
            expected, url, self.home,
            tool_name=tool_name, home=self.home, project_dir=project_dir, extra_input=extra_input,
        )

    def test_global_site_allowed_outside_any_project(self):
        self.assertListed(ALLOW, 'https://www.homedepot.com/p/123')

    def test_global_site_allowed_inside_project(self):
        self.assertListed(ALLOW, 'https://www.homedepot.com/', self.project)

    def test_project_site_allowed(self):
        self.assertListed(ALLOW, 'https://www.crescentelectric.com/', self.project)

    def test_project_site_allowed_when_an_ancestor_is_trusted(self):
        self.trust(self.home)
        self.assertListed(ALLOW, 'https://www.crescentelectric.com/', self.project)

    def test_local_settings_bare_host_and_object_entries_allowed(self):
        self.assertListed(ALLOW, 'https://www.lowes.com/', self.project)
        self.assertListed(ALLOW, 'https://www.ebay.com/', self.project)

    def test_project_site_asks_outside_project(self):
        self.assertListed(ASK, 'https://www.crescentelectric.com/')

    def test_project_site_asks_in_untrusted_project(self):
        self.assertListed(ASK, 'https://www.crescentelectric.com/', self.untrusted)

    def test_cwd_does_not_choose_the_project(self):
        """cwd follows the shell's `cd`, so a list in the cwd must not count, even in a
        trusted project."""
        self.assertDecision(
            ASK, 'https://www.crescentelectric.com/', self.project,
            tool_name=BLOCKED_SITE_TOOL, home=self.home,
        )

    def test_project_opened_through_a_symlink_keeps_its_lists(self):
        """Trust is recorded under the path the project was opened by."""
        self.git(self.project, 'init', '-q')
        link = self.home / 'link'
        link.symlink_to(self.project)
        self.trust(link)
        self.assertListed(ALLOW, 'https://www.crescentelectric.com/', link)

    def test_unlisted_site_asks(self):
        self.assertListed(ASK, 'https://example.com/', self.project)

    def test_backslash_before_a_listed_host_asks(self):
        self.assertListed(ASK, 'https://evil.com\\@www.homedepot.com/', self.project)

    def test_init_script_on_listed_site_asks(self):
        self.assertListed(ASK, 'https://www.homedepot.com/', self.project, extra_input={'initScript': 'alert(1)'})

    def test_plain_navigation_options_allowed(self):
        self.assertListed(ALLOW, 'https://www.homedepot.com/', self.project, 'mcp__blocked-site-browser__navigate_page', {'type': 'url', 'pageId': 1})

    def test_harmless_unlisted_argument_asks(self):
        """The allowlist covers arguments too, so it can't miss one a release adds."""
        self.assertListed(ASK, 'https://www.homedepot.com/', self.project, extra_input={'isolatedContext': 'x'})

    def test_unmatched_bracket_asks(self):
        """urlparse raises on these, while Chrome opens evil.com."""
        self.assertListed(ASK, 'https://x[@evil.com/', self.project)
        self.assertListed(ASK, 'https://x]@evil.com/', self.project)

    def test_state_changing_tool_asks(self):
        self.assertListed(ASK, None, self.project, 'mcp__blocked-site-browser__emulate', {'userAgent': 'x'})

    def test_other_file_path_argument_asks(self):
        self.assertListed(ASK, None, self.project, 'mcp__blocked-site-browser__get_network_request', {'responseFilePath': '/tmp/x'})

    def test_malformed_input_asks(self):
        self.assertListed(ASK, None, self.project, 'mcp__blocked-site-browser__take_snapshot', {'pageId': {'nested': []}, 'verbose': 'x', 'filePath': 1})

    def test_unknown_tool_asks(self):
        self.assertListed(ASK, None, self.project, 'mcp__blocked-site-browser__launch_pwa', {'manifestUrl': 'https://evil.com/'})

    def test_init_script_on_reload_asks(self):
        """initScript runs on reload, back, and forward too, which carry no URL."""
        self.assertListed(ASK, None, self.project, 'mcp__blocked-site-browser__navigate_page', {'type': 'reload', 'initScript': 'alert(1)'})

    def test_init_script_on_about_blank_asks(self):
        self.assertListed(ASK, 'about:blank', self.project, extra_input={'initScript': 'alert(1)'})

    def test_reload_allowed(self):
        self.assertListed(ALLOW, None, self.project, 'mcp__blocked-site-browser__navigate_page', {'type': 'reload'})

    def test_snapshot_with_file_path_asks(self):
        self.assertListed(ASK, None, self.project, 'mcp__blocked-site-browser__take_snapshot', {'filePath': '/tmp/x.txt'})

    def test_snapshot_without_file_path_allowed(self):
        self.assertListed(ALLOW, None, self.project, 'mcp__blocked-site-browser__take_snapshot', {'pageId': 1})

    def git(self, repo, *arguments):
        """Uses the fixture HOME and no hooks, so the real git config can't interfere."""
        env = {**os.environ, 'HOME': str(self.home), 'GIT_CONFIG_NOSYSTEM': '1'}
        git = ['git', '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', '-C', str(repo)]
        subprocess.run([*git, *arguments], check=True, env=env)

    def make_repo_with_worktree(self, repo):
        self.git(repo, 'init', '-q')
        self.git(repo, 'commit', '-q', '--allow-empty', '-m', 'x')
        worktree = repo / 'worktree'
        self.git(repo, 'worktree', 'add', '-q', str(worktree))
        return worktree

    def test_bare_repo_worktree_lists_ignored(self):
        """A bare repo has no main checkout whose settings could stand in."""
        bare = self.project / 'repo.git'
        bare.mkdir()
        self.git(bare, 'init', '-q', '--bare')
        source = self.home / 'source'
        self.git(self.home, 'init', '-q', str(source))
        self.git(source, 'commit', '-q', '--allow-empty', '-m', 'x')
        self.git(source, 'push', '-q', str(bare), 'HEAD:main')
        worktree = self.project / 'worktree'
        self.git(bare, 'worktree', 'add', '-q', str(worktree), 'main')
        write_settings(worktree / '.claude/settings.json', ['https://evil.com/'])

        self.assertListed(ASK, 'https://evil.com/', worktree)

    def test_worktree_uses_main_checkout_lists(self):
        """A worktree's tracked settings can be overwritten without a prompt."""
        worktree = self.make_repo_with_worktree(self.project)
        write_settings(worktree / '.claude/settings.json', ['https://evil.com/'])

        self.assertListed(ASK, 'https://evil.com/', worktree)
        self.assertListed(ALLOW, 'https://www.crescentelectric.com/', worktree)

    def test_project_in_a_repo_subdirectory_keeps_its_own_lists(self):
        repo = self.home / 'repo'
        project = repo / 'app/public'
        write_settings(project / '.claude/settings.json', ['https://www.fastenersplus.com/'])
        self.trust(project)
        worktree = self.make_repo_with_worktree(repo)
        (worktree / 'app/public').mkdir(parents=True)

        self.assertListed(ALLOW, 'https://www.fastenersplus.com/', project)
        self.assertListed(ALLOW, 'https://www.fastenersplus.com/', worktree / 'app/public')

    def test_listed_site_asks_for_default_chrome_server(self):
        """The list pre-authorizes only blocked-site-browser, whose input tools are denied."""
        self.assertListed(ASK, 'https://www.homedepot.com/', self.project, 'mcp__chrome-devtools__new_page')

    def test_broken_project_settings_keep_global_list(self):
        (self.project / '.claude/settings.json').write_text('{ not json')
        self.assertListed(ALLOW, 'https://www.homedepot.com/', self.project)
        self.assertListed(ASK, 'https://www.crescentelectric.com/', self.project)


if __name__ == '__main__':
    unittest.main(verbosity=2)
