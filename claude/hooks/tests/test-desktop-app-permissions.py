#!/usr/bin/env python3
"""
Tests for desktop-app-permissions.py.
Run with: python3 test-desktop-app-permissions.py
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'desktop-app-permissions.py'
ASK = 'ask'
DENY = 'deny'


def run(command):
    """Run the hook with a command string, return (stdout, returncode)."""
    payload = {'tool_name': 'Bash', 'tool_input': {'command': command}}
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


class DecisionTest(unittest.TestCase):

    def assertAsks(self, command):
        out, code = run(command)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), ASK, f'expected a prompt for: {command}')

    def assertDenies(self, command):
        out, code = run(command)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertEqual(decision(out), DENY, f'expected a refusal for: {command}')

    def assertSilent(self, command):
        out, code = run(command)
        self.assertEqual(code, 0, f'non-zero exit for: {command}')
        self.assertIsNone(decision(out), f'expected silence for: {command}')


class LaunchDetectionTest(DecisionTest):

    def test_bare_launcher_asks(self):
        self.assertAsks('code .')

    def test_launcher_after_operator_asks(self):
        self.assertAsks('npm run build && code .')

    def test_wrappers_stripped_before_matching(self):
        self.assertAsks('FOO=1 nohup firefox --headless')

    def test_open_asks(self):
        self.assertAsks('open -a Slack')

    def test_bundle_executable_path_asks(self):
        self.assertAsks('/Applications/Firefox.app/Contents/MacOS/firefox --version')

    def test_applications_directory_path_asks(self):
        self.assertAsks('/Applications/Firefox.app/Contents/MacOS/../Resources/foo')

    def test_automation_driver_via_runner_asks(self):
        self.assertAsks('npx playwright test')

    def test_applescript_targeting_an_app_asks(self):
        self.assertAsks('osascript -e \'tell application "Safari" to quit\'')

    def test_launchctl_start_asks(self):
        self.assertAsks('launchctl start com.example.agent')

    def test_bundle_path_inside_bash_c_asks(self):
        self.assertAsks('bash -c "/Applications/Firefox.app/Contents/MacOS/firefox --version"')

    def test_bundle_path_handed_to_xargs_asks(self):
        self.assertAsks('echo x | xargs /Applications/Firefox.app/Contents/MacOS/firefox')


class WriteDenialTest(DecisionTest):
    """A path this command's own syntax names as a destination earns a refusal, not a prompt."""

    def test_redirect_into_a_bundle_is_denied(self):
        self.assertDenies('cat foo > /Applications/iTerm.app/Contents/MacOS/iTerm2')

    def test_appending_into_a_bundle_is_denied(self):
        self.assertDenies('echo x >>/Applications/iTerm.app/Contents/Info.plist')

    def test_copy_into_the_applications_directory_is_denied(self):
        self.assertDenies('cp notes.txt /Applications')

    def test_copy_out_of_a_bundle_stays_silent(self):
        self.assertSilent('cp /Applications/Firefox.app/Contents/Info.plist ~/tmp/')

    def test_moving_a_bundle_out_is_denied(self):
        self.assertDenies('mv /Applications/Firefox.app ~/tmp/')

    def test_removing_a_bundle_is_denied(self):
        self.assertDenies('rm -rf /Applications/Firefox.app')

    def test_making_a_directory_in_applications_is_denied(self):
        self.assertDenies('mkdir -p /Applications/Firefox.app/Contents/Extra')

    def test_chmod_on_a_bundle_binary_is_denied(self):
        self.assertDenies('chmod +x /Applications/Firefox.app/Contents/MacOS/firefox')

    def test_in_place_edit_of_a_bundle_file_is_denied(self):
        self.assertDenies('sed -i.bak s/a/b/ /Applications/Firefox.app/Contents/Info.plist')

    def test_plutil_replace_in_a_bundle_is_denied(self):
        self.assertDenies(
            'plutil -replace CFBundleName -string x /Applications/Firefox.app/Contents/Info.plist')

    def test_plutil_read_of_a_bundle_stays_silent(self):
        self.assertSilent('plutil -p /Applications/Firefox.app/Contents/Info.plist')

    def test_unzip_into_applications_is_denied(self):
        self.assertDenies('unzip build.zip -d /Applications')

    def test_descriptor_redirect_is_not_a_path(self):
        self.assertSilent('grep -a PASTE /Applications/iTerm.app/Contents/Info.plist 2>&1')

    def test_write_outside_an_application_directory_stays_silent(self):
        self.assertSilent('cp notes.txt ~/tmp/notes.txt')


class QuotedOperatorTest(DecisionTest):
    """An operator inside quotes is argument text, not a new command position."""

    def test_pipe_in_grep_pattern_stays_silent(self):
        self.assertSilent("grep -E 'files touched|code comments:' harvest.log")

    def test_pipe_in_double_quoted_pattern_stays_silent(self):
        self.assertSilent('rg "zoom|slack" notes.md')

    def test_semicolon_in_commit_message_stays_silent(self):
        self.assertSilent('git commit -m "fix the parser; code cleanup follows"')

    def test_ampersands_in_quoted_pattern_stay_silent(self):
        self.assertSilent("grep -rn 'a&&code' .")

    def test_backtick_in_quoted_argument_stays_silent(self):
        self.assertSilent("""git commit -m 'wrap `code` in backticks'""")

    def test_escaped_pipe_stays_silent(self):
        self.assertSilent(r'grep -E files\|code harvest.log')

    def test_substitution_inside_double_quotes_still_detected(self):
        self.assertAsks('echo "$(code --version)"')

    def test_backtick_substitution_inside_double_quotes_still_detected(self):
        self.assertAsks('echo "`code --version`"')

    def test_substitution_inside_single_quotes_stays_silent(self):
        self.assertSilent("""echo '$(code --version)'""")

    def test_escaped_substitution_in_double_quotes_stays_silent(self):
        self.assertSilent(r'echo "\$(code --version)"')

    def test_real_pipe_after_a_quoted_one_still_detected(self):
        self.assertAsks("grep -E 'a|b' harvest.log | code -")


class NonLaunchTest(DecisionTest):

    def test_app_name_as_argument_stays_silent(self):
        self.assertSilent('grep -i firefox /var/log/system.log')

    def test_reading_a_bundle_path_stays_silent(self):
        self.assertSilent('ls -d /Applications/Firefox*.app')

    def test_grepping_a_bundle_binary_stays_silent(self):
        self.assertSilent('grep -o -a PASTE /Applications/iTerm.app/Contents/MacOS/iTerm2')

    def test_inspecting_a_bundle_binary_stays_silent(self):
        self.assertSilent('codesign -dv /Applications/Firefox.app/Contents/MacOS/firefox')

    def test_excluded_bundle_binary_stays_silent(self):
        path = ('/Applications/Local.app/Contents/Resources/extraResources'
                '/bin/wp-cli/posix/wp')
        self.assertSilent('%s post list' % path)

    def test_python_open_call_in_a_heredoc_stays_silent(self):
        self.assertSilent("python3 - <<'PY'\nopen('/tmp/x').read()\nPY")

    def test_non_bash_tool_stays_silent(self):
        payload = {'tool_name': 'Read', 'tool_input': {'command': 'code .'}}
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), '')


class ParsedLineTest(DecisionTest):
    """Launches and writes bash_ast finds where the old splitter could not see them."""

    def test_launch_inside_command_substitution_asks(self):
        self.assertAsks('x=$(open -a Safari)')

    def test_launch_inside_if_asks(self):
        self.assertAsks('if true; then code .; fi')

    def test_launch_inside_bash_c_asks(self):
        self.assertAsks("bash -c 'open -a Safari'")

    def test_launch_behind_env_asks(self):
        self.assertAsks('env FOO=1 "open" -a Safari')

    def test_launch_behind_command_asks(self):
        self.assertAsks('command \\open -a Safari')

    def test_launch_behind_sudo_with_options_asks(self):
        self.assertAsks('sudo -u root code .')

    def test_launch_after_apostrophe_in_quoted_heredoc_asks(self):
        self.assertAsks("cat <<'EOF'\ndon't\nEOF\nopen -a Safari")

    def test_launch_after_substitution_in_double_quotes_asks(self):
        self.assertAsks('echo "$(date)" && code .')

    def test_redirect_attached_to_a_word_is_denied(self):
        self.assertDenies('echo x>/Applications/Firefox.app/Contents/Info.plist')

    def test_redirect_with_dup_spelling_is_denied(self):
        self.assertDenies('echo x >&/Applications/Firefox.app/Contents/Info.plist')

    def test_applescript_in_heredoc_asks(self):
        self.assertAsks("osascript <<'EOF'\ntell application \"Safari\" to quit\nEOF")

    def test_variable_in_command_position_asks(self):
        self.assertAsks('"$BROWSER" https://example.com')

    def test_unparseable_line_asks(self):
        self.assertAsks('echo "unterminated')

    def test_ordinary_command_stays_silent(self):
        self.assertSilent('git status --short')


class ReaderAndWriterPolicyTest(DecisionTest):

    def test_rg_with_pre_on_a_bundle_binary_asks(self):
        self.assertAsks('rg --pre /Applications/Firefox.app/Contents/MacOS/firefox x .')

    def test_rg_on_a_bundle_binary_stays_silent(self):
        self.assertSilent('rg -a PASTE /Applications/iTerm.app/Contents/MacOS/iTerm2')

    def test_pager_on_a_bundle_binary_asks(self):
        self.assertAsks('less /Applications/Firefox.app/Contents/MacOS/firefox')

    def test_attached_short_flag_destination_is_denied(self):
        self.assertDenies('unzip build.zip -d/Applications')

    def test_tar_attached_directory_is_denied(self):
        self.assertDenies('tar -xf build.tar -C/Applications')

    def test_find_delete_in_a_bundle_is_denied(self):
        self.assertDenies('find /Applications/Firefox.app -name "*.log" -delete')

    def test_find_exec_rm_in_a_bundle_is_denied(self):
        self.assertDenies('find /Applications/Firefox.app -name "*.log" -exec rm -f {} +')

    def test_find_exec_reader_in_a_bundle_stays_silent(self):
        self.assertSilent('find /Applications/Firefox.app -name Info.plist -exec plutil -p {} \\;')

    def test_find_without_delete_stays_silent(self):
        self.assertSilent('find /Applications/Firefox.app -name "*.plist"')


class IsolationNoteTest(unittest.TestCase):

    def reason(self, command):
        out, _ = run(command)
        return json.loads(out)['hookSpecificOutput']['permissionDecisionReason']

    def test_missing_flags_are_named(self):
        self.assertIn('Missing isolation flags', self.reason('firefox --headless'))

    def test_complete_flags_are_acknowledged(self):
        command = 'firefox --profile /tmp/ff --no-remote --new-instance --headless'
        self.assertIn('Isolation flags are present', self.reason(command))


if __name__ == '__main__':
    unittest.main()
