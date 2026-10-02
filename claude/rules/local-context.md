- Look for a `CLAUDE.local.md` file in the project/repository when you start a new session. If it exists, it provides context/custom instructions for that repo, so load it. It may also be a plain `CLAUDE.md` file that's higher up than the tracked `wp-content/CLAUDE.md` file.

- I often put planning notes in a `_notes` folder in a repo, so relevant things there may be there as well.

## WordPress Accounts

- When a task on a WordPress site needs an account, and the `CLAUDE.md` at the site root doesn't already give you one, create your own account with `wp user create claude-[descriptor] claude-[descriptor]@example.test --role=[role]`, where `descriptor` is what makes the account unique, like `editor` for an account with an editor role. The command prints the password it generated. Record that password and the username in that same file, under a `### Local admin login` heading. Don't create an account if you can reuse an existing one, but don't modify accounts to avoid creating your own. e.g., it's generally useful to have separate accounts for subscriber, contributor, author, editor, admin, and super-admin. If the site doesn't already have an account for each user role, then go ahead and create them.

- Write the credentials only to the `CLAUDE.md` at the site root, which sits outside any git repository. Never write them to a `CLAUDE.md` that's committed inside `wp-content`, or inside one of its plugin or theme repos, because everyone on the project reads that file.

- Create the account only on a local site. Never create users for any remote environment like staging or production or any other shared environment.

- Always log in through `wp-login.php` with those credentials. Local's one-click login drops the browser into my own account, so anything you do lands in my user's history, my editor preferences, and my audit trail. Check who you're logged in as before you act: if the admin bar says "Howdy, iandunn" and you didn't type a password, log out and log back in as the agent account.

- Multisite rejects a hyphen in `wp user create`, so create the account as `claudeeditor`, then rename it with `wp db query "UPDATE {prefix}users SET user_login = 'claude-editor', user_nicename = 'claude-editor', display_name = 'claude-editor' WHERE user_login = 'claudeeditor'"`, where `{prefix}` is what `wp db prefix` prints. Then run `wp cache flush`. Grant super admin with `wp super-admin add` only after the rename, because WordPress stores super admins by username.
