#!/usr/bin/env python3
"""Tests for `bash_ast`, the shfmt-backed parser every Bash hook shares."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import bash_ast


def commands(line):
    return bash_ast.parse(line).commands


def argvs(line):
    return [command.argv for command in commands(line)]


def chain(line):
    return bash_ast.parse(line).chain


class WordResolutionTest(unittest.TestCase):
    def test_quotes_and_escapes_resolve_to_the_program_bash_runs(self):
        for line in ('"git" push', "'git' push", '\\git push', 'g"i"t push', "g'it' push"):
            with self.subTest(line=line):
                self.assertEqual(argvs(line), [['git', 'push']])

    def test_name_is_lowercased_basename(self):
        self.assertEqual(commands('/usr/bin/Git push')[0].name, 'git')

    def test_ansi_c_quoting_is_decoded(self):
        self.assertEqual(argvs("printf $'a\\nb' $'\\x67it'"), [['printf', 'a\nb', 'git']])

    def test_double_quoted_backslashes_follow_bash(self):
        self.assertEqual(argvs('echo "a\\$b" "c\\d"'), [['echo', 'a$b', 'c\\d']])

    def test_expansions_are_not_literal(self):
        word = commands('echo "$HOME/x"')[0].words[1]
        self.assertIsNone(word.value)
        self.assertFalse(word.literal)

    def test_globs_braces_and_tildes_are_flagged(self):
        words = commands("ls *.txt {a,b} ~/x '*' 'stash@{0}' stash@{0}")[0].words
        self.assertTrue(words[1].glob)
        self.assertTrue(words[2].brace)
        self.assertTrue(words[3].tilde)
        self.assertTrue(words[4].literal)
        self.assertTrue(words[5].literal)
        self.assertFalse(words[6].brace)

    def test_brace_groups_only_count_when_bash_expands_them(self):
        expected = {
            '{a,b}': True, "{'a',b}": True, '{\\{,b}': True, '{a\\{,b}': True, 'w{x,}p': True, '{1..3}': True, 'a{b,{c,d}}': True,
            'stash@{0}': False, '@{u}..HEAD': False, '@{upstream}...HEAD': False,
            '\\{a,b\\}': False, '{a}': False, 'a,b': False,
        }
        for text, brace in expected.items():
            with self.subTest(text=text):
                self.assertEqual(commands(f'echo {text}')[0].words[1].brace, brace)

    def test_line_continuation_disappears(self):
        self.assertEqual(argvs('gi\\\nt push'), [['git', 'push']])


class CommandDiscoveryTest(unittest.TestCase):
    def test_commands_inside_compound_statements_are_found(self):
        lines = {
            'if true; then git push --force; fi': ['true', 'git'],
            'for x in a; do git clean -fdx; done': ['git'],
            'while false; do rm x; done': ['false', 'rm'],
            'case x in *) git push;; esac': ['git'],
            '( git push )': ['git'],
            '{ git push; }': ['git'],
            'f() { git push; }': ['git'],
            'coproc git clean -fdx': ['git'],
            'time git push': ['git'],
            '! git push': ['git'],
        }
        for line, names in lines.items():
            with self.subTest(line=line):
                self.assertEqual([command.name for command in commands(line)], names)

    def test_substitutions_are_found(self):
        names = [command.name for command in commands('echo $(git push) `id` <(ls) "$(rm x)"')]
        self.assertEqual(sorted(names), ['echo', 'git', 'id', 'ls', 'rm'])

    def test_substitution_in_an_assignment_or_test_is_found(self):
        self.assertIn('git', [c.name for c in commands('x=$(git push)')])
        self.assertIn('git', [c.name for c in commands('export x=$(git push)')])
        self.assertIn('git', [c.name for c in commands('[[ -n $(git push) ]]')])

    def test_unquoted_heredoc_substitution_is_found(self):
        self.assertIn('git', [c.name for c in commands('cat <<EOF\n$(git push)\nEOF')])

    def test_quoted_heredoc_body_is_data(self):
        self.assertEqual([c.name for c in commands("cat <<'EOF'\n$(git push)\nEOF")], ['cat'])

    def test_comments_are_ignored(self):
        self.assertEqual(argvs("git status # it's fine; rm -rf /"), [['git', 'status']])

    def test_bare_redirect_is_reported(self):
        command = commands('> file')[0]
        self.assertEqual(command.words, [])
        self.assertEqual(command.redirects[0].target.value, 'file')


class WrapperTest(unittest.TestCase):
    def test_transparent_wrappers_are_peeled(self):
        lines = (
            'command git push', 'command -p git push', 'builtin git push', 'exec git push',
            'nohup git push', 'nice -n 5 git push', 'sudo -u root git push', 'env git push',
            'env -i FOO=1 git push', 'env -u HOME git push', 'timeout 5 git push',
            'timeout -s KILL 5 git push', 'caffeinate -i git push', 'arch -arm64 git push',
        )
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(argvs(line), [['git', 'push']])

    def test_command_v_does_not_run_its_operand(self):
        self.assertEqual(commands('command -v git')[0].name, 'command')
        self.assertEqual(commands('command -pV git')[0].name, 'command')

    def test_env_split_string_with_its_own_escapes_is_opaque(self):
        for line in ("env -S 'git\\_push'", "env -S 'git ${X}'", "env -S 'git push #x'",
                     "env -S '-C /tmp git add -A'", "env -S 'GIT_DIR=/x git status'",
                     "env -S 'git status;git clean -fdx'", "env -S $'git\\tstatus'",
                     "env -S 'git status | sh'"):
            with self.subTest(line=line):
                self.assertIsNotNone(commands(line)[0].opaque)

    def test_input_redirects_are_benign_only_when_literal_or_dev_null(self):
        self.assertFalse(commands('git commit -F - < msg.txt')[0].redirects[0].benign)
        self.assertTrue(commands('git log < /dev/null')[0].redirects[0].benign)
        self.assertTrue(commands("git commit -F - <<'EOF'\nmsg\nEOF")[0].redirects[0].benign)

    def test_shell_string_filled_in_by_xargs_or_find_is_opaque(self):
        for line in ("xargs -I{} sh -c '{}'", "find . -exec sh -c '{}' \\;", "xargs eval",
                     "xargs -I{} env -S 'git {}'"):
            with self.subTest(line=line):
                self.assertTrue(any(c.opaque for c in commands(line)))

    def test_shell_string_under_xargs_is_still_reparsed(self):
        self.assertIn(['git', 'reset', '--hard'], argvs("xargs sh -c 'git reset --hard'"))
        self.assertIn(['git', 'reset', '--hard', '{}'], argvs("xargs -I{} sh -c 'git reset --hard {}'"))
        self.assertFalse(any(c.opaque for c in commands("xargs -0 sh -c 'git status' _")))

    def test_env_split_string_passes_later_words_through(self):
        self.assertEqual(argvs("env -S 'git reset' '#' --hard"), [['git', 'reset', '#', '--hard']])

    def test_command_option_clusters_are_parsed(self):
        self.assertEqual(argvs('command -pp git push'), [['git', 'push']])
        self.assertEqual(argvs('command -p -- git push'), [['git', 'push']])
        self.assertIsNotNone(commands('command -x git push')[0].opaque)

    def test_env_assignments_are_collected(self):
        command = commands('env GIT_DIR=/x git status')[0]
        self.assertIn('GIT_DIR', [name for name, _ in command.assigns])

    def test_shell_dash_c_is_reparsed(self):
        found = commands("bash -c 'git push'")
        self.assertEqual(found[0].argv, ['git', 'push'])
        self.assertEqual(found[0].wrappers, ['bash -c'])
        self.assertTrue(found[0].nested)

    def test_clustered_dash_c_is_reparsed(self):
        self.assertEqual(argvs("sh -ec 'git push'"), [['git', 'push']])

    def test_eval_and_env_split_string_are_reparsed(self):
        self.assertEqual(argvs('eval git push'), [['git', 'push']])
        self.assertEqual(argvs("env -S 'git push'"), [['git', 'push']])

    def test_name_built_inside_a_reparsed_string_is_opaque(self):
        found = commands("sh -c 'a=w b=p; $a$b db reset'")
        self.assertTrue(any(command.opaque for command in found))

    def test_non_literal_command_string_is_opaque(self):
        self.assertIsNotNone(commands('bash -c "$script"')[0].opaque)
        self.assertIsNotNone(commands('eval "$x"')[0].opaque)

    def test_shell_reading_stdin_is_opaque(self):
        self.assertIsNotNone(commands('bash')[0].opaque)
        self.assertIsNotNone(commands('bash -s')[0].opaque)

    def test_shell_reading_a_literal_heredoc_is_reparsed(self):
        self.assertEqual(argvs("bash <<'EOF'\ngit push\nEOF"), [['git', 'push']])

    def test_shell_running_a_script_is_an_ordinary_command(self):
        command = commands('bash ~/dotfiles/claude/bin/close-isolated-chrome.sh')[0]
        self.assertEqual(command.name, 'bash')
        self.assertIsNone(command.opaque)

    def test_xargs_and_find_exec_have_dynamic_arguments(self):
        xargs = commands('xargs -n 1 git push')[0]
        self.assertEqual(xargs.argv, ['git', 'push'])
        self.assertTrue(xargs.dynamic_args)
        found = commands("find . -name x -exec git push {} \\;")
        self.assertEqual([command.name for command in found], ['git', 'find'])
        self.assertTrue(found[0].dynamic_args)

    def test_unknown_wrapper_option_is_opaque(self):
        for line in ('sudo --bogus git push', 'env --block-signal git push', 'nice -z git push',
                     'bash --bogus script.sh', "fish -C 'git push' x"):
            with self.subTest(line=line):
                self.assertTrue(any(command.opaque for command in commands(line)))

    def test_clustered_and_attached_option_values_are_skipped(self):
        for line in ('sudo -uroot git push', 'nice -n5 git push', 'nice -5 git push',
                     'xargs -0 -I{} git push', 'xargs -i git push', 'timeout --signal=KILL 5 git push'):
            with self.subTest(line=line):
                self.assertEqual(commands(line)[-1].argv, ['git', 'push'])

    def test_option_value_that_expands_is_opaque(self):
        for line in ('env -u w{x,}p db reset', 'sudo -u w{x,p} db reset', 'nice -n $N git push',
                     'bash -o w{x,p} -c x'):
            with self.subTest(line=line):
                self.assertTrue(any(command.opaque for command in commands(line)))

    def test_shell_option_values_in_clusters_are_skipped(self):
        self.assertEqual(argvs("bash -eo pipefail -c 'git push'"), [['git', 'push']])
        self.assertTrue(any(c.opaque for c in commands("bash -oc pipefail 'git push'")))
        self.assertTrue(any(c.opaque for c in commands('bash -Z script.sh')))

    def test_watch_exec_runs_an_argv(self):
        self.assertEqual(argvs('watch -x git push'), [['git', 'push']])
        self.assertEqual(argvs("watch 'git push'"), [['git', 'push']])

    def test_commands_git_runs_for_you_are_found(self):
        lines = {
            'git bisect run git clean -fdx': ['git', 'clean', '-fdx'],
            "git submodule foreach --recursive 'git clean -fdx'": ['git', 'clean', '-fdx'],
            "git rebase -x 'git clean -fdx' main": ['git', 'clean', '-fdx'],
            "git rebase --exec='git clean -fdx' main": ['git', 'clean', '-fdx'],
            "git rebase -x'git clean -fdx' main": ['git', 'clean', '-fdx'],
            "git -C repo rebase --exe 'git clean -fdx' main": ['git', 'clean', '-fdx'],
        }
        for line, inner in lines.items():
            with self.subTest(line=line):
                found = commands(line)
                self.assertIn(inner, [command.argv for command in found])
                self.assertTrue(all(c.nested for c in found if c.argv == inner))

    def test_heredoc_bodies_keep_their_backslashes(self):
        quoted = commands("bash <<'EOF'\necho \\'; wp db reset --yes; echo \\'\nEOF")
        self.assertIn('wp', [command.name for command in quoted])
        unquoted = commands('bash <<EOF\necho \\"; wp db reset --yes; echo \\"\nEOF')
        self.assertIn('wp', [command.name for command in unquoted])

    def test_shell_reading_stdin_by_path_is_reparsed(self):
        for line in ("bash - <<< 'git clean -fdx'", "bash /dev/stdin <<< 'git clean -fdx'",
                     ". /dev/stdin <<< 'git clean -fdx'", "source - <<< 'git clean -fdx'"):
            with self.subTest(line=line):
                self.assertIn(['git', 'clean', '-fdx'], argvs(line))
        self.assertIsNotNone(commands('source <(curl x)')[-1].opaque)

    def test_nul_ends_an_ansi_c_string(self):
        self.assertEqual(argvs("git reset $'--hard\\0x'"), [['git', 'reset', '--hard']])

    def test_trap_string_is_reparsed(self):
        self.assertIn(['git', 'clean', '-fdx'], argvs("trap 'git clean -fdx' EXIT"))
        self.assertEqual(argvs('trap -p'), [['trap', '-p']])

    def test_wrapped_commands_own_s_flag_is_not_sudo_s(self):
        found = commands("sudo git log --grep 'a;b' -i")
        self.assertEqual(found[0].argv, ['git', 'log', '--grep', 'a;b', '-i'])
        self.assertIsNone(bash_ast.parse("sudo git log --grep 'a;b' -i").chain)
        self.assertEqual(argvs("sudo -s git log --grep 'a;b'"), [['git', 'log', '--grep', 'a;b']])

    def test_watch_value_cluster_does_not_turn_on_exec(self):
        self.assertEqual(argvs("watch -dx 'git push'"), [['git', 'push']])
        self.assertEqual(argvs('watch -tx git push'), [['git', 'push']])

    def test_git_runner_clusters_and_submodule_options(self):
        self.assertIn(['git', 'clean', '-fdx'], argvs("git rebase -ix'git clean -fdx' main"))
        self.assertIn(['git', 'clean', '-fdx'], argvs("git submodule --quiet foreach 'git clean -fdx'"))
        self.assertTrue(any(c.opaque for c in commands('git --bogus-global status')))

    def test_sudo_shell_keeps_dollar_expansions_live(self):
        """sudo escapes `(` but not `$`, so `$(...)` stays literal while `$HOME` expands."""
        self.assertEqual(argvs("sudo -s echo '$(git clean -fdx)'"), [['echo', '$(git clean -fdx)']])
        self.assertIsNone(commands("sudo -s git log '$HOME'")[0].words[2].value)

    def test_program_running_git_options_are_reparsed(self):
        for line in ("git fetch --upload-pack='git clean -fdx' origin",
                     "git push --receive-pack 'git clean -fdx' origin",
                     "git clone -u 'git clean -fdx' x y",
                     "git send-email --to-cmd='git clean -fdx' x",
                     "git grep -O'git clean -fdx' pattern",
                     "git send-pack --receive-pack='git clean -fdx' x"):
            with self.subTest(line=line):
                self.assertIn(['git', 'clean', '-fdx'], argvs(line))

    def test_bare_optional_value_option_does_not_swallow_the_next_word(self):
        self.assertIn(['git', 'clean', '-fdx'],
                      argvs("git grep -O --open-files-in-pager='git clean -fdx' x"))
        self.assertIn(['git', 'clean', '-fdx'], argvs("git grep -nO'git clean -fdx' x"))
        self.assertIn(['git', 'clean', '-fdx'], argvs("git grep -O'git clean -fdx' x"))

    def test_clone_config_is_opaque(self):
        for line in ("git clone -c core.sshCommand='x' a b", 'git clone --config=core.fsmonitor=x a b',
                     "git clone -ccore.pager=x a b", 'git clone --conf=x a b', 'git clone -qc x a b',
                     'git clone --template=/tmp/t a b', 'git init --templ /tmp/t'):
            with self.subTest(line=line):
                self.assertTrue(any(c.opaque for c in commands(line)))
        self.assertFalse(any(c.opaque for c in commands('git clone a b')))

    def test_non_literal_rebase_argument_is_opaque(self):
        self.assertTrue(any(c.opaque for c in commands('git rebase -x "$cmd" main')))
        self.assertFalse(any(c.opaque for c in commands('git commit -m "$msg"')))

    def test_chroot_skips_the_new_root(self):
        self.assertEqual(argvs('chroot / git push'), [['git', 'push']])

    def test_shell_heredoc_overridden_by_a_later_stdin_redirect_is_opaque(self):
        found = commands("bash <<'EOF' < other.sh\necho hi\nEOF")
        self.assertIsNotNone(found[0].opaque)

    def test_arithmetic_subscript_that_could_expand_is_opaque(self):
        for line in ("(( a['$(git clean -fdx)'] ))", "let \"a['\\$(id)']\"",
                     "echo $(( a['$(id)'] ))", "[[ a['$(id)'] -eq 1 ]]",
                     "declare -i x=\"a['\\$(id)']\"", "printf -v \"a['\\$(id)']\" x"):
            with self.subTest(line=line):
                self.assertTrue(any(c.opaque for c in commands(line)))
        self.assertFalse(any(c.opaque for c in commands('(( x + 1 ))')))
        self.assertFalse(any(c.opaque for c in commands('printf "%s" "$HOME"')))

    def test_subscripts_outside_arithmetic_clauses_are_checked(self):
        for line in ('echo "${a[\'x[$(git clean -fdx)]\']}"', "a['x[$(id)]']=1",
                     "x=([0]=y ['z[$(id)]']=1)", "read 'x[$(id)]'", "FOO=\"${a['x[$(id)]']}\" ls"):
            with self.subTest(line=line):
                self.assertTrue(any(c.opaque for c in commands(line)))

    def test_subscripts_without_an_expansion_are_not_flagged(self):
        for line in ('[[ -n $HOME ]]', 'echo $((a[0]+1))', "env printf '%s' '[$HOME]'",
                     "printf '%s\\n' '$x' '[y]'", 'echo ${a[0]}'):
            with self.subTest(line=line):
                self.assertFalse(any(c.opaque for c in commands(line)))

    def test_non_bash_shell_code_is_opaque(self):
        """zsh and fish code isn't read with bash's grammar, so it can't be vouched for."""
        for line in ("fish --command 'git push'", "zsh -c 'git push'", "ksh <<< 'git push'"):
            with self.subTest(line=line):
                self.assertIsNotNone(commands(line)[0].opaque)
        self.assertEqual(argvs("sh -c 'git push'"), [['git', 'push']])

    def test_output_limiting_filter_reading_dev_null_is_not_a_chain(self):
        self.assertIsNone(bash_ast.parse('git log | head -5 </dev/null').chain)

    def test_output_limiting_filter_with_an_input_redirect_is_a_chain(self):
        for line in ('git log | head <<< "$(git clean -fdx)"', 'git log | head < <(git clean -fdx)',
                     'git log | head <<EOF\n$(git clean -fdx)\nEOF'):
            with self.subTest(line=line):
                parsed = bash_ast.parse(line)
                self.assertIsNotNone(parsed.chain)
                self.assertIn(['git', 'clean', '-fdx'], [c.argv for c in parsed.commands])

    def test_redirect_on_a_declaration_is_reported(self):
        found = commands('export x=1 > file')
        self.assertEqual(found[-1].redirects[0].target.value, 'file')

    def test_out_of_range_escape_does_not_crash(self):
        bash_ast.parse("printf $'\\U7fffffff'")

    def test_git_exec_path_binary_is_judged_as_git(self):
        self.assertEqual(argvs('/opt/homebrew/opt/git/libexec/git-core/git-clean -fdx'), [['git', 'clean', '-fdx']])
        self.assertIn(bash_ast.GIT_EXEC_PATH_WRAPPER, commands('git-status')[0].wrappers)

    def test_non_literal_program_name_is_opaque(self):
        self.assertIsNotNone(commands('$EDITOR file')[0].opaque)
        self.assertIsNotNone(commands('$(echo git) push')[-1].opaque)


class ChainTest(unittest.TestCase):
    def test_single_commands_do_not_chain(self):
        for line in ('git status', 'git log 2>/dev/null', "git commit -m 'a; b && c'", 'echo $(date)'):
            with self.subTest(line=line):
                self.assertIsNone(chain(line))

    def test_chaining_constructs_are_reported(self):
        for line in ('a; b', 'a && b', 'a || b', 'a | b', 'a & b', 'a &', 'a\nb', '( a )',
                     '{ a; }', 'if a; then b; fi', 'for x in y; do a; done', "bash -c 'a; b'",
                     'echo $(a; b)', 'a |& b'):
            with self.subTest(line=line):
                self.assertIsNotNone(chain(line))

    def test_output_limiting_tail_is_not_a_chain(self):
        parsed = bash_ast.parse('git log | head -20 | wc -l')
        self.assertIsNone(parsed.chain)
        self.assertEqual([command.argv for command in parsed.commands], [['git', 'log']])

    def test_tail_that_can_do_more_is_a_chain(self):
        for line in ('git log | tail -f', 'git log | head file', 'git log | sort', 'git log | head > x'):
            with self.subTest(line=line):
                self.assertIsNotNone(chain(line))


class RedirectTest(unittest.TestCase):
    def test_benign_redirects(self):
        redirects = commands('git log 2>/dev/null 2>&1 &>/dev/null </dev/null')[0].redirects
        self.assertTrue(all(redirect.benign for redirect in redirects))

    def test_real_file_redirects_are_not_benign(self):
        for line in ('git log > x', 'git log >> x', 'git log > /dev/null.bak', 'git log >&x', 'git log > "$f"'):
            with self.subTest(line=line):
                self.assertFalse(commands(line)[0].redirects[0].benign)


class FailureTest(unittest.TestCase):
    def test_unparseable_line_raises(self):
        for line in ("echo 'unterminated", 'if true; then', 'a &&'):
            with self.subTest(line=line):
                with self.assertRaises(bash_ast.ParseError):
                    bash_ast.parse(line)

    def test_missing_shfmt_raises(self):
        original = bash_ast.find_shfmt
        bash_ast.find_shfmt = lambda: None
        try:
            with self.assertRaises(bash_ast.ParseError):
                bash_ast.parse('git status')
        finally:
            bash_ast.find_shfmt = original


if __name__ == '__main__':
    unittest.main()
