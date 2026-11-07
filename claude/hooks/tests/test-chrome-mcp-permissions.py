#!/usr/bin/env python3
"""
Tests for chrome-mcp-permissions.py's navigation gate.
Run with: python3 test-chrome-mcp-permissions.py

Every run writes the session usage-gate marker first, so the hook short-circuits
that gate instead of shelling out to `claude -p "/usage"` for several seconds.
The pre-authorization cases read the real project matrix rather than a fixture,
since the point is that the shipped PRE_AUTHORIZED_SITE_MATRICES entry resolves.
The `blockedSiteBrowser.sites` and `chromeDevtools.sites` cases use fixture settings files
under a throwaway HOME.
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


def reason(stdout):
    return json.loads(stdout)['hookSpecificOutput']['permissionDecisionReason']


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
    """Uses a throwaway HOME, so a host on the real global `chromeDevtools.sites` list can't
    change the results."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def assertDecision(self, expected, url, cwd, **run_options):
        super().assertDecision(expected, url, cwd, home=self.home, **run_options)

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
SNAPSHOT_TOOL = 'mcp__blocked-site-browser__take_snapshot'


def write_settings(path, sites, key='blockedSiteBrowser'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: {'sites': sites}}))


class ListTestCase(GateTestCase):
    """Uses a throwaway HOME, so the real global list and trust config can't change the
    results."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name).resolve()
        self.project = self.home / 'project'
        self.untrusted = self.home / 'untrusted'
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


class BlockedSiteListTest(ListTestCase):

    def setUp(self):
        super().setUp()
        write_settings(self.home / '.claude/settings.json', ['https://www.homedepot.com/'])
        write_settings(self.project / '.claude/settings.json', ['https://www.crescentelectric.com/', 'www.lowes.com', {'url': 'https://www.ebay.com/'}, 42])
        write_settings(self.project / '.claude/settings.local.json', ['https://www.acehardware.com/'])
        write_settings(self.untrusted / '.claude/settings.json', ['https://www.crescentelectric.com/'])

    def test_global_site_allowed_outside_any_project(self):
        self.assertListed(ALLOW, 'https://www.homedepot.com/p/123')

    def test_global_site_allowed_inside_project(self):
        self.assertListed(ALLOW, 'https://www.homedepot.com/', self.project)

    def test_project_site_allowed(self):
        self.assertListed(ALLOW, 'https://www.crescentelectric.com/', self.project)

    def test_project_site_asks_when_only_an_ancestor_is_trusted(self):
        self.trust(self.home)
        self.assertListed(ASK, 'https://www.crescentelectric.com/', self.project)

    def test_folder_inside_a_trusted_project_lists_ignored(self):
        """A worktree sits inside its trusted main checkout, but doesn't inherit its trust."""
        worktree = self.project / '.claude/worktrees/x'
        write_settings(worktree / '.claude/settings.json', ['https://evil.com/'])
        self.assertListed(ASK, 'https://evil.com/', worktree)

    def test_bare_host_and_object_entries_allowed(self):
        self.assertListed(ALLOW, 'https://www.lowes.com/', self.project)
        self.assertListed(ALLOW, 'https://www.ebay.com/', self.project)

    def test_local_settings_site_allowed(self):
        self.assertListed(ALLOW, 'https://www.acehardware.com/', self.project)

    def test_project_that_is_not_a_git_repository_allowed(self):
        self.trust(self.untrusted)
        self.assertListed(ALLOW, 'https://www.crescentelectric.com/', self.untrusted)

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

    def test_snapshot_into_working_directory_scratch_allowed(self):
        self.assertListed(ALLOW, None, self.project, SNAPSHOT_TOOL, {'pageId': 1, 'filePath': str(self.home / '.claude/tmp/page.txt')})

    def test_snapshot_into_session_scratchpad_asks(self):
        """The MCP server only writes inside its client roots and its own temp directory."""
        scratchpad = Path(tempfile.gettempdir()).resolve() / f'claude-{os.getuid()}' / 'project' / 'session' / 'scratchpad'
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(scratchpad / 'page.txt')})

    def test_snapshot_without_a_txt_name_asks(self):
        """The server swaps any extension for `.txt`, so a link at the `.txt` name would be written through."""
        scratch = self.home / '.claude/tmp'
        scratch.mkdir(parents=True)
        (scratch / 'page.txt').symlink_to(self.home / '.claude/settings.json')
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(scratch / 'page.html')})
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(scratch / 'page')})
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(scratch / '.txt')})

    def test_snapshot_at_the_scratch_root_asks(self):
        """The server would write `.claude/tmp.txt`, beside scratch rather than in it."""
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(self.home / '.claude/tmp')})
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(self.home / '.claude/tmp') + '/'})

    def test_snapshot_dot_dot_through_a_scratch_symlink_asks(self):
        """Node collapses `..` as text, so this writes `notes.txt` beside `.claude`, not in scratch."""
        deep = self.home / '.claude/tmp/a/b/c'
        deep.mkdir(parents=True)
        (self.home / '.claude/tmp/deep').symlink_to(deep)
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(self.home / '.claude/tmp/deep/../../../notes.txt')})

    def test_snapshot_outside_scratch_asks(self):
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(self.home / '.claude/settings.json')})
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(self.home / '.claude/tmp/../settings.json')})

    def test_snapshot_relative_file_path_asks(self):
        """The MCP server resolves a relative path against its own directory, not the session's."""
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': '.claude/tmp/page.txt'})

    def test_snapshot_through_a_scratch_symlink_asks(self):
        scratch = self.home / '.claude/tmp'
        scratch.mkdir(parents=True)
        (scratch / 'link.txt').symlink_to(self.home / '.claude/settings.json')
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(scratch / 'link.txt')})

    def test_apex_and_www_hosts_are_the_same_site(self):
        self.assertListed(ALLOW, 'https://homedepot.com/p/123')
        write_settings(self.home / '.claude/settings.json', ['homedepot.com'])
        self.assertListed(ALLOW, 'https://www.homedepot.com/p/123')

    def test_project_list_covers_the_www_twin(self):
        self.assertListed(ALLOW, 'https://crescentelectric.com/', self.project)

    def test_local_list_covers_the_www_twin(self):
        self.assertListed(ALLOW, 'https://acehardware.com/', self.project)

    def test_snapshot_onto_a_hard_link_asks(self):
        scratch = self.home / '.claude/tmp'
        scratch.mkdir(parents=True)
        target = self.home / 'notes.txt'
        target.write_text('mine')
        os.link(target, scratch / 'page.txt')
        self.assertListed(ASK, None, self.project, SNAPSHOT_TOOL, {'filePath': str(scratch / 'page.txt')})

    def test_other_subdomains_are_not_the_same_site(self):
        self.assertListed(ASK, 'https://evil.homedepot.com/')
        self.assertListed(ASK, 'https://www.www.homedepot.com/')

    def test_snapshot_without_file_path_allowed(self):
        self.assertListed(ALLOW, None, self.project, 'mcp__blocked-site-browser__take_snapshot', {'pageId': 1})

    def test_listed_site_asks_for_default_chrome_server(self):
        """The list pre-authorizes only blocked-site-browser, whose input tools are denied."""
        self.assertListed(ASK, 'https://www.homedepot.com/', self.project, 'mcp__chrome-devtools__new_page')

    def test_broken_project_settings_keep_global_list(self):
        (self.project / '.claude/settings.json').write_text('{ not json')
        self.assertListed(ALLOW, 'https://www.homedepot.com/', self.project)
        self.assertListed(ASK, 'https://www.crescentelectric.com/', self.project)


CHROME_TOOL = 'mcp__chrome-devtools__new_page'
PLUGIN_CHROME_TOOL = 'mcp__plugin_chrome-devtools-mcp_chrome-devtools__navigate_page'


class ChromeDevtoolsListTest(ListTestCase):

    def setUp(self):
        super().setUp()
        write_settings(self.home / '.claude/settings.json', ['https://qa.example.com/'], 'chromeDevtools')
        write_settings(self.project / '.claude/settings.json', ['staging.example.com'], 'chromeDevtools')
        write_settings(self.project / '.claude/settings.local.json', ['https://www.preprod.example.com/'], 'chromeDevtools')
        write_settings(self.untrusted / '.claude/settings.local.json', ['https://evil.com/'], 'chromeDevtools')

    def test_global_site_allowed_outside_any_project(self):
        self.assertListed(ALLOW, 'https://qa.example.com/page', tool_name=CHROME_TOOL)

    def test_project_sites_allowed(self):
        self.assertListed(ALLOW, 'https://staging.example.com/', self.project, CHROME_TOOL)
        self.assertListed(ALLOW, 'https://www.preprod.example.com/', self.project, CHROME_TOOL)

    def test_plugin_server_uses_the_same_list(self):
        self.assertListed(ALLOW, 'https://staging.example.com/', self.project, PLUGIN_CHROME_TOOL, {'type': 'url'})

    def test_www_twin_allowed(self):
        self.assertListed(ALLOW, 'https://www.staging.example.com/', self.project, CHROME_TOOL)
        self.assertListed(ALLOW, 'https://preprod.example.com/', self.project, CHROME_TOOL)

    def test_other_subdomains_ask(self):
        self.assertListed(ASK, 'https://evil.staging.example.com/', self.project, CHROME_TOOL)
        self.assertListed(ASK, 'https://example.com/', self.project, CHROME_TOOL)

    def test_project_sites_ask_outside_project(self):
        self.assertListed(ASK, 'https://staging.example.com/', tool_name=CHROME_TOOL)

    def test_untrusted_project_sites_ask(self):
        self.assertListed(ASK, 'https://evil.com/', self.untrusted, CHROME_TOOL)

    def test_list_does_not_grant_a_lookalike_server(self):
        self.assertListed(ASK, 'https://qa.example.com/', self.project, 'mcp__other-chrome-devtools__new_page')

    def test_list_does_not_grant_blocked_site_browser(self):
        self.assertListed(ASK, 'https://qa.example.com/', self.project)
        self.assertListed(ASK, 'https://staging.example.com/', self.project)


if __name__ == '__main__':
    unittest.main(verbosity=2)
