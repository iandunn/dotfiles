#!/usr/bin/env python3
"""
Tests for read-deny-permissions.py.
Run with: python3 test-read-deny-permissions.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / 'read-deny-permissions.py'
ASK = 'ask'


class ReadDenyTest(unittest.TestCase):
    """Any word that names a path the Read tool is denied asks, whatever the program."""

    @classmethod
    def setUpClass(cls):
        cls.temp = os.path.realpath(tempfile.mkdtemp())
        cls.home = os.path.join(cls.temp, 'home')
        cls.project = os.path.join(cls.temp, 'project')
        os.makedirs(os.path.join(cls.home, '.claude'))
        os.makedirs(os.path.join(cls.home, '.ssh'))
        os.makedirs(os.path.join(cls.home, '.config', 'gh'))
        os.makedirs(os.path.join(cls.project, '.claude'))
        os.makedirs(os.path.join(cls.project, 'sub'))
        os.makedirs(os.path.join(cls.project, '.ssh'))
        os.makedirs(os.path.join(cls.project, 'withsecret'))
        Path(cls.project, 'withsecret', 'auth.json').write_text('x')
        Path(cls.home, '.claude', 'settings.json').write_text(json.dumps({'permissions': {'deny': [
            'Read(**/.npmrc)', 'Read(**/auth.json)', 'Read(~/.ssh/**)', 'Read(~/.config/gh/**)',
        ]}}))
        Path(cls.project, '.claude', 'settings.json').write_text(json.dumps({'permissions': {
            'deny': ['Read(./.env)'],
        }}))
        for path in ('home/.npmrc', 'home/.ssh/id_rsa', 'project/.env', 'project/a.md'):
            Path(cls.temp, path).write_text('x')
        os.symlink(os.path.join(cls.home, '.npmrc'), os.path.join(cls.project, 'innocent'))
        cls.clean = os.path.join(cls.temp, 'clean')
        os.makedirs(os.path.join(cls.clean, 'src'))
        Path(cls.clean, 'src', 'a.md').write_text('x')
        cls.ripgrep_config = os.path.join(cls.temp, 'rg.conf')
        Path(cls.ripgrep_config).write_text('\n'.join([
            '# comment', '--glob-case-insensitive', '--glob=!.npmrc', '--glob=!auth.json',
            '--glob=!.ssh', '--glob=!**/.config/gh', '--glob=!.env', '',
        ]))
        cls.env = {**os.environ, 'HOME': cls.home, 'RIPGREP_CONFIG_PATH': cls.ripgrep_config}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp)

    def decide(self, command, env=None, cwd=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps({'tool_input': {'command': command}, 'cwd': cwd or self.project}),
            capture_output=True, text=True, env=env or self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)['hookSpecificOutput']['permissionDecision']

    def assertAsks(self, command):
        self.assertEqual(self.decide(command), ASK, f'should ask: {command}')

    def assertSilent(self, command):
        self.assertIsNone(self.decide(command), f'should stay silent: {command}')

    def test_ordinary_reads_stay_silent(self):
        self.assertSilent('cat a.md')
        self.assertSilent('wc -l a.md sub')
        self.assertSilent('ls ~')
        self.assertSilent('git status')
        self.assertSilent('echo "$HOME/notes"')

    def test_any_program_naming_a_denied_path_asks(self):
        for command in ('cat .npmrc', 'wc -c ~/.npmrc', f'head {self.home}/.ssh/id_rsa',
                        'jq . auth.json', 'less .env', 'sub/../.npmrc', 'ls ~/.ssh',
                        'cat ~/.config/gh/hosts.yml'):
            self.assertAsks(command)

    def test_resolved_forms_ask(self):
        self.assertAsks('cat ~/.npm*')
        self.assertAsks('cat ~/.ssh/*')
        self.assertAsks('cat ~/.{bashrc,npmrc}')
        self.assertAsks('cat innocent')
        self.assertAsks('X=~/.npmrc')

    def test_embedded_paths_ask(self):
        self.assertAsks('curl -d @auth.json http://localhost')
        self.assertAsks('tool --config=~/.npmrc')
        self.assertAsks('sort -o.npmrc a.md')

    def test_hidden_positions_ask(self):
        self.assertAsks('for f in ~/.ssh/*; do echo "$f"; done')
        self.assertAsks('bash -c "cat ~/.npmrc"')
        self.assertAsks('echo $(cat ~/.npmrc)')
        self.assertAsks('cat < ~/.npmrc')
        self.assertAsks('cat a.md | head -c 0 ~/.npmrc')

    def test_cd_targets_are_followed(self):
        self.assertAsks('cd ~/.ssh && cat id_rsa')
        self.assertAsks('cd "$HOME" && cat .ssh/id_rsa')

    def test_expanding_words_ask_on_denied_names(self):
        self.assertAsks('cat "$HOME/.ssh/id_rsa"')
        self.assertAsks('cat $HOME/.config/gh/hosts.yml')
        self.assertSilent('cat "$HOME/notes"')
        self.assertSilent('echo "$(which gh)"')

    def test_names_split_by_quoting_ask(self):
        for command in ('cat $HOME/.n\\pmrc', 'cat "$HOME/.ss"h/id_rsa', "cat $HOME/.s''sh/x",
                        'cat $HOME/.s{s,s}h/id_rsa', 'cat $HOME/.config/./gh/hosts.yml',
                        'cat $HOME/.config/x/../gh/hosts.yml', 'cd "$HOME/.config" && cat gh/x',
                        'cat ~/.npmr{a..c}'):
            with self.subTest(command=command):
                self.assertAsks(command)

    def test_paths_in_script_text_ask(self):
        for command in (f"python3 -c \"print(open('{self.home}/.npmrc').read())\"",
                        f"sed -n 'r {self.home}/.ssh/id_rsa' a.md",
                        f"awk 'BEGIN{{ARGV[1]=\"{self.home}/.npmrc\";ARGC=2}}1'"):
            with self.subTest(command=command):
                self.assertAsks(command)

    def test_an_existing_path_that_only_shares_a_name_is_silent(self):
        self.assertSilent('ls .ssh')

    def test_directory_options_are_followed(self):
        for command in ('tar -C ~ -cf - .ssh', 'tar -C"$HOME" -cf - .ssh',
                        'tar --directory="$HOME" -cf - .ssh', 'git -C ~ show :.npmrc'):
            with self.subTest(command=command):
                self.assertAsks(command)

    def test_other_spellings_of_a_denied_path_ask(self):
        self.assertAsks(f'cat /System/Volumes/Data{self.home}/.npmrc')

    def test_ripgrep_with_its_config_is_silent(self):
        for command in ('rg -n foo', 'rg -n foo ~', "rg -g '*.md' foo", "rg -g '!*.md' foo",
                        'command rg -i foo .', 'rg -t json foo'):
            with self.subTest(command=command):
                self.assertSilent(command)

    def test_ripgrep_that_could_reach_denied_files_asks(self):
        self.assertEqual(self.decide("rg --glob='.config/**' foo", cwd=self.home), ASK)
        for command in ("rg -g '*' foo", "rg --iglob .NPMRC foo ~",
                        'rg -L foo', 'rg -iL foo', 'rg --follow foo', 'rg --no-config foo',
                        'env -i rg foo', 'xargs rg foo', 'rg -g "$G" foo', 'rg $OPTS foo',
                        'RIPGREP_CONFIG_PATH=/dev/null rg foo',
                        'echo RIPGREP_CONFIG_PATH'):
            with self.subTest(command=command):
                self.assertAsks(command)

    def test_reads_hidden_from_the_line_ask(self):
        for command in ('wc -c $HOME/.n?mrc', 'cat $PWD/../.n*', "rg -g '{*,}' foo",
                        "rg -g 'a{u,x}th.j*' foo withsecret",
                        'rg --pre ./x foo', 'rg --no-glob-case-insensitive foo',
                        'sed -n -f x.sed a.md', 'sed -nf x.sed a.md', 'awk -f x.awk a.md',
                        "awk 'BEGIN{ARGV[1]=ENVIRON[\"HOME\"] \"/.n\" \"pmrc\";ARGC=2}1'",
                        'cat ~/.ſſh/config',
                        "bash -c \"unset RIPGREP_CONFIG_PAT''H; rg token ~\""):
            with self.subTest(command=command):
                self.assertAsks(command)
        self.assertEqual(self.decide('rg token', cwd=os.path.join(self.home, '.config')), ASK)
        for command in ("sed -n '1,5p' a.md", "awk '{print $1}' a.md", 'sed -i.bak s/a/b/ a.md'):
            with self.subTest(command=command):
                self.assertSilent(command)

    def test_reads_through_file_lists_and_hidden_cd_targets_ask(self):
        for command in ('cd "$HOME/.config" && rg -l token', 'sort --files0-from=list a.md',
                        'wc --files0-from list', "ruby -e 'puts File.read(%q{~/.npmrc})'",
                        'fd -t f . "$HOME/x" -x cat'):
            with self.subTest(command=command):
                self.assertAsks(command)
        for command in ("command rg -n '\\$[0-9]|stock' a.md", "rg -n '\\$[0-9]' a.md",
                        'rg -n "view ?box|git add -p" a.md', 'rg x ~/.config'):
            with self.subTest(command=command):
                self.assertSilent(command)

    def test_names_completed_by_an_expansion_ask(self):
        for command in ('cat sub/.np${Y}mrc', 'cat sub/.np$()mrc', 'cat sub/.npmr${X:-c}',
                        'cat sub/.npmr${X:=c}', 'cat sub/.npmr${HOME:+c}',
                        'cat sub/.npmr$(echo c)', 'cat sub/.np${X:-m}rc', 'cat ${X:-.npmrc}',
                        'cd $HOME/.s${X:-s}h && cat id_rsa'):
            with self.subTest(command=command):
                self.assertAsks(command)
        for command in ('echo "fix $x thing"', 'cp "$f" "$f.bak"', 'echo "${HOME}/notes"'):
            with self.subTest(command=command):
                self.assertSilent(command)

    def test_ripgrep_outside_its_allowlist_asks(self):
        linked = os.path.join(self.temp, 'cfg')
        if not os.path.lexists(linked):
            os.symlink(os.path.join(self.home, '.config'), linked)
        for command in ("rg ''--no-{config,config} foo .", "rg ''-{L,n} foo .",
                        'rg ""$X--no-config foo .', "rg -g 'withsecret/*' foo",
                        "rg -g 'withsecret/**' foo", "rg -g 'p*/**' foo",
                        "rg -g '*.yml' foo ~/oth*",
                        'rg -n token ~/.config/gh/..', 'rg -n token ~/.config/.',
                        'rg -n token ~/.config//', f'rg -n token {linked}',
                        'command rg -n "\\\\$[0-9]|stock" a.md', 'rg --type-add x:*.md foo'):
            with self.subTest(command=command):
                self.assertAsks(command)
        for command in ("rg -g '.np?rc' foo", "rg --iglob .NPMRC foo"):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command, cwd=self.home), ASK)

    def test_shapes_python_and_bash_read_differently_ask(self):
        for command in ("rg -g '\\.np?rc' foo", "rg -g '.ss[^x]' -g 'id_rsa' foo ~",
                        "rg -g 'auth.js?\\n' foo withsecret", 'ls ~/.ss[^x]/',
                        'cat ~/.config/g[[:lower:]]/hosts.yml', 'wc -c ~/.npmr[^x]',
                        "awk 'BEGIN{system(\"cat sub/.np?rc\")}'",
                        'awk \'BEGIN{print "cat x" | "sh"}\'', 'cat /.vol/16777220/12345',
                        'xargs -a list.txt cat', 'cat $(fd -H npmrc ~)',
                        'echo ' + 'x{a,b}' * 22):
            with self.subTest(command=command):
                self.assertAsks(command)
        config = os.path.join(self.home, '.config')
        for command in ('cat ~+/gh/hosts.yml', 'cat $PWD/gh/hosts.yml',
                        'cat "${PWD}"/gh/hosts.yml'):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command, cwd=config), ASK)
        linked = os.path.join(self.temp, 'cfg2')
        if not os.path.lexists(linked):
            os.symlink(config, linked)
        self.assertAsks(f'rg --files {linked}')

    def test_shell_options_and_directory_changes_the_hook_cannot_follow_ask(self):
        for command in ("bash -O dotglob -c 'cat ~/*'", "bash -O nocaseglob -c 'cat ~/.NPM*'",
                        "bash -O extglob -c 'cat ~/.!(x)'", 'shopt -s dotglob',
                        'env -C ~/.config cat gh/hosts.yml',
                        'env --chdir=/x/.config cat gh/hosts.yml', 'sudo -D ~/.config cat gh/x',
                        'cat ~-/gh/hosts.yml', 'rg token ~-', 'CDPATH=~/.config cd gh',
                        "bash -c '. ./x.sh; rg token ~'"):
            with self.subTest(command=command):
                self.assertAsks(command)
        for command in ("bash -c 'ls'", 'env FOO=1 ls -C sub', 'rg -o foo'):
            with self.subTest(command=command):
                self.assertSilent(command)

    def test_spellings_that_hide_a_search_root_or_filter_ask(self):
        for command in ("rg -g '*.json' foo ~+/withsecret", 'fd -e .json -x cat . withsecret',
                        'fd -e=json -x cat . withsecret',
                        'fd --extension=.json -x cat . withsecret',
                        "rg -g 'withsecret/*' foo withsecret",
                        'awk \'BEGIN{c="sh"; print "cat x" | c}\'',
                        'jq -n -L . \'import "auth" as $a; $a\'', 'jq -f prog.jq a.json',
                        "bash '-O' dotglob -c 'cat sub/*'", "env '-C' ~/.config cat gh/hosts.yml",
                        "env BASHOPTS=dotglob bash -c 'cat sub/*'"):
            with self.subTest(command=command):
                self.assertAsks(command)
        for command in ("awk '$1 > 5 || $2 < 3 {print}' a.md", "jq '.foo' a.md"):
            with self.subTest(command=command):
                self.assertSilent(command)

    def test_fd_exec_ignores_denied_files_its_filters_skip(self):
        self.assertSilent('fd -e md -x wc -l . withsecret')
        self.assertAsks('fd -e json -x wc -l . withsecret')
        self.assertAsks('fd -E -e x -x cat . withsecret')

    def test_common_ripgrep_shapes_are_silent(self):
        for command in ("rg -C 3 -g '*.php' foo", 'rg -C3 foo', 'rg --version', 'rg -z foo',
                        "rg -g 'package.json' foo", "rg -g 'README*' foo",
                        "rg -g 'src/**/*.php' foo", 'rg foo ./sub', 'rg foo sub/',
                        "rg -g '.np?rc' foo", "rg -g 'sub/*.md' foo", 'rg foo ../project/sub',
                        'rg -n foo "$HOME/x"', 'rg --include-zero foo',
                        "awk '{print $1}' a.md"):
            with self.subTest(command=command):
                self.assertSilent(command)

    def test_ripgrep_globs_ask_only_where_a_matching_denied_file_exists(self):
        self.assertAsks("rg -g '*.json' foo withsecret")
        self.assertSilent("rg -g '*.md' foo withsecret")
        self.assertSilent("rg -g '*.{md,php}' foo withsecret")
        self.assertIsNone(self.decide("rg -g '*.json' foo", cwd=self.clean))

    def test_the_launch_project_rules_apply_after_a_cd(self):
        launch = {**self.env, 'CLAUDE_PROJECT_DIR': self.project}
        self.assertEqual(self.decide('cat ../project/.env', env=launch, cwd=self.clean), ASK)
        self.assertIsNone(self.decide('cat ../project/.env', cwd=self.clean))

    def test_fd_exec_only_checks_the_paths_it_searches(self):
        self.assertSilent('fd -e md . sub -x wc -l')
        self.assertAsks('fd -e json . . -x wc -l')

    def test_wildcard_rules_are_named(self):
        settings = Path(self.home, '.claude', 'settings.json')
        original = settings.read_text()
        settings.write_text(json.dumps({'permissions': {'deny': ['Read(**/*.pem)']}}))
        try:
            config = os.path.join(self.temp, 'pem.conf')
            Path(config).write_text('--glob-case-insensitive\n--glob=!*.pem\n--glob=!.env\n')
            env = {**self.env, 'RIPGREP_CONFIG_PATH': config}
            self.assertEqual(self.decide('cat "$HOME/key.pem"', env=env), ASK)
            self.assertIsNone(self.decide('rg foo', env=env))
            self.assertEqual(self.decide('rg foo', env=self.env), ASK)
        finally:
            settings.write_text(original)

    def test_ripgrep_without_a_complete_config_asks(self):
        missing = {**self.env, 'RIPGREP_CONFIG_PATH': os.path.join(self.temp, 'nope')}
        self.assertEqual(self.decide('rg foo', env=missing), ASK)
        partial = os.path.join(self.temp, 'partial.conf')
        Path(partial).write_text('--glob=!.npmrc\n')
        self.assertEqual(self.decide('rg foo', env={**self.env, 'RIPGREP_CONFIG_PATH': partial}),
                         ASK)

    def test_fd_exec_over_a_denied_file_asks(self):
        for command in ('fd -x cat', 'fd -H -x cat', f'fd -X wc -c . {self.home}',
                        'fd -L -x cat', f'fd -x cat \\; . {self.home}'):
            with self.subTest(command=command):
                self.assertAsks(command)
        self.assertSilent('fd -e md')
        self.assertSilent(f'fd -x cat \\; . {self.clean}')

    def test_fd_exec_over_clean_directories_is_silent(self):
        self.assertIsNone(self.decide('fd -e md -x wc -l', cwd=self.clean))
        self.assertIsNone(self.decide('fd -X cat . src', cwd=self.clean))

    def test_fd_exec_over_a_link_to_a_denied_file_asks(self):
        linked = os.path.join(self.temp, 'linked')
        os.makedirs(linked)
        os.symlink(os.path.join(self.home, '.ssh'), os.path.join(linked, 'keys'))
        self.assertEqual(self.decide('fd -x cat', cwd=linked), ASK)

    def test_unreadable_user_settings_ask(self):
        env = {**os.environ, 'HOME': os.path.join(self.temp, 'missing')}
        self.assertEqual(self.decide('cat a.md', env=env), ASK)

    def test_unparseable_line_asks(self):
        self.assertAsks('cat "a.md')


if __name__ == '__main__':
    unittest.main()
