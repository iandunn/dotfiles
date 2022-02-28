## Installing these files

cd ~/Library/ApplicationSupport/Steam/steamapps/common/insurgency2/insurgency/cfg
cp {server.cfg.example | default_server_occupy.cfg | etc} ~/dotfiles/{same name, minus "default", "example", etc}
	repeat ^ for other default files you want to modify
run bash: `for file in ~/dotfiles/insurgency/cfg/*; do ln -sf $file $(basename $file) ; done`
repeat same for `scripts/` folder

to apply:
	`exec {filename without extension}` in console
	if that doesn't work, vote to restart game
	if that doesn't work, exit to main menu and then start new game. shortcut is to just type `map {map} {mode}`. usually this works if the above doesn't.
	if that doesn't work, quit app and reopen


// rename this file to _readme.md and merge install.txt into it
// make sections for install, commands, general notes, etc
// maybe move some notes from cfg files here, like references to generic articles

// seems like team 1 is always security, 2 is always insurgents
// it tells you when you join the game to join team 1 (security), or 2 (insurgents)
ins_bot_add 		- add 1 bot to team 1. sometimes it seems like it adds it to _both_ teams, though? if that happens, you just have to follow this by kicking from t2
ins_bot_add_t2 		- add 1 both to team 2
ins_bot_kick_t1
ins_bot_kick_t2

// todo any settings to balance out teams? seems like security bots usually kill insurgent bots too easy, so game isn't close and isn't fun
// sometimes it's the opposite though. maybe that's intentional? not fun regardless
// kicking from security helps, but want an easier way to autobalance during and after rounds
// ideally would be in a cfg file so don't have to manually do it

ins_bot_difficulty {0-3, 3 being brutal}

kill - suicide when stuck

map {mapname} {mode}
this is useful for playing hunt mode against lots of bots, with no bots on your team. just like you can on an empty remote server

some MP game modes not working with `map` command. they're also not accessible in the solo menu.
	- switch to map right away, rather than waiting for voting etc
	if enter and there aren't any bots on other side, is that because you entered a mode that the map doesn't support?
		or does it just send you to anohter map in that case?
	bots will show up in tab menu, but not actually be in the game
		or maybe they are, but are just sitting at their respawn?
	huh, no, `map buriz_night strike` should work but doesn't. will maybe work if restart game
	oh wait, strike/ambush/etc don't show up in solo menu either, only push/occupy/skirmish/firefight
		oh, huh, started a firefiht match (tactical not competivie), then the ambush maps became available in vote>change, maybe strike etc too?
		er, no, same problem w/ no enemy bots on map



	maybe have to use the `{name}_coop` version of the map?

	// maybe also need to do 'mp_theater_override default' in console, OR in server mod cfg, or server.cfg? or 'classic' or other?
		// this might be the reason that the bots started working, or maybe i just didn't notice things right
	// can be default or classic, maybe others. ah, yeah, see theater_* files in cfg folder


map contact_night ambush - playing as attackers/insuregencts
	10 supply - oh prolly b/c i haven't setup an ambush config`
	bots on both sides work

map sinjar ambush - playing as sec/defenders
	chose sniper, but makes me vip. doesn't give me any weapons. can pick up from dead playser though

map buhriz strike
	sec bots play, but ins bots just sit at spawn until someone comes into their field of vision, regardless of which side i'm on
	try theater elite and hardcore


// todo find what mode is this? is looks great - https://www.youtube.com/watch?v=1KB3HIUhspg
	// was it an older one that was removed? even if it is, is it still accessible directly via `map buhriz {mode}` (and maybe also overwriting the theater?)
	// i guess maybe it's just conquer? but it seems like there's way more bots that normal. i guess you could just do that yourself by adding bots?
	// different uniforms, but thats minor
	// yeah, it was coop hardcore conquer, see timestamp 9:18
	// so maybe it'd be fun to do a local coop match, play sniper, have bots on your team just guard you (if possible), but add a lot of extra bots on other team, so get overrun if don't play well
	// like simulating a horde
	// any way to make difficult of bots different between teams?

// todo command bots from any class, not just leader

// todo try out the total conversions you downloaded. looks like you got all the good ones
// todo try out the custom maps you downloaded.
	// there are more too, i only  went through the first two pages of "most popular all time"
	// so start up again here - https://steamcommunity.com/workshop/browse/?appid=222880&requiredtags%5B0%5D=Checkpoint&actualsort=trend&browsesort=trend&p=3&days=-1


// launch options to set in steam
	// see https://community.pcgamingwiki.com/topic/4571-harmful-misconceptions-in-launch-options-and-console-commandsarguments-for-source-engine-based-games/
	// don't use
	 	// -high
	// do use
	 	// -novid to ignore startup interstitial
		// -nojoy and -nosteamcontroller
		// todo added those, but still seeing interstiaial, and get beachball for a few seconds before it loads. if persists, probably just disable them b/c no problems before
			// removed -novid b/c not working anyway, does it still happen?
			// dont remember, but removed other two b/c of crashes w/ custom maps/mods. maybe not have been the cause, but not worth time to investigate


// one of the maps or mods has messed up the armor preview, it shows ammo clips instead
	// can prob assume it's not a map, since it's applying to other maps, right?
	// so maybe the born to kill or five mods? try disabling and see if that fixes. neither work anyway b/c btk crashes and five forces remote play


// maybe check out day of infamy and create a `games/insurgency` and `games/day-of-infamy` at same time, since will have to redo symlinks

// this is useful resource: https://github.com/jaredballou/insurgency-data/tree/master/mods/insurgency/2.4.2.4/scripts/theaters
