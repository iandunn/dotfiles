"""Shell-line shape checks shared by the permission hooks.

Both `file-command-permissions.py` and `command-allowlist-permissions.py` have to answer the same
question before they can vouch for a command: does bash run anything beyond the one command being
judged? The answer depends only on how bash parses the line, not on which command is being gated,
so it lives here -- one scanner means the two hooks cannot disagree about whether a `$` inside
single quotes expands or a `;` inside double quotes separates.

What stays in the hooks is policy. They gate different commands and reach different verdicts for
the same operator, so this module classifies what it finds and says nothing about what to do
about it.

The filename uses underscores because this is an imported module rather than a hook the settings
file names; the hooks themselves keep the hyphens.
"""
import re

# Operators bash expands anywhere it expands anything, which is everywhere but inside single
# quotes. An agent can't mechanically split these out of a line, so they're classified apart from
# the operators that chain.
EXPANDING_OPERATORS = ('$', '`')

# Operators that run a second command, and that an agent can always rewrite as separate tool
# calls. `&` covers both `&&` and backgrounding, and a bare newline is bash's own separator.
CHAINING_OPERATORS = (';', '&', '|', '\n')

# Parentheses group commands into a subshell. Unquoted they're a bash syntax error in every shape
# these hooks gate, so classifying them costs nothing and keeps a `(` from being read as ordinary
# text if that ever changes.
GROUPING_OPERATORS = ('(', ')')

# Characters that can begin a redirect, checked against BENIGN_REDIRECT before they're treated as
# meaningful. `&` is here because `&>/dev/null` starts with it.
REDIRECT_OPERATORS = ('>', '<', '&')

# Redirects that throw output away or shuffle file descriptors, matched at the position of the
# `>`/`<`/`&` (any leading fd digit has already been read as an ordinary character). These can't
# write a real file or start a second command, so they don't count against a line: `2>/dev/null`,
# `>>/dev/null`, `&>/dev/null`, `< /dev/null`, and fd duplication like `2>&1`. The trailing
# lookahead keeps `/dev/null` a whole word, so a redirect to `/dev/null.bak` or `/dev/nullx` is
# still a real write, and restricts `>&` to a bare fd number so `>&somefile` is too.
BENIGN_REDIRECT = re.compile(
    r'(?:&?>>?\s*/dev/null|<\s*/dev/null|>&[0-9]+)(?![\w./-])'
)

# The same redirects, plus the optional leading file-descriptor digit, matched as whole tokens so
# they can be dropped from a line before it's tokenized. Bash consumes a redirection before the
# command sees its argv, so leaving `2>/dev/null` in the token list would hand the command a
# phantom positional. `(?<!\S)` keeps the leading digit its own token so a value like `wp_2` isn't
# clipped.
STRIP_REDIRECT = re.compile(
    r'(?<!\S)[0-9]*(?:&?>>?\s*/dev/null|<\s*/dev/null|>&[0-9]+)(?![\w./-])'
)

EXPAND = 'expand'
CHAIN = 'chain'
GROUP = 'group'
REDIRECT = 'redirect'
UNREADABLE = 'unreadable'


def first_operator(command):
    """Return (kind, description) for the first operator bash could act on, or None.

    Quote state is what decides for most of them: bash treats `;`, `&`, `|`, `(`, `)`, `<`, `>`,
    and a newline literally inside quotes of either kind, which is what lets a multi-paragraph
    commit message and a SQL subquery's parens through. `$` and a backtick still expand inside
    double quotes, so only single quotes silence those.

    An unterminated quote or a trailing backslash comes back as UNREADABLE, because the rest of
    the line can't be read. So does a backslash-newline: bash splices the next line on before
    parsing, so a check that read the newline as an escaped literal would see nothing wrong.
    """
    quote = None
    escaped = False
    index = 0

    while index < len(command):
        character = command[index]

        if escaped:
            escaped = False
        elif character == '\\' and quote != "'":
            if command[index + 1:index + 2] == '\n':
                return UNREADABLE, 'a backslash-newline splices the next line onto this command'
            escaped = True
        elif quote == "'":
            if character == "'":
                quote = None
        elif quote == '"':
            if character == '"':
                quote = None
            elif character in EXPANDING_OPERATORS:
                return EXPAND, f'{character!r} expands even inside double quotes'
        elif character in ('"', "'"):
            quote = character
        elif character in EXPANDING_OPERATORS:
            return EXPAND, f'{character!r} outside quotes can expand into another command'
        elif character in REDIRECT_OPERATORS:
            benign = BENIGN_REDIRECT.match(command, index)
            if benign:
                index = benign.end()
                continue
            if character in CHAINING_OPERATORS:
                return CHAIN, f'{character!r} outside quotes chains a second command'
            return REDIRECT, f'{character!r} outside quotes redirects to a file'
        elif character in CHAINING_OPERATORS:
            return CHAIN, f'{character!r} outside quotes chains a second command'
        elif character in GROUPING_OPERATORS:
            return GROUP, f'{character!r} outside quotes groups commands into a subshell'

        index += 1

    if quote is not None:
        return UNREADABLE, 'a quote is left open, so the rest of the line cannot be read'
    if escaped:
        return UNREADABLE, ('the line ends in a backslash, so it continues where this hook '
                            'cannot see')
    return None
