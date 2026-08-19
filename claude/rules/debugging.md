# Debugging and Understanding Code

- On the frontend add `console.log()` statements and use the Chrome MCP to test your changes.

- On the backend add php error logs and trigger the code with `curl`, wp cli, etc, then read the log.

- Use subagents when exploring the codebase to speed it up.

- When you fix a bug in one area of the code, check to see if it's occurring in other areas too

<!-- My global gitignore covers `.claude`, which keeps scratch files out of commits while leaving them visible to me. -->
- Put temporary files in `.claude/tmp/` inside the project. This overrides the harness's own instruction to use a session scratchpad under the system temp dir, and it overrides plain `/tmp` — `.claude/tmp/` wins over any scratchpad directory a harness prompt names. A permanent artifact like PDF -> text goes in the project's `_notes` folder if one exists, or the Relay folder when the project uses Relay. If neither exists, ask where it should go instead of picking a spot.

- To test a change reversibly (e.g., "does this lint rule still fire without the ignore comment?"), use `Edit` to make the change and a second `Edit` to put it back. Don't copy the file to a backup and then restore it.
