# Writing for Humans

These rules cover anything a person reads. Detailed plans, TODOs, Relay docs, etc, are the type of thing meant as context for agents, and that's where you'd write the way you normally would.

These are the rules I want followed. For how I actually write -- sentence length, punctuation habits, how I qualify unproven claims, what I never say -- use the `writing-in-my-voice` skill, which has a reference file for each type of writing (commit messages, pull requests, emails, slack, etc). The two can disagree, and the skill flags it where they do.


## Brevity

Applies to: commit messages, PR descriptions, QA instructions, ticket comments, code comments, documentation files.

- Simple commit: 1 sentence beyond the title. Complex commit: roughly 2 paragraphs. That's a target, and there may be exceptions where you can go above it, but that should be rare.

- PR description: an overview only, because the details belong in the commit messages.

- Code comment: 1-2 sentences is the ideal, then only add more if necessary.

- Include all the important information, but keep it short enough that it's actually practical to read. Don't pad back up to one of the limits above just because there's room.


## Documentation

Follow these rules when creating documentation files, commit messages, pull requests, ticket descriptions/comments, etc. Don't use them for code comments -- see the `Comments` section of `writing-code.md` instead.

- Update documentation files continuously as you learn things and design a solution, prepare a commit, etc. Don't wait until the end.

- Correct/update existing docs rather than appending the correction to original stale/false info.

- Record what was expensive to learn and is invisible from the code. Skip anything a reader gets from the code itself. The durable conclusion is what's important, though, not how you found it.

- For things that are longer than 3 paragraphs, include a 1 sentance TL;DR at the top
