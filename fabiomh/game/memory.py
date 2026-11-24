"""D2R memory access through pyMeow.

Static offsets from the base of the D2R.exe module. They belong to a specific game version and break on patches:
- UI struct: base + 0x1ECE2D8 (`UI.inGame` at byte 0)
- Unit hash table: base + 0x1EBE5F0; one table per unit type, 0x400 bytes apart
  (0 = player, 1 = monster, 4 = item). See `units.iter_units`.
- Roster (list of players in the game, with the position of the party members): base + 0x1ED4900, pointer to the
  first `RosterUnit`. See `player.read_other_players`.

Measured on 3.4.95032 (on 3.3.93847 they were 0x1EBD158, 0x1EAD470 and 0x1EC3780: all three moved +0x11180). After a
patch, `python scan_offsets.py` (inside a game, opening and closing menus when it asks) finds all three again.
"""
import ctypes as ct
import sys
from typing import Type

sys.path.append(r"c:/dev/pyMeow-1.73.42")
import pyMeow as pm  # type: ignore

UI_OFFSET = 0x1ECE2D8
UNIT_TABLE_OFFSET = 0x1EBE5F0
ROSTER_OFFSET = 0x1ED4900


PROCESS_NAME = "D2R.exe"


def game_running(process_name=PROCESS_NAME):
    """True if the game process is open (by name; does not depend on an already open proc)."""
    return pm.process_exists(process_name)


def attach(process_name=PROCESS_NAME):
    """Opens the process and returns (proc, ui_address, unit_address)."""
    proc = pm.open_process(process_name)
    base = pm.get_module(proc, process_name)["base"]
    return proc, base + UI_OFFSET, base + UNIT_TABLE_OFFSET


def roster_address(unit_address):
    """Address of the pointer to the roster, from the unit hash table's (both are static in the module)."""
    return unit_address - UNIT_TABLE_OFFSET + ROSTER_OFFSET


def close(proc):
    pm.close_process(proc)


def read_struct(proc, address, Ts: Type[ct.Structure]) -> ct.Structure:
    return Ts.from_buffer_copy(pm.r_bytes(proc, address, ct.sizeof(Ts)))


def read_int(proc, address):
    return pm.r_int(proc, address)
