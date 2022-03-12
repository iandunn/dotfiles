### high

escape problems
	- [ ] if in browser url bar typing, don't want to cancel the focus on the bar by cancelling the locked mods
		when writing yahoo mail emial have to go to url bar to hit escape b/c otherwise esc will close email and might lose contents
		process_record_user: if mod lock active, and hit escape, then return false

	- [ ] holding cmd and alt and tapping escape doesn't trigger osx force quit
		look at onscreen keyboard to see what happens
		solution is that esc shouldn't cancel when they're being held?
		could do that in is_oneshot_cancel_key()

	maybe it's just a bad idea to reuse escape key?
	could have dedicated "ESCAPE_OS" key in one of the blank spots?
	thats hard to reach but so is escape

	- [ ] try switghing it to layer thumb key since never use that w/ mods
		but will that stick the layer on? would want to cancel the layer oneshot too

	maybe the even deeper root problem is just that locking mods on is problematic
	didn't have these problems w/ native OSM() though, so how is callum different?




- [ ] hold shift, scroll mouse to scroll window horizontally. that works.
	release shift, and scroll again. should return to scrolling vertical, but mod is stuck on
	same happens with holding cmd to zoom
	shouldn't lock when holding, only when tapping

- [ ] cancel mod lock when hit same mod twice
	eg, alt alt would cancel instead of keeping it on
	that way don't have to move hand to hit esc
	hmmm, might cause problems w/ ambiguity though, since won't be sure if it's on or not.
		that might be a smaller problem though
	if solve, cc callum in case he wants to integrate

- [ ] callum oneshot has side effects when interact w/ mouse
	 press shift to select file in phpstorm, click mouse. expect shift to be cancelled, but it isn't
	    works in Finder though, so quirk related to whatever UI toolkit phpstorm uses, or something?
	does process_us_rec receive mouse codes? if it does then easy to easy to add to cacnel func
		didn't see at first, but look deeper. maybe ask on reddit

	it must be possible because stock qmk osm does it, so just copy that?

	or maybe it's a fundamental consequence of how the intented behavior is different?
		the native OSM(MOD_LSHFT) doesn't support the above interaction either
		if so, just have to learn to hold shift down instead of tap



### medium

- [ ] reformat layout() to be easier to read and more compact
	some one where someone used ---+---- or something to draw borders of keys

- [ ] break layout() into vars for left and right hand, so don't have to scroll?
	can't b/c then they wouldn't be all on the same line?

- [ ] find a way to use GUI to edit the keymap itself
	might be nice to move keymap to separate file even if don't get this working
	not json though. comments are essential

### low

- [ ] maybe use ergodox leds to indicate that mods locked on?
