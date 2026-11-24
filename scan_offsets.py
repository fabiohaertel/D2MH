"""Finds the static offsets of `fabiomh/game/memory.py` again after a D2R patch. Run it with the game open and the
character **inside a game**, and follow the steps in the terminal:

    python scan_offsets.py

It prints the three offsets to paste into `memory.py` and says whether they changed. It writes nothing.

Code signatures (AOB) do not work: they do not survive patches, and on 3.3.93847 only ~27% of the `.text` pages can be
read (the rest is decrypted on demand). Everything here uses only `.data`, which reads in full:

- **UI (guided):** snapshots of `.data` while you open and close the inventory (I) and the character screen (C). What is
  left is the byte that is 1 only with the inventory open (`invMenu`) and the one that is 1 only with the character
  screen open (`charMenu`). If the layout of `structs.UI` did not change (`charMenu = invMenu + 1` and `inGame` at
  `invMenu - 1` equal to 1), `UI_OFFSET = invMenu - 1`. If it changed, the script says where each byte ended up, to
  adjust `structs.UI`.
- **Unit table (structure):** 6 tables of 128 pointers, 0x400 bytes apart (see `units.py`), in which each unit has
  `dwType` = table type and `dwUnitId % 128` = bucket.
- **Roster (structure):** a pointer to a `RosterUnit` with a readable name and the `dwUnitId` of a player in the unit
  table. The scan starts near the unit table (on 3.3.93847 they are 0x16310 bytes from each other).

If the unit table or the roster is not found, the layout of `UnitAny` (`dwType`/`dwUnitId` at 0x00/0x08) or of
`RosterUnit` (`szName` at 0x00, `dwUnitId` at 0x48) probably changed.
"""
import struct

import numpy as np

from fabiomh.game import memory
from fabiomh.game.memory import pm, read_struct
from fabiomh.game.structs import UI, RosterUnit

PAGE = 0x1000
CHUNK = 0x100000
UNIT_TYPES_CHECKED = (0, 1, 4)  # player, monster, item: the ones that always have units inside a game
MAX_EXTRA_ROUNDS = 6            # extra open/close rounds when more than one candidate is left
UI_LAYOUT_SPAN = 0x40           # maximum distance between invMenu and charMenu to consider them part of the same struct


def read_range(proc, base, start, end):
    """Reads [start, end) of the module. Returns (bytes, pages that could not be read). Unreadable pages are zeroed."""
    buf = bytearray(end - start)
    missing = []
    for off in range(start, end, CHUNK):
        n = min(CHUNK, end - off)
        try:
            buf[off - start:off - start + n] = pm.r_bytes(proc, base + off, n)
            continue
        except Exception:
            pass
        for p in range(off, off + n, PAGE):
            m = min(PAGE, end - p)
            try:
                buf[p - start:p - start + m] = pm.r_bytes(proc, base + p, m)
            except Exception:
                missing.append(p)
    return bytes(buf), missing


def read_sections(proc, base):
    """{name: (va, size)} from the PE header of the loaded module."""
    head = pm.r_bytes(proc, base, PAGE)
    pe = struct.unpack_from("<I", head, 0x3C)[0]
    count = struct.unpack_from("<H", head, pe + 6)[0]
    opt_size = struct.unpack_from("<H", head, pe + 20)[0]
    sections = {}
    for i in range(count):
        o = pe + 24 + opt_size + 40 * i
        name = head[o:o + 8].rstrip(b"\0").decode(errors="replace")
        vsize, va = struct.unpack_from("<II", head, o + 8)
        sections[name] = (va, vsize)
    return sections


# ---------------------------------------------------------------------------------------------------------- UI


class GuidedScan:
    """Snapshots of .data, each with the expected state of (inventory, character screen)."""

    def __init__(self, proc, base, data_va, data_end):
        self.proc, self.base, self.data_va, self.data_end = proc, base, data_va, data_end
        self.inv = None   # mask: bytes that followed the inventory in all snapshots
        self.char = None  # same, character screen
        self.last = None  # last snapshot, to check inGame

    def step(self, text, inv_open, char_open):
        input(f"\n>> {text} e aperte Enter aqui... ")
        data, missing = read_range(self.proc, self.base, self.data_va, self.data_end)
        if missing:
            print(f"   ({len(missing)} páginas do .data ilegíveis)")
        a = np.frombuffer(data, dtype=np.uint8)
        inv_hit, char_hit = a == int(inv_open), a == int(char_open)
        self.inv = inv_hit if self.inv is None else self.inv & inv_hit
        self.char = char_hit if self.char is None else self.char & char_hit
        self.last = a
        print(f"   candidatos: inventário {int(self.inv.sum())}, personagem {int(self.char.sum())}")

    def offsets(self, mask):
        return [self.data_va + int(i) for i in np.nonzero(mask)[0]]


def guided_ui(proc, base, data_va, data_end):
    """Returns (UI_OFFSET or None, text explaining the result)."""
    scan = GuidedScan(proc, base, data_va, data_end)
    scan.step("Dentro do jogo, com TODOS os menus fechados", 0, 0)
    scan.step("Abra o INVENTÁRIO (I), só ele", 1, 0)
    scan.step("Feche o inventário", 0, 0)
    scan.step("Abra o PERSONAGEM (C), só ele", 0, 1)
    scan.step("Feche o personagem", 0, 0)
    scan.step("Abra o INVENTÁRIO (I) de novo, só ele", 1, 0)
    scan.step("Feche tudo", 0, 0)

    # Extra rounds while more than one candidate is left and the previous round eliminated some (a byte that
    # copies the flag never goes away; then the neighboring inventory/character pair decides, below)
    previous = None
    for _ in range(MAX_EXTRA_ROUNDS):
        counts = (int(scan.inv.sum()), int(scan.char.sum()))
        if counts == previous:
            break
        previous = counts
        if scan.inv.sum() > 1:
            scan.step("Ainda há mais de um candidato. Abra o INVENTÁRIO (I)", 1, 0)
            scan.step("Feche o inventário", 0, 0)
        elif scan.char.sum() > 1:
            scan.step("Ainda há mais de um candidato. Abra o PERSONAGEM (C)", 0, 1)
            scan.step("Feche o personagem", 0, 0)
        else:
            break

    invs, chars = scan.offsets(scan.inv), scan.offsets(scan.char)
    print("\ninventário (invMenu): " + (", ".join(f"{o:#x}" for o in invs[:10]) or "nenhum"))
    print("personagem (charMenu): " + (", ".join(f"{o:#x}" for o in chars[:10]) or "nenhum"))

    # Nearby inventory/character pairs: both belong to the same struct
    pairs = [(i, c) for i in invs for c in chars if abs(c - i) <= UI_LAYOUT_SPAN]
    if not pairs:
        return None, "nenhum par inventário/personagem próximo; repita (menus abertos/fechados certinho?)"
    for inv, char in pairs:
        in_game = int(scan.last[inv - 1 - data_va])
        if char == inv + 1 and in_game == 1:
            return inv - 1, f"layout igual ao structs.UI (inGame={in_game} em {inv - 1:#x})"
    lines = [f"invMenu {i:#x}, charMenu {c:#x} (charMenu - invMenu = {c - i:+#x})" for i, c in pairs]
    return None, ("o layout do UI mudou; ajuste structs.UI e o UI_OFFSET a partir destes pares:\n   "
                  + "\n   ".join(lines))


# ------------------------------------------------------------------------------------------ unit table and roster


def pointer_mask(q, base, size):
    """Values that look like a heap pointer (canonical, outside the module)."""
    return (q >= 0x10000) & (q < 0x7FFFFFFFFFFF) & ~((q >= base) & (q < base + size))


def window_sums(mask, width):
    """s[i] = sum of mask[i:i+width]."""
    c = np.concatenate(([0], np.cumsum(mask, dtype=np.int64)))
    return c[width:] - c[:-width]


def as_qwords(data):
    return np.frombuffer(data[:len(data) // 8 * 8], dtype=np.uint64)


def find_unit_table(proc, base, size, data, data_va):
    """List of (offset, units checked, player ids)."""
    q = as_qwords(data)
    nonzero = window_sums(q != 0, 128)
    pointers = window_sums(pointer_mask(q, base, size), 128)
    n = len(q) - 6 * 128
    ok = np.ones(n, bool)
    for t in range(6):
        nz, pt = nonzero[t * 128:t * 128 + n], pointers[t * 128:t * 128 + n]
        ok &= nz == pt  # table with only zeros and pointers
        if t in UNIT_TYPES_CHECKED:
            ok &= pt >= 1
    found = []
    for i in np.nonzero(ok)[0]:
        checked, player_ids, good = 0, set(), True
        for t in UNIT_TYPES_CHECKED:
            for bucket in range(128):
                p = int(q[i + t * 128 + bucket])
                if not p:
                    continue
                try:
                    unit_type, _, unit_id = struct.unpack("<III", pm.r_bytes(proc, p, 12))
                except Exception:
                    good = False
                    break
                if unit_type != t or unit_id % 128 != bucket:
                    good = False
                    break
                checked += 1
                if t == 0:
                    player_ids.add(unit_id)
            if not good:
                break
        if good:
            found.append((data_va + int(i) * 8, checked, player_ids))
    return found


def roster_name(proc, base, offset, player_ids):
    """Does the pointer at base+offset lead to a RosterUnit of a player in the unit table? Returns the name or None."""
    try:
        roster = read_struct(proc, pm.r_uint64(proc, base + offset), RosterUnit)
    except Exception:
        return None
    name = roster.szName
    if not name or not all(32 <= c < 127 for c in name) or roster.dwUnitId not in player_ids:
        return None
    return name.decode()


def find_roster(proc, base, size, data, data_va, player_ids, near):
    """List of (offset, name), scanning the .data pointers starting from the ones closest to `near`."""
    q = as_qwords(data)
    offsets = data_va + np.nonzero(pointer_mask(q, base, size))[0].astype(np.int64) * 8
    found = []
    for offset in offsets[np.argsort(np.abs(offsets - near), kind="stable")]:
        name = roster_name(proc, base, int(offset), player_ids)
        if name:
            found.append((int(offset), name))
            if len(found) >= 3:
                break
    return found


# --------------------------------------------------------------------------------------------------------- main


def report(name, current, found):
    if found is None:
        print(f"{name} = ???  (não achou; atual {current:#x})")
    else:
        print(f"{name} = {found:#x}  ({'igual ao atual' if found == current else f'MUDOU, atual {current:#x}'})")


def main():
    proc = pm.open_process("D2R.exe")
    try:
        module = pm.get_module(proc, "D2R.exe")
        base, size = module["base"], module["size"]
        data_va, data_size = read_sections(proc, base)[".data"]
        data_end = data_va + data_size
        print(f"D2R.exe base={base:#x} tamanho={size:#x} .data={data_va:#x}+{data_size:#x}")
        result = {}

        print("\n== UI (guiado)")
        ui_offset, why = guided_ui(proc, base, data_va, data_end)
        print(why)
        if ui_offset is not None:
            result["UI_OFFSET"] = ui_offset
            ui = read_struct(proc, base + ui_offset, UI)
            print(f"conferência: inGame={ui.inGame} bAct={ui.bAct} (ato {ui.bAct + 1}?)")

        print("\n== Unit table e roster (estrutura)")
        data, _ = read_range(proc, base, data_va, data_end)
        tables = find_unit_table(proc, base, size, data, data_va)
        for offset, checked, ids in tables:
            print(f"unit table {offset:#x}: {checked} units conferidas, {len(ids)} players")
        if len(tables) == 1:
            offset, _, player_ids = tables[0]
            result["UNIT_TABLE_OFFSET"] = offset
            rosters = find_roster(proc, base, size, data, data_va, player_ids, offset)
            for r_offset, name in rosters:
                print(f"roster {r_offset:#x} → {name}")
            if rosters:
                result["ROSTER_OFFSET"] = rosters[0][0]
            else:
                print("roster: nada (mudou o layout do RosterUnit?)")
        elif not tables:
            print("unit table: nada (dentro de um jogo? mudou o layout do UnitAny?)")
        else:
            print("unit table: mais de uma; confira com o diag.py")

        print("\n== Cole em fabiomh/game/memory.py")
        for name in ("UI_OFFSET", "UNIT_TABLE_OFFSET", "ROSTER_OFFSET"):
            report(name, getattr(memory, name), result.get(name))
    finally:
        pm.close_process(proc)


if __name__ == "__main__":
    main()
