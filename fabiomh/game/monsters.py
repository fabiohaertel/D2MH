"""Monster reading (unit table type 1).

- dwMode 0 = dying, 12 = dead: they are ignored.
- Mercenaries are filtered by dwTxtFileNo. In town no monster at all is read, so as not to show NPCs.
- MonsterData.typeFlags (0x1A from pUnitData): 2 = super unique, 4 = champion, 8 = unique, 16 = minion.
- Necromancer and druid summons become kind "summon" by dwTxtFileNo (measured in game: Clay Golem = 289,
  skeleton = 363, with typeFlags 0). The druid ones (419 to 428) are public, not yet measured in this version.
  742 to 744: measured in game, alive next to the player, with flags 0 and the same party buff states as the mercs
  (3, 32, 33, 42, 45, 49, 51), while the nearest enemy only had 105. They were drawn in red (normal).
  571 and 616: same case, but with unique typeFlags (8, 10, 24), golden with an immunity ring. Hydra (351 to 353):
  seen red, only with states 105 and 187.
  There is no owner field in MonsterData. Revived monsters (Revive) keep the original txt; they are found by the
  `revive` state (state 96, `REVIVE_STATE`) in the state flags of the stat list: `pStatList + 0xB30`, 6 DWORDs, bit N =
  state N (`STATE_FLAGS_OFFSET`). Measured in game (revived cows, txt 391, outside the Cow Level): only they had bit 96;
  in the same block, the Act 2 merc and the player had 34 (Prayer) and the player 70 (Warmth). There is a second copy at
  +0xB50, which is not used. A revived monster becomes kind "summon" (white), like the summons by txt.
- Immunities: `UnitAny.pStatList + 0xE8` → stat array, immune = value >= 100. Measured online with diag_stats.py
  (3.3.93847): the stats are on the client and the elite bonuses are already added (txt 160 unique with cold 100, against
  25 for the others). There are two lists (+0x30 and +0xE8), equal on all monsters measured. +0xE8 is used, which had one
  more stat on NPCs and seems to be the complete one. Not yet measured: whether it drops with Conviction and breaks the
  immunity.
- Measured cost: read_immunities takes ~12 µs per elite (20 elites = ~0.25 ms per 150 ms tick). That is why there is no
  cache.
"""
from config import IMMUNITY_KINDS
from fabiomh.game.memory import read_int, read_struct
from fabiomh.game.structs import DynamicPath, MonsterData, StatArray, StatValue
from fabiomh.game.units import UNIT_TYPE_MONSTER, iter_units

TOWN_LEVELS = {1, 40, 75, 103, 109}
MERC_TXT_FILE_NOS = {271, 338, 359, 560, 561}
SUMMON_TXT_FILE_NOS = {
    289, 290, 291, 292,  # Necromancer: golems (clay, blood, iron, fire)
    363, 364,            # Necromancer: skeleton, skeleton mage
    419,                 # Druid: raven
    420, 421, 428,       # Druid: Spirit Wolf, Dire Wolf, Grizzly
    422, 423, 424,       # Druid: Spirit of Barbs, Heart of Wolverine, Oak Sage
    425, 426, 427,       # Druid: Poison Creeper, Carrion Vine, Solar Creeper
    351, 352, 353,       # Sorceress: Hydra (public, seen in game as normal)
    742, 743, 744,       # Measured in game (Throne of Destruction, party): allies with flags 0, showed up as normal
    571, 616,            # Measured in game: allies with unique flags (8, 10, 24), showed up golden with a ring
}

STATE_FLAGS_OFFSET = 0xB30  # in pStatList: 6 DWORDs, bit N = state N
REVIVE_STATE = 96


def has_state(proc, pStatList, state):
    """True if the unit is in the state (states.txt). A failed read gives False."""
    try:
        flags = read_int(proc, pStatList + STATE_FLAGS_OFFSET + state // 32 * 4)
    except Exception:
        return False
    return bool(flags >> (state % 32) & 1)


STAT_ARRAY_OFFSET = 0xE8
MAX_MONSTER_STATS = 128  # measured: 9 to 12. Above that the read picked up garbage
IMMUNE_VALUE = 100
# Stat → immunity, in the order of the ring arcs (colors in window.IMMUNITY_COLORS)
IMMUNITY_STATS = {39: "fire", 43: "cold", 41: "light", 45: "poison", 37: "magic", 36: "physical"}


def read_immunities(proc, pStatList):
    """Tuple of the unit's immunities. Unreadable stats give (): the monster still shows up, just without the ring."""
    try:
        array = read_struct(proc, pStatList + STAT_ARRAY_OFFSET, StatArray)
        if not array.pStats or not 0 < array.qwCount <= MAX_MONSTER_STATS:
            return ()
        stats = read_struct(proc, array.pStats, StatValue * array.qwCount)
    except Exception:
        return ()

    values = {stat.wStat: stat.nValue for stat in stats}
    return tuple(name for stat, name in IMMUNITY_STATS.items() if values.get(stat, 0) >= IMMUNE_VALUE)


def read_monsters(proc, address):
    """Returns [(x, y, kind)] with kind = unique / champion / minion / normal / summon. A monster of IMMUNITY_KINDS with
    an immunity gets a 4th value, the read_immunities tuple."""
    monsters = []

    for monster in iter_units(proc, address, UNIT_TYPE_MONSTER):
        if monster.dwMode in (0, 12) or not monster.pPath:
            continue
        if monster.dwTxtFileNo in MERC_TXT_FILE_NOS:
            continue

        try:
            path = read_struct(proc, monster.pPath, DynamicPath)
            flags = read_struct(proc, monster.pUnitData, MonsterData).typeFlags if monster.pUnitData else 0
        except Exception:
            continue

        if monster.dwTxtFileNo in SUMMON_TXT_FILE_NOS or (
                monster.pStatList and has_state(proc, monster.pStatList, REVIVE_STATE)):
            kind = "summon"
        elif flags & (2 | 8):
            kind = "unique"
        elif flags & 4:
            kind = "champion"
        elif flags & 16:
            kind = "minion"
        else:
            kind = "normal"

        immunities = read_immunities(proc, monster.pStatList) if kind in IMMUNITY_KINDS and monster.pStatList else ()
        if immunities:
            monsters.append((path.xPos, path.yPos, kind, immunities))
        else:
            monsters.append((path.xPos, path.yPos, kind))

    return monsters
