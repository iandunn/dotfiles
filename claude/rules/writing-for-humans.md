# Writing for Humans

These rules cover anything a person reads. Detailed plans, TODOs, Relay docs, etc, are the type of thing meant as context for agents, and that's where you'd write the way you normally would.

These are the rules I want followed. For how I actually write -- sentence length, punctuation habits, how I qualify unproven claims, what I never say -- use the `writing-in-my-voice` skill, which has a reference file for each type of writing (commit messages, pull requests, emails, slack, etc). The two can disagree, and the skill flags it where they do.


## Brevity

Applies to: commit messages, PR descriptions, QA instructions, ticket comments, code comments, documentation files.

Interactive replies to me aren't covered here. Their rules live in the Response Style section of `CLAUDE.md`.

- Simple commit: 1 sentence beyond the title. Complex commit: roughly 2 paragraphs. That's a target, and there may be exceptions where you can go above it, but that should be rare.

- PR description: an overview only, because the details belong in the commit messages.

- Code comment: 1-2 sentences is the ideal, then only add more if necessary.

- Include all the important information, but keep it short enough that it's actually practical to read. Don't pad back up to one of the limits above just because there's room.


## Dates and Times

- Technical writing takes ISO 8601 dates, `2013-02-27`. That covers commit messages, PR and issue bodies, code review comments, replies in a GitHub/Make/Trac thread, code comments, documentation, and blog posts.

- Everything else takes `m/d/yyyy`, unpadded, `2/27/2013`. That covers email, Slack, chat, support forums, and proposals.

- Times are the same form in both: `3pm` and `3:15am`. Lowercase, no space before the meridiem, and no `:00` on the hour. That doesn't change when a time follows an ISO date, so it's `2013-02-27 3pm`.

- None of this reaches a string some system consumes -- a `date()` or `strftime()` format, an argument to a shell command, a filename, or a log line quoted verbatim. Those keep whatever format they require.


## Code and Data Samples

Applies anywhere a person reads the sample: an issue or PR body, a commit message, a ticket comment, a code review, documentation, Slack, email.

- Format a sample the way it would be formatted in a file. One element, key, or statement per line, and every nested level indented. Never collapse a sample onto a single line, even a short one, because the shape is most of what the reader is there to see.

- Indent with tabs, not spaces.

- Tag the fence with its language so it gets syntax highlighting.

```xml
<order>
	<status>SHIPPED</status>
	<placedDate>2013-02-27</placedDate>
	<itemCount>3</itemCount>
</order>
```


## Documentation

Follow these rules when creating documentation files, commit messages, pull requests, ticket descriptions/comments, etc. Don't use them for code comments -- see the `Comments` section of `writing-code.md` instead.

- Update documentation files continuously as you learn things and design a solution, prepare a commit, etc. Don't wait until the end.

- Correct/update existing docs rather than appending the correction to original stale/false info.

- Record what was expensive to learn and is invisible from the code. Skip anything a reader gets from the code itself. The durable conclusion is what's important, though, not how you found it.

- For things that are longer than 3 paragraphs, include a 1 sentance TL;DR at the top
