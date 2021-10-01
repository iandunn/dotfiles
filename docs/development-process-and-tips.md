# general development process

use when starting any new piece of code

don't need to follow dogmatically in real life,	but the guidelines help you approach it logically,
and stay on track instead of doing it aimlessly, or getting tunnel vision deep in a rabbit hole

note that this is for a small part of a project (e.g. a github issue). don't do waterfall approach for whole project, do agile.


## before writing any code:
- [ ] spent time thinking/reading about the problem, asking questions. make sure you really understand it
- [ ] break it down and list out the requirements, both explicit and assumed. label the assumed ones, ask if they're actual requirements

- [ ] consider several different solutions, weigh pros/cons. what's the minimal needed to achieve result, without adding tech debt?
- [ ] pick the solution that seems best

- [ ] break solution down into small steps that are easy to understand and implement
- [ ] write out psuedocode for each step
- [ ] read through psuedocode several times, and iterate until it makes sense, and answers all questions


## when ready to write code

### business logic:
- [ ] copy psuedocode to live file as comments in a new (modular) function
- [ ] write unit test that fails
- [ ] make unit test pass w/ hardcoded data and shortcuts
- [ ] replace hardcoded with real logic, but step by step. don't skip steps. watch tests during each test
- [ ] once working, refactor to be cleaner if needed (and worth it). don't be a perfectionist, though, just get it good enough. there are many more problems to solve.

### UI:
- [ ] build UI first w/ hardcoded logic -- see https://blog.codinghorror.com/ui-first-software-development/
- [ ] if react, break into components (ala "thinking in react")
- [ ] watch the browser via browsersync as you write code. get working w/ hardcoded before moving to `calc()`, live data, etc
- [ ] ...



## when spending too much time on something / down a rabbit hole

* do you have a clear understanding of the problem and the solution?
	* if not, go back to the general process and clarify both of those

* is this an essential thing, or a nice-to-have thing?
	* is it user-facing or just "pure" code to make yourself happy?
    * is it long term architecture, or just short term throwaway?
		* if not important then look for shortcuts, or just don't do it.
		* if it's essential, then take a (task-negative) break, then catch up on comms and do other stuff the rest of the day. come back to it tomorrow when your brain is fresh

* if you're working on X, and notice problem Y
	* is Y blocking X?
		* if no: don't stop X and start Y, just write down a quick note or gh issue for Y with a quick brain dump, and go back to X
		* if yes: write a brain dump of where you are with X, then another dump of what you know about Y. then start the general process for Y, finish it, and circle back to X


## todo

* maybe create an adapted process for UI, since it's somewhat different than algorithms/business logic?
	* the concepts still apply though
	* if designing the UI, understand what user needs to do, consider different UIs to achieve that
	* if using someone else's design, "understand the problem" looks like getting very familiar w/ details of design, thinking of different ways to implement
