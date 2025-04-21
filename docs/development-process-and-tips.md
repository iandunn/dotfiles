# general development process

copy this to a new file when starting any new piece of code.
as you move through it, rephrase general principles to contextualize them.
	e.g., "get a quick, high level overview" could mean reading a proposal, looking at a mockup, etc

don't need to follow dogmatically in real life,	but the guidelines help you approach it logically,
and stay on track instead of doing it aimlessly, or getting tunnel vision deep in a rabbit hole

note that this is for a small part of a project (e.g. a github issue). don't do waterfall approach for whole project, do agile.


## AI Usage

* At start of larger task like building a new feature - make it do the boilerplate
	* Give AI a lot of context about the goal of the feature and how you want it to be architected
	* Prompt: Give me 3 different ways to approach solving this problem. Then give me the pros/cons for each. Address the time required for each and code quality/maintainablility.
	* Ask it to create the overall structure of the code and fill it with stubs for all the functions, views, etc
* During
  * Ask it to do each particular task, like filling in a stub w/ real logic
  * Review all the code it adds and make changes yourself
	* make sure it's working as intended.
	* look for edge cases and error handling
	* look for security, maintainability, performance, accessibility
* Before merge
  * Ask what problems are there?
  * Ask what could be improved
  * Do manual review of all code



## TL;DR

### understand
- [ ] understand the problem. break it down problem into list of requirements
- [ ] consider several approaches, choose the best
- [ ] break solution down into list of small steps

### code
- [ ] write failing tests
	experiment with only doing integration tests, not unit
	only test the public interface for a series of functions
	( not e2e, still fast local phpunit, but )

	worked ok for 5ftF test-contributor.php
	not sure it was any faster, but probably more reliable
	still not worth the time though? try again just to see if next time is faster


- [ ] write stubs that solve tests w/ hardcoded data
- [ ] replace hardcoded w/ live data in small steps



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
		https://en.wikipedia.org/wiki/XY_problem
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
	    list out the requirements, both explicit and assumed.
	        label the assumed ones, ask if they're actual requirements, or mention to stakeholders that going with before start writing code for it
			- [ ]
			- [ ]
			- [ ]
			- [ ]

	- [ ] are there too many to fix in a single reasonably-sized pr?
			if so, find some kind of logical grouping and open pr for 1st group, merge, then start pr for 2nd

--------------------------------------------------------------------------------------------------------------------------------------------

### evaluate solutions

- [ ] consider several different solutions, weigh pros/cons.
		have others solved this before?	look for libraries/plugins/whatever
			if trustworthy enough to run on production, then use that to save time
			if not, then look at code to get ideas for how to build better version yourself

		what's the minimal solution needed to achieve the result, without adding tech debt?
			are there some requirements that could be modified or removed for a significant reduction in time/effort? if so, suggest they
		will there be unintended consequences?
		write psuedocode for any that have potential, or if need to in order to think through and evaluate it
		if having trouble, try working backwards - https://www.youtube.com/watch?v=v34NqCbAA1c
		if there are no good options, that may be because the design or requirements are flawed/unrealistic/etc
			if so, tell them the problem(s), and suggest an alternative


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
- [ ] build _functional_ UI first w/ hardcoded logic (not pixel perfect) -- see https://blog.codinghorror.com/ui-first-software-development/
- [ ] get review from any stakeholders, iterate based on feedback
- [ ] if react, break into components (ala "thinking in react")
- [ ] watch the browser via browsersync as you write code.
- [ ] get working w/ hardcoded values before moving to `calc()`, live data, etc
- [ ] implement the business logic
- [ ] circle back and make UI pixel-perfect


### business logic:
- [ ] copy psuedocode to live file as comments in a new (modular) function
- [ ] create empty stubs for all functions, have them call each other w/ hardcoded example arguments. try to make things models/pure functions where possible
- [ ] write 1 failing test for all models
- [ ] hardcode example return values for all models, so tests pass
- [ ] replace hardcoded lines with real logic, one at a time. don't skip steps. watch tests during each test
- [ ] once working, refactor to be cleaner if needed, and worth it. don't be a perfectionist, just get it good enough. there are many more problems to solve.

( for things that can't be automatically tested, what would a good process be? maybe try to apply same principals? give examples )


--------------------------------------------------------------------------------------------------------------------------------------------

## when spending too much time on something / down a rabbit hole

* is this an essential thing, or a nice-to-have thing?
	* is it user-facing or just "pure" code to make yourself happy?
    * is it long term architecture, or just short term throwaway?
		* if not important then look for shortcuts, or just don't do it.
		* if it's essential, then take a (task-negative) break, then catch up on comms and do other stuff the rest of the day.
			come back to it tomorrow when your brain is fresh
			consider if there are different ways to approach it

* are there too many remaining TODOs to keep track of mentally?
	* if so, make a list of them, organize it in logical order, and do each one at a time.
	focus on one at a time and don't get distracted. make notes on other things if have ideas, but then return to current task

* do you have a clear understanding of the problem and the solution?
	* if not, go back to the general process and clarify both of those

* take a break
	* rest for a bit, collect your thoughts, let your subconscious do some processing, let the frustration fade
	* then come back fresh

* would it help to start fresh with a different approach?
	don't look at it as throwing away the code you've written, look at it as building a second version with the knowledge you gained building the prototype
	can save current code in archived branch in case need to refer to it or switch back to it

* if you're working on X, and notice problem Y
	* is Y blocking X?
		* if no: don't stop X and start Y, just write down a quick note or gh issue for Y with a quick brain dump, and go back to X
		* if yes: write a brain dump of where you are with X, then another dump of what you know about Y. then start the general process for Y, finish it, and circle back to X

* ask for help. maybe a different perspective will provide a better approach.

--------------------------------------------------------------------------------------------------------------------------------------------


## todo

* add links to detailed explanations for all the shorthand used

* maybe create an adapted process for UI, since it's somewhat different than algorithms/business logic?
	* the concepts still apply though
	* if designing the UI, understand what user needs to do, consider different UIs to achieve that
	* if using someone else's design, "understand the problem" looks like getting very familiar w/ details of design, thinking of different ways to implement

* the "before writing any code" section has a lot of stuff that is more project management territory, like prioritizing.
	maybe move it there, but leave a reference to it?
	or maybe keep b/c you typically do all that anyway. it'd _ideally_ be done by a PM, but you don't usually have one, so it's on you
