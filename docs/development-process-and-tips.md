# general development process

use when starting any new piece of code

don't need to follow dogmatically in real life,	but the guidelines help you approach it logically,
and stay on track instead of doing it aimlessly, or getting tunnel vision deep in a rabbit hole

note that this is for a small part of a project (e.g. a github issue). don't do waterfall approach for whole project, do agile.


## before writing any code:

### "emergencies"

- [] if it's an "emergency", then:
    - [] identify the superficial cause of the problem (e.g., the line of code causing a fatal error)
	- [] put in a quick, temporary solution to "stop the bleeding"
		e.g., just revert the commit that added it, comment it out, disable the feature flag, replace it with a hardcoded value, return early, etc
		that gives you time & space to work on a more permanent fix without the pressure leading you to make a bad decision
		-- https://wp.me/p7H4VZ-2W5 (todo summarize for public)
	- [] once the pressure if off, follow the normal process to deeply understand the problem and implement the best solution


### understand the problem
- [ ] get a quick, high-level overview of the problem before going down any rabbit holes

- [ ] make sure it's worth it
	- [ ] ask how important it is to the team/organization, and then weigh that against the opportunity cost.
	- [ ] if it is worth doing, how should it be prioritized relative to other potential projects/tasks?

- [ ] make sure you're the right one to solve it
	- [ ] is a deeper systemic/process solution needed?
	- [ ] is a technology solution the best way to solve this, or is it really a human problem?

- [ ] get a deep understanding of problem
	- [ ] spend time thinking/reading about it, asking questions. make sure you really understand it
	- [ ] did they come to you with a problem, or a solution? if it's the latter, step back and ask what problem they're trying to solve
	- [ ] are you being asked to solve the root problem, or just a symptom of it?
	- [ ] as you learn things, post them the ticket/issue/p2/whatever.
			that documents important info, models that people don't have to know everything, and spurs ideas and feedback from others
	- [ ] if it's a bug, figure out how to reproduce it. add a unit test for that

- [ ] if it's worth solving
	- [ ] is now the right time to do it?
		- [] are there higher priorities? do them before this
		- [] are you in the middle of another task? finish that first
		    context switching is inefficient and stressful
		    shifting priorities is demoralizing -- https://hbr.org/2019/07/6-causes-of-burnout-and-how-to-avoid-them

	- [ ] break problem down
		explain it in your own words
	    list out the requirements, both explicit and assumed. label the assumed ones, ask if they're actual requirements:
			- [ ]
			- [ ]
			- [ ]
			- [ ]

--------------------------------------------------------------------------------------------------------------------------------------------

### evaluate solutions

- [ ] consider several different solutions, weigh pros/cons.
		what's the minimal solution needed to achieve the result, without adding tech debt? will there be unintended consequences?
		write psuedocode for any that have potential, or if need to in order to think through and evaluate it
		if having trouble, try working backwards - https://www.youtube.com/watch?v=v34NqCbAA1c


#### notes & psuedocode for potential ideas

1) [ description ]

	[ notes, questions, psuedocode ]

2) [ description ]

	[ notes, questions, psuedocode ]

3) etc


-----


- [ ] pick the solution that seems best, or has the most potential


--------------------------------------------------------------------------------------------------------------------------------------------

### chosen solution

- [ ] break solution down into small steps that are easy to understand and implement
- [ ] write out psuedocode for each step

[ psuedocode ]






- [ ] read through psuedocode several times, and iterate until it makes sense, and answers all questions
	- [ ] manually run through example w/ actual data in your head
- [ ] if discover big problem, reconsider other potential solutions. if not, continue



--------------------------------------------------------------------------------------------------------------------------------------------

## when ready to write code

### UI:
- [ ] build UI first w/ hardcoded logic -- see https://blog.codinghorror.com/ui-first-software-development/
- [ ] get review from any stakeholders, iterate based on feedback
- [ ] if react, break into components (ala "thinking in react")
- [ ] watch the browser via browsersync as you write code.
- [ ] get working w/ hardcoded before moving to `calc()`, live data, etc
- [ ] ...


### business logic:
- [ ] copy psuedocode to live file as comments in a new (modular) function
- [ ] can it be structured as a model/pure function? if so:
	- [ ] write unit test that fails
	- [ ] make unit test pass w/ hardcoded data and shortcuts
	- [ ] replace hardcoded with real logic, but step by step. don't skip steps. watch tests during each test
	- [ ] once working, refactor to be cleaner if needed (and worth it). don't be a perfectionist, though, just get it good enough. there are many more problems to solve.
- [] if not, (what would good process be? maybe try to apply same principals? give examples)


--------------------------------------------------------------------------------------------------------------------------------------------

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



--------------------------------------------------------------------------------------------------------------------------------------------


## todo

* add links to detailed explanations for all the shorthand used

* maybe create an adapted process for UI, since it's somewhat different than algorithms/business logic?
	* the concepts still apply though
	* if designing the UI, understand what user needs to do, consider different UIs to achieve that
	* if using someone else's design, "understand the problem" looks like getting very familiar w/ details of design, thinking of different ways to implement
