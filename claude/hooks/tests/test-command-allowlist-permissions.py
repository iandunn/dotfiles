#!/usr/bin/env python3
"""
Tests for command-allowlist-permissions.py.
Run with: python3 test-command-allowlist-permissions.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'command-allowlist-permissions.py'
ALLOW = 'allow'
ASK = 'ask'
DENY = 'deny'


def run(payload):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip(), result.returncode


def decision(stdout):
    if not stdout:
        return None
    return json.loads(stdout)['hookSpecificOutput']['permissionDecision']


class DecisionTest(unittest.TestCase):

    def outcome(self, command):
        stdout, code = run({'tool_name': 'Bash', 'tool_input': {'command': command}})
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        return decision(stdout)

    def assertAllows(self, command):
        self.assertEqual(self.outcome(command), ALLOW, f'expected an allow for: {command}')

    def assertAsks(self, command):
        self.assertEqual(self.outcome(command), ASK, f'expected a prompt for: {command}')

    def assertDenies(self, command):
        self.assertEqual(self.outcome(command), DENY, f'expected a refusal for: {command}')

    def assertSilent(self, command):
        self.assertIsNone(self.outcome(command), f'expected no opinion for: {command}')


class WpAllowlistTest(DecisionTest):

    def test_bare_globals_allowed(self):
        self.assertAllows('wp --info')
        self.assertAllows('wp --version')

    def test_read_only_subcommands_allowed(self):
        self.assertAllows('wp plugin list')
        self.assertAllows('wp plugin list --format=json')
        self.assertAllows('wp option get siteurl')
        self.assertAllows('wp user list')
        self.assertAllows('wp help')

    def test_sanctioned_writes_allowed(self):
        self.assertAllows('wp option update blogname Foo')
        self.assertAllows('wp option delete my_option')
        self.assertAllows('wp core update')
        self.assertAllows('wp plugin update akismet')
        self.assertAllows('wp transient delete update_plugins')

    def test_destructive_subcommands_ask(self):
        self.assertAsks('wp user create admin admin@example.com')
        self.assertAsks('wp user delete 1')
        self.assertAsks('wp plugin install akismet')
        self.assertAsks('wp plugin delete akismet')
        self.assertAsks('wp db reset')
        self.assertAsks('wp db import backup.sql')
        self.assertAsks('wp post delete 1')
        self.assertAsks('wp eval "echo 1;"')

    def test_narrower_transient_delete_does_not_widen(self):
        self.assertAsks('wp transient delete some_other_key')

    def test_bare_command_asks(self):
        self.assertAsks('wp')


class TokenBoundaryTest(DecisionTest):

    def test_prefix_must_start_the_command(self):
        self.assertAsks('wp bad plugin list')

    def test_partial_token_does_not_match(self):
        """`post list` must not vouch for a different subcommand that merely starts with it."""
        self.assertAsks('wp post listing')
        self.assertAsks('wp option getx foo')


class WpGlobalFlagTest(DecisionTest):

    def test_leading_url_is_stepped_over(self):
        self.assertAllows('wp --url=example.test post list --post_type=page')

    def test_several_leading_globals_are_stepped_over(self):
        self.assertAllows('wp --url=example.test --skip-plugins --quiet option get home')

    def test_code_loading_globals_ask(self):
        self.assertAsks('wp --require=evil.php post list')
        self.assertAsks('wp --exec="echo 1;" post list')

    def test_remote_execution_globals_ask(self):
        self.assertAsks('wp --ssh=user@host post list')
        self.assertAsks('wp --http=user@host option update home evil')

    def test_unknown_leading_global_asks(self):
        self.assertAsks('wp --not-a-real-global post list')


class MetacharacterGuardTest(DecisionTest):

    def test_chained_command_asks(self):
        self.assertAsks('wp option get siteurl && wp db reset --yes')

    def test_semicolon_asks(self):
        self.assertAsks('wp option get siteurl; rm -rf /tmp/x')

    def test_command_substitution_asks(self):
        self.assertAsks('wp option get $(id)')

    def test_pipe_asks(self):
        self.assertAsks('wp option get siteurl | tee /tmp/x')

    def test_redirect_asks(self):
        self.assertAsks('wp post list > /tmp/x')

    def test_quoted_substitution_still_asks(self):
        """The guard runs before tokenizing, so quotes can't hide a metacharacter from it."""
        self.assertAsks('wp option get "$(id)"')


class BinaryResolutionTest(DecisionTest):

    LOCAL_WP = '/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/posix/wp'

    def test_absolute_path_resolves_to_wp(self):
        self.assertAllows(f'{self.LOCAL_WP} plugin list')

    def test_quoted_absolute_path_resolves_to_wp(self):
        self.assertAllows(f'"{self.LOCAL_WP}" plugin list')

    def test_command_prefix_is_stripped(self):
        self.assertAllows('command wp plugin list')

    def test_unknown_binary_is_left_alone(self):
        self.assertSilent('drush cache-rebuild')

    def test_unlisted_path_to_a_covered_name_denied(self):
        """Any executable can be named `wp`; only the spellings in BINARY_ALLOWED_PATHS resolve."""
        self.assertDenies('/tmp/evil/wp plugin list')
        self.assertDenies('./wp plugin list')


class VipProxiedWpTest(DecisionTest):

    def test_target_without_separator(self):
        self.assertAllows('vip @co-williams.staging wp post list')

    def test_target_with_separator(self):
        self.assertAllows('vip @co-williams.staging -- wp post list')

    def test_flag_style_target_denied(self):
        """Flag-style targets are denied outright: `@org.env` is the only accepted spelling."""
        self.assertDenies('vip -a co-williams -e staging wp post list')

    def test_inline_flag_style_target_denied(self):
        self.assertDenies('vip --app=co-williams --env=staging -- wp post list')

    def test_debug_flag_is_stepped_over(self):
        self.assertAllows('vip -d @co-williams.staging wp post list')

    def test_proxied_url_global_is_stepped_over(self):
        self.assertAllows('vip @co-williams.staging -- wp --url=dev.example.com post list')

    def test_unlisted_proxied_subcommand_asks(self):
        self.assertAsks('vip @co-williams.staging wp db reset')

    def test_proxied_code_loading_global_asks(self):
        self.assertAsks('vip @co-williams.staging -- wp --require=evil.php post list')
        self.assertAsks('vip @co-williams.staging -- wp --http=x post list')

    def test_interactive_shell_asks(self):
        self.assertAsks('vip @co-williams.staging -- wp')


class VipEnvironmentGateTest(DecisionTest):

    def test_production_asks_even_for_an_allowlisted_read(self):
        self.assertAsks('vip @co-williams.production wp post list')

    def test_flag_style_production_denied(self):
        self.assertDenies('vip -a co-williams -e production wp post list')

    def test_unrecognized_environment_asks(self):
        self.assertAsks('vip @co-williams.sandbox wp post list')

    def test_conflicting_targets_denied(self):
        """Two target spellings on one line would leave the hook guessing which one VIP honors."""
        self.assertDenies('vip @co-williams.production -e staging wp post list')
        self.assertDenies('vip -e production -e staging wp post list')
        self.assertDenies('vip @co-williams.production @co-williams.staging wp post list')

    def test_at_target_after_the_subcommand_denied(self):
        self.assertDenies('vip wp @co-williams.staging post list')

    def test_missing_environment_asks(self):
        self.assertAsks('vip @co-williams wp post list')

    def test_no_target_at_all_asks(self):
        self.assertAsks('vip wp post list')

    def test_develop_and_preprod_allowed(self):
        self.assertAllows('vip @co-williams.develop wp post list')
        self.assertAllows('vip @co-williams.preprod wp post list')


class VipConfirmationFlagTest(DecisionTest):

    def test_yes_asks_despite_an_allowlisted_read(self):
        self.assertAsks('vip @co-williams.staging --yes -- wp user list')

    def test_short_yes_asks(self):
        self.assertAsks('vip @co-williams.staging -y -- wp user list')

    def test_yes_after_the_separator_asks(self):
        self.assertAsks('vip @co-williams.staging -- wp user list --yes')


class VipNativeTest(DecisionTest):

    def test_environmentless_reads_allowed(self):
        self.assertAllows('vip whoami')
        self.assertAllows('vip app list')

    def test_version_and_help_allowed(self):
        self.assertAllows('vip --version')
        self.assertAllows('vip -v')
        self.assertAllows('vip --help')

    def test_environment_scoped_reads_allowed(self):
        self.assertAllows('vip @co-williams.staging logs')
        self.assertAllows('vip @co-williams.staging slowlogs')

    def test_production_scoped_read_asks(self):
        self.assertAsks('vip @co-williams.production logs')

    def test_data_moving_subcommands_ask(self):
        self.assertAsks('vip @co-williams.staging sync')
        self.assertAsks('vip @co-williams.staging import sql backup.sql')
        self.assertAsks('vip @co-williams.staging export sql')
        self.assertAsks('vip @co-williams.staging backup db')
        self.assertAsks('vip @co-williams.staging db')

    def test_config_writes_ask(self):
        self.assertAllows('vip @co-williams.staging config envvar list')
        self.assertAsks('vip @co-williams.staging config envvar set FOO')

    def test_bare_vip_asks(self):
        self.assertAsks('vip')


class McpInputTest(DecisionTest):
    """The Local WP MCP server passes bare WP-CLI arguments with no `wp` and a leading `--url=`."""

    def outcome_from_args(self, args):
        stdout, code = run({'tool_name': 'mcp__local-wp__wp_cli', 'tool_input': {'args': args}})
        self.assertEqual(code, 0, f'non-zero exit for args: {args}')
        return decision(stdout)

    def test_allowlisted_args_allowed(self):
        self.assertEqual(self.outcome_from_args('plugin list'), ALLOW)

    def test_leading_url_global_allowed(self):
        args = '--url=publix.test/jobs post list --post_type=page --format=table'
        self.assertEqual(self.outcome_from_args(args), ALLOW)

    def test_unlisted_args_ask(self):
        self.assertEqual(self.outcome_from_args('db reset'), ASK)

    def test_empty_args_ask(self):
        self.assertEqual(self.outcome_from_args(''), ASK)


class NoOpinionTest(DecisionTest):
    """The `if:` filters fail open on lines Claude Code can't decompose, so the hook also runs on
    commands it has no allowlist for. Those must exit silently so `settings.json` applies, and
    these examples are real prompts from the 2026-08-28 investigation."""

    def test_compound_lines_without_a_covered_command_are_left_alone(self):
        self.assertSilent('jq -r .a f.json | head -3')
        self.assertSilent('cd "$TMPDIR" && jq -r keys page.json')
        self.assertSilent('which claude; ls -la $(which claude)')
        self.assertSilent(
            'for f in a.html b.html; do printf "%s " "$f"; command rg -o -m1 "<title>" "$f"; done'
        )

    def test_unparseable_lines_without_a_covered_command_are_left_alone(self):
        self.assertSilent("python3 - <<'EOF'\nprint(\"don't\")\nEOF")

    def test_wp_as_a_word_in_paths_is_not_a_mention(self):
        self.assertSilent('grep -c hero wp-content/themes/publix/style.css | head -1')
        self.assertSilent('cat wp-config.php | head -5')

    def test_wp_inside_a_larger_token_is_left_alone(self):
        self.assertSilent("grep 'wp option' notes.txt")

    def test_covered_command_behind_a_launcher_asks(self):
        """The hook can't vouch for an execution it isn't parsing, but it can insist on a prompt."""
        self.assertAsks('env wp db reset --yes')
        self.assertAsks('command command wp db reset --yes')
        self.assertAsks('VIP_DEBUG=1 vip @app.production wp post delete 1')

    def test_bare_wp_as_an_argument_asks(self):
        """The accepted cost of the launcher check: a bare `wp` token prompts even as data."""
        self.assertAsks('grep wp notes.txt')

    def test_compound_line_that_runs_wp_still_asks(self):
        """The mention check must not weaken the metacharacter guard."""
        self.assertAsks('wp option get siteurl && wp db reset --yes')
        self.assertAsks('cd /site && wp site list --fields=blog_id 2>&1 | head -20')

    def test_compound_line_that_runs_vip_still_asks(self):
        self.assertAsks('vip @app.staging wp post list | head -3')


class MalformedInputTest(DecisionTest):

    def test_unbalanced_quote_asks(self):
        self.assertAsks('wp option get "unterminated')

    def test_missing_tool_input_is_left_alone(self):
        """A Bash payload with no command carries nothing for this hook to judge."""
        stdout, code = run({'tool_name': 'Bash', 'tool_input': {}})
        self.assertEqual(code, 0)
        self.assertIsNone(decision(stdout))


if __name__ == '__main__':
    unittest.main(verbosity=2)
