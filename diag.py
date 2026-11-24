"""One-off diagnosis: run it **in the game where the map did not appear**, with the maphack open or not.

    python diag.py

Makes a single pass and prints everything the maphack uses to find the map: the UI, each unit in the player hash table
(with each step of the pointer chain, value or exception), the hashes and the seed, and generates the act to see whether
the player's position falls inside the area read (and, if not, in which area of the act it falls).
"""
from collections import Counter

from fabiomh.game import memory
from fabiomh.game import player as player_module
from fabiomh.game.memory import read_int, read_struct
from fabiomh.game.seed import decrypt_seed
from fabiomh.game.structs import UI, Act, ActMisc, DynamicPath, ItemData, Level, Room1, Room2, UnitAny, UnitHashTable
from fabiomh.game.units import UNIT_TYPE_ITEM, UNIT_TYPE_MONSTER, UNIT_TYPE_PLAYER, iter_units
from fabiomh.mapgen.generator import level_act, read_act, run_map_generator
from fabiomh.overlay.points import inside_map


def ptr(value):
    # a null c_void_p comes as None
    return f"{value or 0:#x}"


def walk_player(proc, player):
    """Follows player.py's pointer chain printing each step. Returns (actMisc, levelNo, path) or None."""
    try:
        local_flag = read_int(proc, player.pInventory + 0x70)
        print(f"    pInventory+0x70 = {local_flag} ({'local' if local_flag else 'não local'})")
    except Exception as e:
        print(f"    pInventory+0x70: {type(e).__name__}: {e}")
        return None

    # First 0x80 bytes of the inventory, as u64: to find a better local test than +0x70
    try:
        raw = memory.pm.r_bytes(proc, player.pInventory, 0x80)
        words = [int.from_bytes(raw[i:i + 8], "little") for i in range(0, 0x80, 8)]
        for row in range(0, len(words), 4):
            print(f"    inv+{row * 8:#04x}: " + " ".join(f"{w:#018x}" for w in words[row:row + 4]))
    except Exception as e:
        print(f"    inventário: {type(e).__name__}: {e}")

    steps = [
        ("act", lambda _: read_struct(proc, player.pAct, Act)),
        ("actMisc", lambda act: read_struct(proc, act.pActMisc, ActMisc)),
        ("path", lambda _: read_struct(proc, player.pPath, DynamicPath)),
        ("room1", lambda path: read_struct(proc, path.pRoom1, Room1)),
        ("room2", lambda room1: read_struct(proc, room1.pRoom2, Room2)),
        ("level", lambda room2: read_struct(proc, room2.pLevel, Level)),
    ]
    values = {}
    previous = None
    for name, read in steps:
        try:
            previous = values[name] = read(previous)
        except Exception as e:
            print(f"    {name}: {type(e).__name__}: {e}")
            return None

    actMisc, path, level = values["actMisc"], values["path"], values["level"]
    print(f"    act.pActMisc={ptr(values['act'].pActMisc)} path.pRoom1={ptr(path.pRoom1)} "
          f"room1.pRoom2={ptr(values['room1'].pRoom2)} room2.pLevel={ptr(values['room2'].pLevel)}")
    print(f"    difficulty={actMisc.game_difficulty} levelNo={level.dwLevelNo} pos=({path.xPos}, {path.yPos})")
    print(f"    init_hash={actMisc.dw_init_seed_hash:#x} end_hash={actMisc.dw_end_seed_hash:#x}")
    return actMisc, level.dwLevelNo, path


def describe_path(proc, player):
    """For a unit without pAct: whatever can be read (local flag and position), to know if it is a real unit or a ghost."""
    if player.pInventory:
        try:
            print(f"    pInventory+0x70 = {read_int(proc, player.pInventory + 0x70)}")
        except Exception as e:
            print(f"    pInventory+0x70: {type(e).__name__}")
    if player.pPath:
        try:
            path = read_struct(proc, player.pPath, DynamicPath)
            print(f"    pos=({path.xPos}, {path.yPos}) pRoom1={ptr(path.pRoom1)}")
        except Exception as e:
            print(f"    path: {type(e).__name__}")


def count_other_tables(proc, unit_address):
    """How many units there are in the monster and item tables: if they are full, the table is the current game's."""
    for name, unit_type in (("monstros", UNIT_TYPE_MONSTER), ("itens", UNIT_TYPE_ITEM)):
        count = sum(1 for _ in iter_units(proc, unit_address, unit_type))
        print(f"  {name} na tabela: {count}")


UNIT_TYPE_NAMES = {0: "players", 1: "monstros", 2: "objetos", 3: "mísseis", 4: "itens", 5: "tiles"}
ITEM_MODES_OWNED = (0, 1)  # 0 = stored (inventory/stash/cube), 1 = equipped


def read_all_units(proc, unit_address):
    """{address: (type, unit)} of the 6 unit tables."""
    units = {}
    for unit_type in UNIT_TYPE_NAMES:
        for bucket_head in read_struct(proc, unit_address + unit_type * 0x400, UnitHashTable).table:
            pUnit = bucket_head
            while pUnit:
                try:
                    unit = read_struct(proc, pUnit, UnitAny)
                except Exception:
                    break
                units[pUnit] = (unit_type, unit)
                pUnit = unit.pListNext
    return units


def describe_unit(unit_type, unit):
    return (f"{UNIT_TYPE_NAMES[unit_type]} id={unit.dwUnitId} txt={unit.dwTxtFileNo} mode={unit.dwMode} "
            f"pAct={ptr(unit.pAct)}")


def search_local_player(proc, unit_address):
    """Looks for the local player through paths that do not depend on the player table: owner of the items and
    pointers inside each player's inventory."""
    print("\n== Busca do player local por outros caminhos")
    units = read_all_units(proc, unit_address)
    by_id = {}
    for address, (unit_type, unit) in units.items():
        by_id.setdefault(unit.dwUnitId, []).append((address, unit_type, unit))

    # 1. Owner of the stored/equipped items: the most common one should be the character's id
    owners = Counter()
    for unit_type, unit in units.values():
        if unit_type != UNIT_TYPE_ITEM or unit.dwMode not in ITEM_MODES_OWNED or not unit.pUnitData:
            continue
        try:
            owners[read_struct(proc, unit.pUnitData, ItemData).dwOwnerId] += 1
        except Exception:
            continue
    print(f"  donos dos itens guardados/equipados (ItemData.dwOwnerId, a conferir): {owners.most_common(5)}")
    for owner_id, _ in owners.most_common(3):
        matches = by_id.get(owner_id, [])
        where = "; ".join(f"{address:#x} {describe_unit(t, u)}" for address, t, u in matches) or "em nenhuma tabela"
        print(f"    id {owner_id}: {where}")

    # 2. player.py's plan C: ItemData → Inventory → owning unit
    owners_by_items = player_module.find_item_owners(proc, unit_address)
    print(f"  plano C: offset do inventário no ItemData = "
          f"{'não achado' if player_module.item_inventory_offset is None else hex(player_module.item_inventory_offset)}")
    for owner_id, owner in owners_by_items.items():
        in_table = any(t == UNIT_TYPE_PLAYER and u.dwUnitId == owner_id for t, u in units.values())
        print(f"    dono {owner_id}: {describe_unit(UNIT_TYPE_PLAYER, owner)} "
              f"({'na tabela' if in_table else 'FORA da tabela'})")

    # 3. Pointers inside each player's inventory: does any lead to a player with pAct?
    for address, (unit_type, unit) in units.items():
        if unit_type != UNIT_TYPE_PLAYER or not unit.pInventory:
            continue
        try:
            raw = memory.pm.r_bytes(proc, unit.pInventory, 0x80)
        except Exception:
            continue
        for offset in range(0, 0x80, 8):
            value = int.from_bytes(raw[offset:offset + 8], "little")
            if value == address:
                print(f"  player {unit.dwUnitId}: inv+{offset:#04x} aponta para a própria unit")
            elif value in units:
                print(f"  player {unit.dwUnitId}: inv+{offset:#04x} → {value:#x} {describe_unit(*units[value])}")
            elif 0x10000 <= value < 0x7FFFFFFFFFFF:
                try:
                    target = read_struct(proc, value, UnitAny)
                except Exception:
                    continue
                if target.dwType == UNIT_TYPE_PLAYER and target.pAct and target.pPath and target.dwUnitId:
                    print(f"  player {unit.dwUnitId}: inv+{offset:#04x} → {value:#x} player FORA da tabela: "
                          f"{describe_unit(UNIT_TYPE_PLAYER, target)}")

    return owners_by_items


def check_map(seed, difficulty, levelNo, pos):
    print(f"\n== Mapa (seed {seed}, difficulty {difficulty}, área {levelNo}, ato {level_act(levelNo)})")
    act_levels = read_act(seed, difficulty, level_act(levelNo))
    if not act_levels:
        print("  d2-mapgen.exe não devolveu nenhuma área")
        return
    print(f"  áreas no ato: {sorted(act_levels)}")

    # In which area (offset + size rectangle) the player's position falls
    containing = [
        level_id for level_id, level in act_levels.items()
        if level["offset"]["x"] <= pos[0] < level["offset"]["x"] + level["size"]["width"]
        and level["offset"]["y"] <= pos[1] < level["offset"]["y"] + level["size"]["height"]
    ]
    print(f"  áreas cujo retângulo contém a posição {pos}: {containing or 'nenhuma'}")

    map_data = run_map_generator(seed, difficulty, levelNo)
    if not map_data:
        print("  run_map_generator devolveu None")
        return
    meta, bbox, _ = map_data
    print(f"  offset=({meta['offsetx']}, {meta['offsety']}) size={meta['originalwidth']}x{meta['originalheight']} "
          f"bbox={bbox}")
    print(f"  player dentro do mapa: {'sim' if inside_map(*pos, meta, bbox) else 'NÃO (seed ou área errados?)'}")


def main():
    proc, ui_address, unit_address = memory.attach()
    try:
        game_ui = read_struct(proc, ui_address, UI)
        print(f"== UI: inGame={game_ui.inGame} loading={game_ui.loading} bAct={game_ui.bAct}")

        table = read_struct(proc, unit_address + UNIT_TYPE_PLAYER * 0x400, UnitHashTable)
        found = None
        not_local = []  # valid chains that failed the local test (player.py's plan B)
        count = 0

        print("\n== Players")
        for bucket, pUnit in enumerate(table.table):
            position = 0
            while pUnit:
                try:
                    player = read_struct(proc, pUnit, UnitAny)
                except Exception as e:
                    print(f"  bucket {bucket} posição {position} {pUnit:#x}: ILEGÍVEL ({type(e).__name__}: {e}); "
                          f"o resto do bucket é perdido")
                    break

                count += 1
                print(f"  bucket {bucket} posição {position} {pUnit:#x}: id={player.dwUnitId} "
                      f"type={player.dwType} txt={player.dwTxtFileNo} mode={player.dwMode} "
                      f"class={player.playerClass} corpse={player.isCorpse} pUnitData={ptr(player.pUnitData)} "
                      f"pAct={ptr(player.pAct)} pPath={ptr(player.pPath)} pInventory={ptr(player.pInventory)}")
                if player.pAct and player.pInventory and player.pPath:
                    walked = walk_player(proc, player)
                    if walked and not found and read_int(proc, player.pInventory + 0x70):
                        found = walked
                    elif walked:
                        not_local.append(walked)
                else:
                    print("    ponteiro nulo")
                    describe_path(proc, player)

                pUnit = player.pListNext
                position += 1

        if not count:
            print("  hash table vazia")
        count_other_tables(proc, unit_address)
        owners_by_items = search_local_player(proc, unit_address)
        if not found:
            for owner in owners_by_items.values():
                if owner.pInventory and owner.pPath and read_int(proc, owner.pInventory + 0x70):
                    print(f"\nPlano C: player local {owner.dwUnitId} achado pelos itens, fora da tabela de players.")
                    found = walk_player(proc, owner)
                    break
        if not found and len(not_local) == 1:
            print("\nNenhum player passou no teste pInventory+0x70; plano B: o único player vivo é o local.")
            found = not_local[0]
        if not found:
            print("\nNenhum player local com a cadeia inteira legível.")
            return

        actMisc, levelNo, path = found
        seed = decrypt_seed(actMisc)
        print(f"\n== Seed decriptado: {seed}")
        if seed and actMisc.game_difficulty <= 2 and 1 <= levelNo <= 136:
            check_map(seed, actMisc.game_difficulty, levelNo, (path.xPos, path.yPos))
    finally:
        memory.close(proc)


if __name__ == "__main__":
    main()
