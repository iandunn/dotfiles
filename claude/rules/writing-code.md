# Writing Code

- When writing anything to a file (code, markdown, etc) don't add hard wraps. Let the editor add soft wraps. Add 1 blank line after the end of a ### or smaller section in Markdown, and 2 blank lines after the end of a ## section.

- Match existing code style and WordPress Core conventions

- Follow 10up engineering best practices

- Make only the minimal change necessary — flag larger refactors instead of doing them

- Never touch unrelated lines

- Exclude third-party code when inferring project conventions

- Assume a watch task is running — don't run build commands

- Use descriptive variable/function/etc names, not cryptic/terse abbreviations/etc

- Don't implement anti patterns, like creating pages that dont have deep links

- If automated tests already exist, then write them for code you add as well. Only add meaningful tests, though, don't try to get 100% coverage.

- Never use "smart" quotes etc, they're not displayed correctly in all contexts

- Don't prefix PHP methods etc with a `\`, instead add a `use` statement at the top of the file.


## Comments

- Don't remove comments, TODOs, `console.log()`, or debugger statements unless I ask. Blank lines are often used for readability, don't remove those. When completing a checkbox TODO (`- [ ]`), put an `x` in the box instead of deleting it.

- Only add comments to code that explain *why* the code does something, not *what* it does — prefer descriptive variable naming etc instead.

- Don't add comments that explain new code in relation to code that you changed. The person reading the code after it's merged wouldn't understand what that's about. Comments should be durable and self-contained.

- Wrap lines at 100 characters unless there's a lint rule that specifies lower.

- Add backticks around references to code, like class and file names, etc. Do that in commit messages too.


## Writing for Humans

- When writing for humans (code comments, commit messages, PR descriptions, etc) then don't be overly verbose. Include all the important information, but keep it short enough that it's actually practical to read it. For simple commits that's 1 sentance beyond the title, for complex commits its's roughly 2 paragraphs. For PRs its just an overview because the details should be in the commit messages.

- Code comments: Start with 1-2 sentances as the ideal, then only add more if necessary.

- Detailed plans, TODOs, Relay docs, etc, are the type of thing meant as context for agents, and that's where you'd write the way you normally would.


## Documentation

- Update docs periodically as you learn things and design solution, prepare a commit, etc. Don't wait until the end.
- Correct/update existing docs rather than appending the correction to original stale/false info.
- Record what was expensive to learn and is invisible from the code. Skip anything a reader gets from the code itself. The durable conclusion is what's important, though, not how you found it.
