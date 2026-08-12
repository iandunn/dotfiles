#!/usr/bin/env bats

# Tests for the `unwrap` function in bash/functions.sh.
#
# Run with: bats bash/tests/unwrap.bats
#
# `unwrap` reads the clipboard, rejoins hard-wrapped lines, and writes the result back.
# The clipboard is shimmed here: input goes in via $UNWRAP_TEST_INPUT, output comes out on
# stdout. Warnings about ambiguous joins go to stderr and are asserted separately via
# bats' --separate-stderr.

bats_require_minimum_version 1.5.0

setup() {
	source "$(dirname "$BATS_TEST_FILENAME")/../functions.sh"

	pbpaste() { printf '%s' "$UNWRAP_TEST_INPUT"; }
	pbcopy() { cat; }
}

unwrap_text() {
	UNWRAP_TEST_INPUT="$1"
	run --separate-stderr unwrap
}


# -- basic joining --

@test "single line passes through unchanged" {
	unwrap_text 'echo hello world'
	[ "$output" = 'echo hello world' ]
	[ -z "$stderr" ]
}

@test "wrapped lines join with a single space" {
	unwrap_text $'The quick brown fox\njumps over the lazy dog.'
	[ "$output" = 'The quick brown fox jumps over the lazy dog.' ]
	[ -z "$stderr" ]
}

@test "leading indentation is stripped" {
	unwrap_text $'first part of the line\n  continuation was indented\n\tand this one used a tab'
	[ "$output" = 'first part of the line continuation was indented and this one used a tab' ]
}

@test "blank lines between paragraphs are preserved" {
	unwrap_text $'first paragraph starts here\nand wraps once.\n\nsecond paragraph also\nwraps once.'
	[ "$output" = $'first paragraph starts here and wraps once.\n\nsecond paragraph also wraps once.' ]
}


# -- whitespace fidelity --

@test "terminal copies padded with trailing spaces join cleanly" {
	unwrap_text $'first half of sentence      \nsecond half here            '
	[ "$output" = 'first half of sentence second half here' ]
}

@test "input ending with a newline does not gain a trailing space" {
	unwrap_text $'short paragraph here.\n'
	[ "$output" = 'short paragraph here.' ]
}

@test "mid-line runs of spaces are preserved" {
	unwrap_text 'printf "%-10s  %s" a b'
	[ "$output" = 'printf "%-10s  %s" a b' ]
}


# -- ambiguous joins: a wrap that split a token mid-way is indistinguishable from a
# -- wrap between two words, so the join keeps the space (loud failure: a stray space
# -- inside a token breaks visibly) and reports the junction on stderr

@test "mid-token split keeps the space and warns" {
	# The first line is the longest (= estimated wrap column) and ends with a token
	# that, combined with the next line's first token, exceeds that column: the
	# signature of a wrapper hard-splitting an over-long token.
	unwrap_text $'run t.onabort=()=>{console.log(aVeryLongTok\nenName)} and continue'
	[ "$output" = 'run t.onabort=()=>{console.log(aVeryLongTok enName)} and continue' ]
	[[ "$stderr" == *'may fall inside a token'* ]]
}

@test "adjacent long tokens ending at the wrap column also warn (deliberate false positive)" {
	unwrap_text $'https://example.com/some/really/long/path/here/that/fills/the/line\nhttps://example.com/second/url after.'
	[[ "$output" == 'https://example.com/some/really/long/path/here/that/fills/the/line https://example.com/second/url after.' ]]
	[[ "$stderr" == *'may fall inside a token'* ]]
}

@test "ordinary wrapped prose does not warn" {
	unwrap_text $'The quick brown fox jumps over the lazy dog while the\nindustrious beaver builds a dam.'
	[ "$output" = 'The quick brown fox jumps over the lazy dog while the industrious beaver builds a dam.' ]
	[ -z "$stderr" ]
}


# -- quote markers: "▎" is decorative-only and always stripped; "|" and ">" are also
# -- shell syntax, so they're only stripped when the line looks like part of a quote
# -- block, and every such strip is reported on stderr

@test "blockquote marker ▎ is stripped, even on a single line" {
	unwrap_text '▎ The heron paused mid-stride.'
	[ "$output" = 'The heron paused mid-stride.' ]
	[ -z "$stderr" ]
}

@test "marker-only ▎ line acts as a paragraph break" {
	unwrap_text $'▎ First quoted paragraph\n▎ wraps here.\n▎\n▎ Second quoted paragraph.'
	[ "$output" = $'First quoted paragraph wraps here.\n\nSecond quoted paragraph.' ]
}

@test "multi-line email quote > is stripped with a notice" {
	unwrap_text $'> The quick brown fox jumps over\n> the lazy dog.'
	[ "$output" = 'The quick brown fox jumps over the lazy dog.' ]
	[[ "$stderr" == *'stripped a leading'* ]]
}

@test "nested quote markers >> are stripped together" {
	unwrap_text $'>> Original message text\n>> continues here.\n> A reply to it.'
	[ "$output" = 'Original message text continues here. A reply to it.' ]
	[[ "$stderr" == *'stripped a leading'* ]]
}


# -- shell syntax that must survive: the counter-cases the markers rule used to eat

@test "sed delimiter | starting a continuation line survives (regression: eaten pipe)" {
	# A real incident: `sed "s|^|$r |"` wrapped so the continuation line began with
	# the closing |" of the expression, and unwrap stripped it as a quote marker.
	unwrap_text $'do git config --get-regexp rebase | sed "s|^|$r\n|"; done > backup.txt'
	[[ "$output" == *'sed "s|^|$r |"; done'* ]]
	[[ "$stderr" != *'stripped a leading'* ]]
}

@test "pipe starting a wrapped pipeline continuation survives" {
	unwrap_text $'grep -r pattern some/long/path/to/search/through\n| sort | uniq -c'
	[ "$output" = 'grep -r pattern some/long/path/to/search/through | sort | uniq -c' ]
	[[ "$stderr" != *'stripped a leading'* ]]
}

@test "redirect > starting a continuation line survives when no neighbor is quoted" {
	unwrap_text $'some_command --with --many --flags --that --wrap\n> output-file.txt'
	[ "$output" = 'some_command --with --many --flags --that --wrap > output-file.txt' ]
	[[ "$stderr" != *'stripped a leading'* ]]
}

@test "markdown table rows keep their pipes" {
	unwrap_text $'| Name | Value |\n|------|-------|\n| foo  | 1     |'
	[[ "$output" == '| Name | Value | |------|-------| | foo  | 1     |' ]]
}


# -- encoding --

@test "non-ASCII content passes through intact" {
	unwrap_text $'▎ The heron paused — considering the shallows —\n▎ then struck at something silver.'
	[ "$output" = 'The heron paused — considering the shallows — then struck at something silver.' ]
}
