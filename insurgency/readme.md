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
ins_bot_add 		- add 1 bot to _both_ teams? or just team1? if both, then just have to add to both and then kick one
ins_bot_add_t2 		- add 1 both to team 2
ins_bot_kick_t1
ins_bot_kick_t2

ins_bot_difficulty {0-3, 3 being brutal}

kill - suicide when stuck

map {mapname} {mode}	- switch to map right away, rather than waiting for voting etc
