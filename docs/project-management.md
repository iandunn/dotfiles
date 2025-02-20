# Project Management reminders

## Resources

* https://projectmanagementfoundations.wordpress.com/2020/12/16/project-management-fundamentals-with-scott-berkun-full-presentation/
* https://projectmanagementfoundations.wordpress.com/2021/02/22/project-management-fundamentals-part-2-full-presentation/
* https://github.com/iandunn/leadership/blob/e9cf877d84a4335027b5558b5f9001a21632ace2/tech_lead.md (source repo no longer exists)


## Process

- [ ] Identify stakeholders early and engage w/ them. include any affected people ("not about us without us")
- [ ] Get explicit expectations for timeline & deliverables
- [ ] prioritize deliverables up front, decide what gets cut if need to meet deadline.
  * at start of project, stub out the entire system.  maybe stubbing out is bad if multiple devs work on, because will lead to unused stubs if other devs don't take time to learn the skeleton and write new code with it?
	* goals/features/tasks spreadsheet from https://projectmanagementfoundations.files.wordpress.com/2020/12/vision-and-goals.pdf
- [ ] identify key stats that will track success of project. start collecting now to have baseline that can be compared to once project is done.
- [ ] Create estimates for the work and communicate them (see section below for details)
- [ ] start development
  * focus on the things that are highest priority/most difficult/most unknown first
  * then finish w/ the easy stuff.
- [ ] re-evaluate and communicate estimates at regular intervals
	cone of uncertainty / construx chart - https://projectmanagementfoundations.files.wordpress.com/2020/12/time-and-estimates.pdf
- [ ] get stakeholder feedback at regular intervals
	if practical, give them a way to demo it, like a staging site of feature flag


## Estimates

  * break project into phases, and only estimate one phase at a time. similar to agile sprints, but on a larger scale. that keeps estimates more grounded and accurate. alternatively, make an estimate for each sprint rather than each phase. will depend on what client wants. sprint is more accurate, but less insight into overall cost
	* break everything down into specific tasks, small enough to flesh out assumptions. make small enough that none take longer than ~18 dev hours
	* account for fact that it will take longer than expected when
	    * working on other projects/maintenance rotations at the same time
	    * team hasn't worked together
	    * hasn't done this type of work before
	    * collaborating w/ other teams
	    * holidays/sabbatical/parental leave/etc
	* include generous padding for "unknown unknowns"
	* techniques
		* multiply casual/basic/rough estimate by 2-4
		* PERT: ( Optimal + ( 4 * likely ) + Pessimistic ) / 6
			* don't like much b/c relies on likely being very accurate, but that's not realistic
			* could adjust the factor from 2 and then divide by 4? that doesn't help much
		* w-delphi - team based. each member makes estimate privately. then go through each task as group, and compare estimates. discuss why some as higher or lower. lower because one dev has a better approach? higher because one dev doesn't realize a complicating factor? etc
- [ ] factor in significant time for post-launch bug reports and feature requests
- [ ] leave room at end of project timeline b/c the last 20% takes significantly more than 20% of time
	because lots of detail work and polishing, also because people tend to leave hard/complex/unknown stuff to the end
	also because bugs are found and new features are requested once a large # of folks start using it
	this sounds like too much, but have seen it happen to a large extent
	https://github.com/iandunn/leadership/blob/master/tech_lead.md#the-8020-rule
	* "It is easy to overlook time-consuming nuances that slow the final 20% of a project. When you view your project holistically, break it up using the 80/20 rule, and consider that the final 20% of a project might account for another 80% of the overall timeline. There are a number of reasons for this, but the final 20% is often filled with polishing the deliverable, and complex features require polish for every feature and edge case, which compounds near the project's end."
	* "What does this mean for you? Just treat the 80% point in your project as the halfway marker. That will align expectations against the added effort nuance prescribes."


## When a project is late

Most of the time, the best thing is to cut scope. If necessary, push the deadline.

Adding people is only good if they'll be on the project long term. drive-by contributions are often low quality because they don't have institutional knowledge
and must be more heavily reviewed, bugs fixed, architecture problems & tech debt created, etc

Another option is to lower the quality to some extent, but not worth it long term


## Useful terms & links


* PM triangle: any time there are changes to scope, deadline, or quality, then the others have to change to account for it
  * lowering quality is usually the worst option, unless it's a prototype or the client chooses this option
  * extending the deadline is also bad, because [articulate why]
  * best option is to reduce scope. if did things right and started w/ the most critical stuff, then this will just be pushing lower-priority things to the next phase
* Brooke's Law: Adding people to a late project makes it even more late. https://en.wikipedia.org/wiki/Brooks%27s_law
* Death March: Management wants a stretch of unsustainable work to meet a poorly-planned deadline. https://en.wikipedia.org/wiki/Death_march_(project_management)
* Shturmovshchina: A common Soviet work practice of frantic and overtime work at the end of a planning period in order to fulfill the planned production target. The practice usually gave rise to products of poor quality at the end of a planning cycle. https://en.wikipedia.org/wiki/Shturmovshchina
* Boondoggle: A project that is considered a waste of both time and money, yet is often continued due to extraneous policy or political motivations. https://en.wikipedia.org/wiki/Boondoggle
* Escalation of commitment / sunk cost fallacy: facing increasingly negative outcomes from a decision/action, team continues the behavior instead of altering course. doing things that are irrational, but align with previous decisions/actions. "If you find yourself in a hole, stop digging." https://en.wikipedia.org/wiki/Escalation_of_commitment
* Gold plating: Adding design/code that users won't care about - https://en.wikipedia.org/wiki/Gold_plating_(project_management)
* Planning fallacy: a phenomenon in which predictions about how much time will be needed to complete a future task display an optimism bias and underestimate the time needed. https://en.wikipedia.org/wiki/Planning_fallacy
* Software Peter principle: A dying project which has become too complex to be understood even by its own developers. https://en.wikipedia.org/wiki/Software_Peter_principle
