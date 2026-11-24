"""Reading of the local player (difficulty, area, seed and position) and of the other players' position.

Pointer chain:
- `pInventory + 0x70 != 0` → it is the local player (the other players have 0). But sometimes it gives 0 on the local
  player itself (measured in a game created alone): then, if only one living player has a valid chain, it is the local
  one (plan B, reported in the log). It happened when entering a game right after dying, with the corpse in front: the
  corpse is a player unit (with the inventory), so it is discarded (`isCorpse` or `dwMode` 17) before the test and
  plan B
- pAct (0x20) → Act.pActMisc (0x70) → ActMisc.game_difficulty (0x830), seed hashes 0x840 (u64) / 0x860 (u32)
- pPath (0x38) → DynamicPath.pRoom1 (0x20) → Room1.pRoom2 (0x18) → Room2.pLevel (0x90) → Level.dwLevelNo (0x1F8)

During loading and transitions the pointers can be null or stale. An invalid candidate must `continue` to the next
player, never `return None`: with several players in the game, that wiped the whole overlay.

Each discarded candidate leaves a reason, and `log.report("player", ...)` prints the summary when it changes
(with DEBUG_LOG). It is what tells why the map does not appear in a game: failing read, no local player, seed 0...

Ghosts: the player table has 10 to 12 units with `pAct=0`, position (0, 0) and `pRoom1=0`, all of the character's
class. They are not leftovers from previous games: ids and addresses change every game (what they are is still unknown;
one of them owns ~10 items, maybe the shared stash). They are only counted in the log reason.

Plan C (local player outside the table): a unit's bucket is `dwUnitId % 128`. Measured in a game that failed: the local
player (owner of 17 items) fell into a ghost's bucket, and the bucket's list seemed to end at the ghost, so the player
was unreachable through the table (~9% of games, with 11 ghosts). The likely cause was the wrong `pListNext` (0x150
instead of 0x158, see structs.py), which hid everything after the first one in the bucket; plan C stays as a backup. In
it, the player is found through the items: the `ItemData` of a stored/equipped item has a pointer to the owning
inventory (offset discovered on the first search, by scanning the struct), the inventory starts with the signature
0x01020304 and `Inventory+0x08` points to the owning unit (measured), and its `dwUnitId` has to be the item's
`ItemData.dwOwnerId` (measured: it matches the player's id).

Other players (`read_other_players`): every player in the table that does not pass the local test. Ghost, corpse
(`UnitAny.isCorpse`) and dead (`dwMode` 0 = dying, 17 = dead, to check in game) do not show up. Players in another
area are not filtered here: `build_points` discards what falls outside the map.

The unit table only has the players near the local one (the server only sends the units of the nearby rooms: measured,
a party player in town at ~65 tiles was no longer in it). The game map shows the party members farther away because it
uses the roster (`memory.ROSTER_OFFSET`, linked list of `RosterUnit` through `pNext`), which has the area and position
of the party members. Measured: outside the party (`wPartyId` 0xFFFF) the area and position are 0, and the local player
itself also has position (0, 0). So: the players in the table (exact position, every tick) and, for those not in it,
the party members in the same area from the roster (the roster position lags a few tiles behind).
"""
import ctypes as ct
import time

from fabiomh.game.memory import pm, read_int, read_struct, roster_address
from fabiomh.game.seed import decrypt_seed
from fabiomh.game.structs import UI, Act, ActMisc, DynamicPath, ItemData, Level, Room1, Room2, RosterUnit, UnitAny
from fabiomh.game.units import UNIT_TYPE_ITEM, UNIT_TYPE_PLAYER, iter_units
from fabiomh.log import report

PLAYER_DEAD_MODES = (0, 17)
PLAYER_MODE_DEAD = 17
PARTY_NONE = 0xFFFF
ROSTER_MAX = 16  # guard against a corrupted list (the game has up to 8 players)

INVENTORY_SIGNATURE = 0x01020304  # Inventory+0x00; Inventory+0x08 = owning unit
ITEM_MODES_OWNED = (0, 1)         # 0 = stored (inventory/stash/cube), 1 = equipped
OWNER_NONE = 0xFFFFFFFF           # dwOwnerId of an ownerless item (on the ground)
ITEM_DATA_SCAN_SIZE = 0x100       # how much of ItemData to scan for the pointer to the inventory
ITEM_SCAN_RETRY_SECONDS = 2       # if the scan finds nothing, do not repeat it every tick

item_inventory_offset = None  # offset in ItemData of the pointer to the owning inventory, discovered on the 1st search
next_item_scan = 0

local_unit_id = None  # dwUnitId of the last local player found, so read_other_players does not draw it as another one


def monitor_player(proc, address, ui_address):
    """Returns (difficulty, levelNo, seed, (x, y)) of the local player, or None out of the game."""
    result, reason = find_local_player(proc, address, ui_address)
    if result:
        report("player", reason or "ok")
    else:
        report("player", reason)
    return result


def find_local_player(proc, address, ui_address):
    """Returns (result, None | warning) or (None, readable reason why it was not found)."""
    global local_unit_id

    GameUI = read_struct(proc, ui_address, UI)
    if not GameUI.inGame:
        return None, "fora do jogo (UI.inGame=0)"

    rejected = []   # one reason per discarded player
    not_local = []  # (unit, result) of the players with a valid chain that failed the local test
    count = 0
    ghosts = 0

    for player in iter_units(proc, address, UNIT_TYPE_PLAYER):
        count += 1
        if not player.pAct:
            # Ghost: player unit without an act (only counted, so the reason fits in one line)
            ghosts += 1
            continue
        if player.isCorpse or player.dwMode == PLAYER_MODE_DEAD:
            # Corpse from an earlier death: copy of the character (with the inventory), standing where it appears
            rejected.append(f"cadáver (isCorpse={player.isCorpse} mode={player.dwMode})")
            continue
        if not player.pInventory or not player.pPath:
            # a null c_void_p comes as None
            rejected.append(f"ponteiro nulo (pAct={player.pAct or 0:#x} pInventory={player.pInventory or 0:#x} "
                            f"pPath={player.pPath or 0:#x})")
            continue

        try:
            is_local_player = read_int(proc, player.pInventory + 0x70) != 0
        except Exception as e:
            rejected.append(f"falha ao ler inventory ({type(e).__name__})")
            continue

        result, reason = read_player_state(proc, player)
        label = "local" if is_local_player else "não local"
        if not result:
            rejected.append(f"{label}, {reason}")
            continue

        if is_local_player:
            local_unit_id = player.dwUnitId
            return result, None
        not_local.append((player, result))
        rejected.append(label)

    # Plan C: the local player may be outside the table (a ghost's bucket); search through the items
    try:
        result, unit_id = find_local_by_items(proc, address)
    except Exception:
        # Unreadable item table: plan C must not bring down plan B or the log reason
        result = None
    if result:
        local_unit_id = unit_id
        return result, "ok pelo plano C: player local fora da tabela de players, achado pelos itens"

    # Plan B: the pInventory+0x70 test sometimes gives 0 on the local player itself (measured in a game created alone).
    # If there is only one living player with a valid chain, it is the local one.
    if len(not_local) == 1:
        player, result = not_local[0]
        local_unit_id = player.dwUnitId
        return result, "ok pelo plano B: único player vivo, mas pInventory+0x70=0"

    if not count:
        return None, "nenhum player legível na hash table"

    ghost_note = f"{ghosts} fantasma(s) (pAct=0) ignorado(s)" if ghosts else ""
    if not rejected:
        return None, f"{ghost_note}; player local ausente"
    if ghosts:
        rejected.append(ghost_note)
    return None, f"{count - ghosts} player(s), nenhum válido: " + "; ".join(rejected)


def find_local_by_items(proc, address):
    """Plan C. Returns (result, dwUnitId) of the local player found through the items, or (None, None)."""
    global next_item_scan

    if item_inventory_offset is None and time.monotonic() < next_item_scan:
        return None, None

    owners = find_item_owners(proc, address)
    if item_inventory_offset is None:
        next_item_scan = time.monotonic() + ITEM_SCAN_RETRY_SECONDS

    # In a game with other players, their equipped items also show up: the local test applies, and without it,
    # only if there is a single owner
    candidates = []
    for owner in owners.values():
        if owner.isCorpse or owner.dwMode == PLAYER_MODE_DEAD or not owner.pInventory or not owner.pPath:
            continue
        result, _ = read_player_state(proc, owner)
        if not result:
            continue
        try:
            if read_int(proc, owner.pInventory + 0x70) != 0:
                return result, owner.dwUnitId
        except Exception:
            continue
        candidates.append((result, owner.dwUnitId))

    return candidates[0] if len(candidates) == 1 else (None, None)


def find_item_owners(proc, address):
    """{dwOwnerId: unit} of the players with an act that own stored/equipped items, reaching them through the inventory
    (ItemData → Inventory → owning unit), without going through the player table."""
    global item_inventory_offset

    owners = {}
    for item in iter_units(proc, address, UNIT_TYPE_ITEM):
        if item.dwMode not in ITEM_MODES_OWNED or not item.pUnitData:
            continue
        try:
            raw = pm.r_bytes(proc, item.pUnitData, ITEM_DATA_SCAN_SIZE)
        except Exception:
            continue

        owner_id = ItemData.from_buffer_copy(raw[:ct.sizeof(ItemData)]).dwOwnerId
        if owner_id == OWNER_NONE or owner_id in owners:
            continue

        if item_inventory_offset is None:
            offsets = range(0, ITEM_DATA_SCAN_SIZE, 8)
        else:
            offsets = (item_inventory_offset,)
        for offset in offsets:
            owner = inventory_owner(proc, int.from_bytes(raw[offset:offset + 8], "little"))
            # The id matches the item's owner, and it has an act (the owner of the stash items is a ghost, without an act)
            if owner and owner.dwUnitId == owner_id and owner.pAct:
                item_inventory_offset = offset
                owners[owner_id] = owner
                break

    return owners


def inventory_owner(proc, pInventory):
    """The player unit that owns the inventory at pInventory, or None if there is no inventory there."""
    if not 0x10000 <= pInventory < 0x7FFFFFFFFFFF:
        return None
    try:
        raw = pm.r_bytes(proc, pInventory, 0x10)
        if int.from_bytes(raw[:4], "little") != INVENTORY_SIGNATURE:
            return None
        unit = read_struct(proc, int.from_bytes(raw[8:16], "little"), UnitAny)
    except Exception:
        return None
    return unit if unit.dwType == UNIT_TYPE_PLAYER else None


def read_player_state(proc, player):
    """Follows the pointer chain. Returns ((difficulty, levelNo, seed, (x, y)), None) or (None, reason)."""
    step = "act"
    try:
        act = read_struct(proc, player.pAct, Act)
        step = "actMisc"
        actMisc = read_struct(proc, act.pActMisc, ActMisc)

        difficulty = actMisc.game_difficulty

        step = "path"
        path = read_struct(proc, player.pPath, DynamicPath)
        step = "room1"
        room1 = read_struct(proc, path.pRoom1, Room1)
        step = "room2"
        room2 = read_struct(proc, room1.pRoom2, Room2)
        step = "level"
        level = read_struct(proc, room2.pLevel, Level)

        levelNo = level.dwLevelNo
    except Exception as e:
        # Pointers not initialized yet (e.g. during loading)
        return None, f"falha ao ler {step} ({type(e).__name__})"

    # Discards invalid reads of half-initialized structures
    if difficulty > 2 or not (1 <= levelNo <= 136) or not actMisc.dw_end_seed_hash:
        return None, (f"valores inválidos (difficulty={difficulty} levelNo={levelNo} "
                      f"end_hash={actMisc.dw_end_seed_hash:#x})")

    seed = decrypt_seed(actMisc)
    if not seed:
        return None, f"seed=0 (init_hash={actMisc.dw_init_seed_hash:#x} end_hash={actMisc.dw_end_seed_hash:#x})"

    return (difficulty, levelNo, seed, (path.xPos, path.yPos)), None


def read_other_players(proc, address, levelNo):
    """Returns [(x, y, "otherplayer")] of the living players that are not the local one: those in the unit table and the
    party members in area levelNo that are too far away to be in it (from the roster)."""
    players = []
    seen = {local_unit_id}

    for player in iter_units(proc, address, UNIT_TYPE_PLAYER):
        if not player.pAct or not player.pPath or player.isCorpse or player.dwMode in PLAYER_DEAD_MODES:
            continue

        if player.dwUnitId == local_unit_id:
            continue

        try:
            # Without pInventory it cannot be the local one (the test only identifies the local one)
            if player.pInventory and read_int(proc, player.pInventory + 0x70) != 0:
                continue
            path = read_struct(proc, player.pPath, DynamicPath)
        except Exception:
            continue

        seen.add(player.dwUnitId)
        players.append((path.xPos, path.yPos, "otherplayer"))

    for roster in read_roster(proc, address):
        if roster.dwUnitId in seen or roster.wPartyId == PARTY_NONE or roster.dwLevelId != levelNo:
            continue
        if not roster.dwPosX or not roster.dwPartyLife:
            continue
        players.append((roster.dwPosX, roster.dwPosY, "otherplayer"))

    return players


def read_roster(proc, address):
    """The game's RosterUnits (see the top of the module). A read that fails cuts off the rest of the list."""
    units = []
    try:
        node = int.from_bytes(pm.r_bytes(proc, roster_address(address), 8), "little")
        while node and len(units) < ROSTER_MAX:
            unit = read_struct(proc, node, RosterUnit)
            units.append(unit)
            node = unit.pNext
    except Exception:
        pass
    return units
