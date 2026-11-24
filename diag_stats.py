"""Immunity diagnosis: run it **inside a game, near monsters** (preferably elites, in Hell).

    python diag_stats.py

It only reads memory. It does not trust the known offsets of the stat list: it scans the header of `UnitAny.pStatList`
for (pointer, count) pairs whose target looks like a stat array (WORD layer, WORD stat, int value) and prints the
resistances of each pair. To know which list is right, compare with the "Immune to ..." in the monster's name in game.
It also measures the time of `read_monsters` and the cost of the extra reads per elite. Use it again after a patch.
"""
import time

from fabiomh.game import memory
from fabiomh.game.memory import read_struct
from fabiomh.game.monsters import MERC_TXT_FILE_NOS, read_monsters
from fabiomh.game.structs import UI, DynamicPath, MonsterData
from fabiomh.game.units import UNIT_TYPE_MONSTER, iter_units

HEADER_SIZE = 0x100
MAX_STATS = 512
MAX_NORMALS = 3  # normal monsters listed, only to compare the layout
RESISTS = {36: "physical", 37: "magic", 39: "fire", 41: "light", 43: "cold", 45: "poison"}
TIMING_ROUNDS = 20


def kind_of(flags):
    if flags & (2 | 8):
        return "unique" if flags & 8 else "superunique"
    if flags & 4:
        return "champion"
    if flags & 16:
        return "minion"
    return "normal"


def read_stats(proc, pointer, count):
    """[(layer, stat, value)] of the array, or None if it does not look like a stat array."""
    raw = memory.pm.r_bytes(proc, pointer, count * 8)
    stats = []
    for i in range(0, count * 8, 8):
        stats.append((int.from_bytes(raw[i:i + 2], "little"), int.from_bytes(raw[i + 2:i + 4], "little"),
                      int.from_bytes(raw[i + 4:i + 8], "little", signed=True)))
    # A real stat: id within ItemStatCost (a few hundred) in all entries
    return stats if all(stat < 512 for _, stat, _ in stats) else None


def scan_header(proc, pStatList):
    """Prints every (pointer, count) pair of the header that leads to a stat array."""
    raw = memory.pm.r_bytes(proc, pStatList, HEADER_SIZE)
    words = [int.from_bytes(raw[i:i + 8], "little") for i in range(0, HEADER_SIZE, 8)]
    found = 0

    for index, (pointer, count) in enumerate(zip(words, words[1:])):
        if not 0x10000 <= pointer < 0x7FFFFFFFFFFF or not 0 < count <= MAX_STATS:
            continue
        try:
            stats = read_stats(proc, pointer, count)
        except Exception:
            continue
        if not stats:
            continue
        found += 1
        resists = {RESISTS[stat]: value for _, stat, value in stats if stat in RESISTS}
        immune = sorted(name for name, value in resists.items() if value >= 100)
        print(f"      +{index * 8:#04x}: {count} stats, resistências={resists} imune={immune}")
        print(f"        (layer, stat, valor): {stats}")

    if not found:
        print("      nenhum array de stats no cabeçalho")
        for row in range(0, len(words), 4):
            print(f"      +{row * 8:#04x}: " + " ".join(f"{word:#018x}" for word in words[row:row + 4]))


def measure(proc, unit_address, elites):
    start = time.perf_counter()
    for _ in range(TIMING_ROUNDS):
        result = read_monsters(proc, unit_address)
    per_tick = (time.perf_counter() - start) / TIMING_ROUNDS * 1000
    print(f"\n== Tempo: read_monsters = {per_tick:.2f} ms por tick ({len(result)} monstros)")

    if elites:
        start = time.perf_counter()
        for _ in range(TIMING_ROUNDS):
            for pStatList in elites:
                memory.pm.r_bytes(proc, pStatList, HEADER_SIZE)
        per_round = (time.perf_counter() - start) / TIMING_ROUNDS * 1000
        print(f"   uma leitura de cabeçalho em {len(elites)} elites = {per_round:.3f} ms; "
              f"com o array, estimar o dobro ({per_round * 2:.3f} ms por tick)")


def main():
    proc, ui_address, unit_address = memory.attach()
    try:
        print(f"== UI: inGame={read_struct(proc, ui_address, UI).inGame}")
        elites = []
        normals = 0
        total = 0

        for monster in iter_units(proc, unit_address, UNIT_TYPE_MONSTER):
            if monster.dwMode in (0, 12) or not monster.pPath or monster.dwTxtFileNo in MERC_TXT_FILE_NOS:
                continue
            total += 1
            try:
                path = read_struct(proc, monster.pPath, DynamicPath)
                flags = read_struct(proc, monster.pUnitData, MonsterData).typeFlags if monster.pUnitData else 0
            except Exception as e:
                print(f"  id={monster.dwUnitId}: ilegível ({type(e).__name__})")
                continue

            kind = kind_of(flags)
            if kind == "normal":
                normals += 1
                if normals > MAX_NORMALS:
                    continue
            print(f"  {kind} txt={monster.dwTxtFileNo} id={monster.dwUnitId} flags={flags} "
                  f"pos=({path.xPos}, {path.yPos}) pStatList={monster.pStatList or 0:#x}")
            if not monster.pStatList:
                continue
            if kind != "normal":
                elites.append(monster.pStatList)
            try:
                scan_header(proc, monster.pStatList)
            except Exception as e:
                print(f"      cabeçalho ilegível ({type(e).__name__}: {e})")

        print(f"\n== Monstros vivos: {total}; elites com lista de stats: {len(elites)}")
        measure(proc, unit_address, elites)
    finally:
        memory.close(proc)


if __name__ == "__main__":
    main()
