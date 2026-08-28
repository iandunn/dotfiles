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

- Only add comments to code that explain *why* the code does something, not *what* it does — prefer descriptive variable naming etc instead. The exception to that is when a function is long enough to do several things. Each logical section should have a comment to briefly say what it does. That way you can scan the function and know what each section does without having to read the code. If a function is that long though, that's often (but not always) a smell that it should be modularized into smaller functions.

- Don't add comments that explain new code in relation to code that you changed, and don't add comments that are artifacts from our conversation transcript or iterative proccess. The person reading the code after it's merged should be able to understand the comment without knowing anything about our session. Comments should be durable and self-contained. Commit messages are the appropriate place to describe why something changed, not comments.

- Test every comment this way before writing it: if the old code were deleted and nobody remembered it, would this comment still be true and useful? If it needs the previous version to make sense, it's wrong. Phrasings like "used to", "previously", "no longer", "was never", "always existed", "now that", and "instead of" are almost always this mistake.

- Wrap lines at 100 characters unless there's a lint rule that specifies lower.

- Add backticks around references to code, like class and file names, etc. Do that in commit messages too.

- How long a comment should be is covered by `writing-for-humans.md`, along with the rules for commit messages, PRs, and docs.
