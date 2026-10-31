## Hold / Resume
When I say "hold" or "hold replies" that means that I want to tell you something, and I want you to act on it, but I don't want you to reply yet.

You should do any work that you would normally do, but do it in the background. You can do research, write code, run commands, etc, just don't reply about it yet. The purpose of this is to let me catch up on previous replies about multiple topics without getting distracted by the stream of new replies.

Hold doesn't grant or remove permission for anything -- everything that normally waits for me to ask, like commits in the main checkout, pushes, PRs, and ticket comments, still waits.

In many cases, I haven't even read all of what you've said before, but I want to capture something before I lose the thought. And I don't want to waste time that you could be working instead of idling.

The only thing you should say is "Holding...", and then continue holding your replies until I say "resume", even if I send several prompts. The message that contains "hold" is itself held -- don't answer anything in it, even the part before or after the word "hold". Never respond until I explicitly say "resume", even if one of my prompts asks a question or says something that you think is a reason to respond. Wait for an explicit "resume", and in the mean time just respond "Holding..." to everything I say. Do all work in the background so you'll be ready when I say "resume." When I finally say "resume", that's when you can reply to everything that I said since the hold began.

This doesn't override the instructions about verbosity, though. The verbosity and content of your reply should be the same as if it would be in a session where I didn't use "hold", but supplied the same information as a single large prompt covering multiple topics.

A partial resume is a whitelist for replies, not a release, and it doesn't pause work on anything. If I say "resume for X but hold on everything else", answer X and nothing else, and stay in the hold afterward. A topic I raise for the first time during a hold defaults to held, even when I phrase it as a direct question, and even when it's about your own work, your tooling, or a mistake you made -- especially then, because wanting to correct my understanding of something you did is the most persuasive reason you will invent for breaking a hold. Before replying to anything mid-hold, point to the words in my message that release that specific topic. If you can't, the answer is "Holding...".

When I say "resume", answer every direct question I asked during the hold, even if it's only a line, or say explicitly that it's parked. Compressing the resume is fine, but never drop a question I asked.

If the prompt only used "hold" or "resume" in passing, like "hold on" or "resume the download", these rules don't apply.
