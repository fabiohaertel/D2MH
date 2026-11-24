"""Corpse marker (only in main_win.py): remembers where a player's body was left, even after they move away.

- The unit table only carries the nearby rooms (measured in player.py: at ~65 tiles a player is no longer in it), so
  reading only the table would not show the main case, dying far away and coming back from town. That is why the
  position is kept, per area.
- While the character is dead, monitor_player returns None (the local one with dwMode 17 is discarded). That is why
  out_of_game also reads the table: that is when the body is nearby. With a dead player in sight and UI.inGame on, the
  player is on the death screen, not out of the game, and the GAME_GONE_SECONDS timer does not run.
- Corpse unit: player with `isCorpse` or dwMode 17. The area comes from the unit itself (read_player_state): near a
  transition, the table still carries units from the previous area. If its chain is not readable, the player's current
  area is used.
- Positions up to SAME_CADAVER_TILES apart are the same corpse: the dead player and the body left afterwards can be
  different units.
- It leaves the list when the player is in the area, within REMOVE_TILES of the point, and the unit goes REMOVE_SECONDS
  without showing up. The time counts from when they get near, so it is not erased while the rooms are still loading.
- Resets when the seed changes or after GAME_GONE_SECONDS in a row out of the game, like the DropTracker. The seed alone
  is not enough: in single player it repeats between games.
- Marks the corpse of any player: the project does not read the player's name from the unit.
- With the overlay hidden nothing is read: a death during that interval is not recorded.

To check in game: whether the corpse unit has a valid pPath with the body's position, and whether dwMode 17 holds
(player.py).
"""
import math
import time

from fabiomh.game.memory import read_struct
from fabiomh.game.player import PLAYER_MODE_DEAD, read_player_state
from fabiomh.game.structs import UI, DynamicPath
from fabiomh.game.units import UNIT_TYPE_PLAYER, iter_units

SAME_CADAVER_TILES = 2
REMOVE_TILES = 15
REMOVE_SECONDS = 3
GAME_GONE_SECONDS = 5


def read_cadavers(proc, address, current_level):
    """Returns [(area, x, y)] of the corpses in the table. current_level applies to those with an unreadable chain."""
    cadavers = []

    for player in iter_units(proc, address, UNIT_TYPE_PLAYER):
        if not player.pAct or not player.pPath:
            continue
        if not player.isCorpse and player.dwMode != PLAYER_MODE_DEAD:
            continue

        try:
            path = read_struct(proc, player.pPath, DynamicPath)
        except Exception:
            continue
        if not path.xPos:
            continue

        state, _ = read_player_state(proc, player)
        level = state[1] if state else current_level
        if level is not None:
            cadavers.append((level, path.xPos, path.yPos))

    return cadavers


class CadaverTracker:
    def __init__(self):
        self.gone_since = None  # since when there has been no player or dead player in sight
        self.reset()

    def reset(self):
        self.seed = None
        self.level = None  # area of the last player read
        self.known = {}    # area → [{"x", "y", "missing_since"}]

    def update(self, proc, address, seed, levelNo, player_pos):
        """Returns [(x, y, "cadaver")] of the known corpses in the current area."""
        self.gone_since = None
        if seed != self.seed:
            self.reset()
            self.seed = seed
        self.level = levelNo

        seen = [self.remember(*cadaver) for cadaver in read_cadavers(proc, address, levelNo)]

        now = time.monotonic()
        kept = []
        for cadaver in self.known.get(levelNo, []):
            near = math.hypot(cadaver["x"] - player_pos[0], cadaver["y"] - player_pos[1]) <= REMOVE_TILES
            if any(cadaver is other for other in seen) or not near:
                cadaver["missing_since"] = None
            elif cadaver["missing_since"] is None:
                cadaver["missing_since"] = now
            elif now - cadaver["missing_since"] >= REMOVE_SECONDS:
                continue
            kept.append(cadaver)

        if levelNo in self.known:
            self.known[levelNo] = kept
        return [(cadaver["x"], cadaver["y"], "cadaver") for cadaver in kept]

    def remember(self, level, x, y):
        """The corpse already known at this position, or a new one."""
        cadavers = self.known.setdefault(level, [])
        for cadaver in cadavers:
            if math.hypot(cadaver["x"] - x, cadaver["y"] - y) <= SAME_CADAVER_TILES:
                return cadaver
        cadaver = {"x": x, "y": y, "missing_since": None}
        cadavers.append(cadaver)
        return cadaver

    def out_of_game(self, proc, address, ui_address):
        """Call on the tick in which monitor_player returned None."""
        if self.seed is not None and self.read_while_dead(proc, address, ui_address):
            self.gone_since = None
            return

        now = time.monotonic()
        if self.gone_since is None:
            self.gone_since = now
        elif now - self.gone_since >= GAME_GONE_SECONDS:
            self.reset()

    def read_while_dead(self, proc, address, ui_address):
        """Records the corpses in sight and returns whether there were any. Out of the game, the table may have old
        units."""
        try:
            if not read_struct(proc, ui_address, UI).inGame:
                return False
        except Exception:
            return False

        cadavers = read_cadavers(proc, address, self.level)
        for cadaver in cadavers:
            self.remember(*cadaver)
        return bool(cadavers)
