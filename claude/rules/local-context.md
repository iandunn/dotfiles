- Look for a `CLAUDE.local.md` file in the project/repository when you start a new session. If it exists, it provides context/custom instructions for that repo, so load it. It may also be a plain `CLAUDE.md` file that's higher up than the tracked `wp-content/CLAUDE.md` file.

- I often put planning notes in a `_notes` folder in a repo, so relevant things there may be there as well.

## WordPress Account

- When a task on a WordPress site needs an admin login, and the `CLAUDE.md` at the site root doesn't already give you one, create your own account with `wp user create claude-agent claude-agent@example.test --role=administrator`. The command prints the password it generated. Record that password and the username in that same file, under a `### Local admin login` heading.

- Write the credentials only to the `CLAUDE.md` at the site root, which sits outside any git repository. Never write them to a `CLAUDE.md` that's committed inside `wp-content`, or inside one of its plugin or theme repos, because everyone on the project reads that file.

- Create the account only on a local site. Never create users for any remote environment like staging or production or any other shared environment.

- Always log in through `wp-login.php` with those credentials. Local's one-click login drops the browser into my own account, so anything you do lands in my user's history, my editor preferences, and my audit trail. Check who you're logged in as before you act: if the admin bar says "Howdy, iandunn" and you didn't type a password, log out and log back in as the agent account.

- Multisite rejects usernames containing a hyphen, so `claude-agent` becomes `claudeagent` there. Note which spelling you used when you record the credentials.
