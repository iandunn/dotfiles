# QA Steps

These rules cover QA steps wherever they go: a PR, a ticket description, or a draft update to steps that are already on a ticket. A tester follows them literally, so a step that's wrong costs a round trip with QA, and a step that's vague gets skipped or tested differently than you intended. It's very important that they're correct. When to write them and where they go is in the `Commits / PRs` section of `running-commands.md`.


## Verify every step

- Run every step yourself, exactly as written, before you show me the draft. Open the exact URL, click the exact label, paste the exact snippet, and log in as the role the step names. Don't run a variant you consider equivalent, because the tester only gets the text. Write the steps with the QA environment's URLs and accounts. When you run them locally, the only changes allowed are swapping in the local host, an equivalent local account, and the local ID of content that has a different ID in the QA environment.

- Run them after the last code change. If the code or a step changes afterward, run the affected steps again before showing me the new draft.

- Every expected result is something you observed while running the step, copied from the screen or the response: a label, a notice, a status code, a JSON field and its value. Never write one from what you think the code _should_ do. Check what the browser/script/command/etc _actually_ does. The only exception is a step you couldn't run, which is covered below. After the run in the QA environment, replace any value that came from the local run, like an ID or a host, with what the QA environment showed.

- Before you run them in a remote environment, run them locally and iterate until they're correct.

- Once they're correct and the code has been deployed to the remote QA environment (usually staging or preprod), run them there too. The code usually isn't deployed there until after the PR is open, so run them there when I tell you it's been deployed, even if that's in a later session. Then follow the `After creating a PR` bullet about the ticket in `running-commands.md`. Save the draft and the list of steps you couldn't verify in the project's `_notes` folder, so a later session can finish the remote run. If the project doesn't have one, ask me where they should go. That's standing permission to open the project's QA environment in the browser to run the steps, even when the project's `CLAUDE.md` doesn't list it. Never touch production. Use QA environment URLs/users/etc for this step.

- Log in to the QA environment only with an account that the project's `CLAUDE.md` names for it. If there isn't one, don't run the steps there, and list them as not run remotely. Never write its password to a committed file.

- Check that the URLs, accounts, and data the steps name exist in the QA environment. On the local site you can create users and content for the steps, but don't edit or delete anything you didn't create.

- In the QA environment, you have standing approval to create pages, and to edit and delete the pages you created. Start each page's title with `claude-qa-`, and once you're done with it, delete it permanently rather than moving it to the Trash. Don't create users, and don't create, edit, or delete anything else. Running a step counts as making its changes, so a step that submits a form, saves anything, or sends a request other than a `GET` has to stay within these limits too. If a step needs a change you aren't allowed to make, don't run that step there; list it as not run, and tell me.

- Never cite mocks, fixtures, or stubbed data as evidence. Verification only counts against real endpoints or the running site.


## Report what you couldn't verify

- After the draft, give me a list of every step you didn't run exactly as written in the remote QA environment, with the reason and what I should check. That covers steps you only ran locally, steps you ran with a workaround, and steps you couldn't run at all, like an email being delivered, a third-party payment, a cron event hours later, or a different browser or device. Split it into the steps that are only waiting for the deploy, and the ones you can't verify remotely at all, so the second group isn't buried. If you verified everything, say so in one line.

- A step you couldn't run still needs an expected result. Write it from the code, and name it in that list as inferred.

- Keep that list out of the draft. The tester gets clean steps with no caveats.


## Write for the tester

- Read `writing-for-humans.md` and the `writing-in-my-voice` skill's `references/pull-requests-and-issues.md` before the first draft.

- Write for a tester who knows browser dev tools but doesn't know curl. When a step needs a raw API request, give a `fetch()` snippet to paste into the browser console on a page of the same site, using a relative URL. Assume they know how to use dev tools. Make each snippet do its own multi-step work, like holding something and then releasing it, instead of asking the tester to copy IDs between requests or hand-format values like dates.

- Never put a password, token, cookie, or nonce in a step. Name the role, and say where the tester gets the login. A snippet that needs a nonce gets it from the page when it runs, rather than containing a pasted value.

- Write only what the tester does and what they should see. Leave out why a step has its shape, what you considered, and warnings against mistakes a smart and experienced human wouldn't make.

- When a step needs a page or other content to exist, write creating it as a step the tester performs. Never point the tester at content you created, because you delete yours when you're done.

- Work out the minimum setup that still shows every behavior before writing a step that asks for it. Roles that behave identically need one account between them, not one each.

- Every expected result names something the tester can see, like `"post_status": "draft"`, rather than "it comes back".

- A placeholder names the kind of value that goes in it, like `<draft post ID>` rather than `<their draft>`.

- Put backticks around commands, IDs, URLs, UI labels, and anything else data-shaped. Use inline backticks for a one-line command, and save fenced blocks for multi-line samples like a `fetch()` snippet.

- Give the URL to open wherever a step starts on a new page.
