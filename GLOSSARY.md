# FabioMH

Diablo 2 Resurrected maphack: shows the map of the current area, with the fixed markers and the units read from the
game's memory. Game terms are kept as players say them in English.

## Game

**Game**:
A match created in D2R, from the moment you join until you leave.
_Avoid_: match, session

**Seed**:
The number rolled for each game that, together with the difficulty, defines the layout of every area.
_Avoid_: map id

**Difficulty**:
Normal, Nightmare or Hell.

**Act**:
One of the 5 groups of areas in the game, each with its own town.

**Town**:
The first area of each act (Rogue Encampment, Lut Gholein, Kurast Docks, Pandemonium Fortress, Harrogath),
where no monster is shown.
_Avoid_: camp

## Place and map

**Area**:
A region of the game identified by a number (e.g. Lower Kurast, Canyon of the Magi).
_Avoid_: level, zone, stage, map

**Map**:
The drawing of an area: the borders of what is walkable and the markers, generated from the seed.
_Avoid_: image, PNG (and "map" in the sense of area: "area change", not "map change")

**Marker**:
A fixed point on the map, known only from the seed (exit, waypoint, quest, boss, super chest).
_Avoid_: point, object

**Exit**:
Any passage from one area to another: door, stairs or border.
_Avoid_: entrance, portal

**Border exit**:
The exit between two adjacent outdoor areas, with no door or stairs (e.g. River of Flame → Chaos Sanctum).

**Right tomb**:
In the Canyon of the Magi, Tal Rasha's tomb with the right symbol.
_Avoid_: right exit, good exit

**Boss**:
One of the fixed NPCs that the map marks in its own area: Radament, Maggot King, Summoner, Izual, Nihlathak.
_Avoid_: using it for any strong monster (for that, see **Unique**)

**Quest**:
The marker of the object or NPC that a quest requires in that area (e.g. the Cairn stones, the Hellforge, Anya).
_Avoid_: objective, mission

**Waypoint**:
The marker of the area's teleport point.
_Avoid_: WP, portal

**Super chest**:
A chest with a higher drop chance, marked only in the areas the player chose (by default, Lower Kurast).
_Avoid_: sparkly chest

## Units

**Unit**:
A live game entity, read from memory on every read: player, monster or item.
_Avoid_: entity, object, point

**Monster**:
A living enemy outside town; mercenaries and town NPCs are not monsters.
_Avoid_: mob, enemy

**Unique**:
Monster category read from memory, which includes the super uniques (e.g. Andariel, the living Radament).
_Avoid_: boss

**Champion**:
A monster from a group of champions.

**Minion**:
A monster that accompanies a unique.
_Avoid_: follower, retinue

**Normal**:
A monster that is not a unique, champion or minion.
_Avoid_: common

**Rune**:
A rune dropped on the ground, of a type the player asked to see.
_Avoid_: item, drop

**Local player**:
The character of whoever is running FabioMH.
_Avoid_: me, character, player (alone)

**Other player**:
A living player in the same game who is not the local player.

**Ghost**:
One of the player units without an act that show up in every game and are nobody playing.

**Corpse**:
The body left by a player who died: it is still a player unit, but does not count as a player.
_Avoid_: body, cadaver

## Display

**Overlay**:
Where the map is shown, whatever the mode.
_Avoid_: window, panel, screen

**Browser mode**:
The overlay in its own Chrome window, next to the game.

**Over-the-game mode**:
The overlay as a transparent panel drawn on top of the game.
_Avoid_: win, window mode
