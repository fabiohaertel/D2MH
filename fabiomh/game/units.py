from fabiomh.game.memory import read_struct
from fabiomh.game.structs import UnitAny, UnitHashTable
from fabiomh.log import report

UNIT_TYPE_PLAYER = 0
UNIT_TYPE_MONSTER = 1
UNIT_TYPE_OBJECT = 2
UNIT_TYPE_ITEM = 4


# Walks the hash table of one unit type: 128 buckets, and each bucket is a linked list through pListNext.
# An unreadable unit in the middle of the list cuts off the rest of the bucket (without it there is no pListNext). For
# players this can hide the local player, so the failure is logged (players only: the monster lists change every tick).
def iter_units(proc, address, unit_type):
    units = read_struct(proc, address + unit_type * 0x400, UnitHashTable)
    broken = []

    for bucket, pUnit in enumerate(units.table):
        position = 0
        while pUnit:
            try:
                unit = read_struct(proc, pUnit, UnitAny)
            except Exception:
                broken.append(f"bucket {bucket}, posição {position}, {pUnit:#x}")
                break
            pUnit = unit.pListNext
            position += 1

            yield unit

    if unit_type == UNIT_TYPE_PLAYER:
        report("units", "unit ilegível cortou a lista: " + "; ".join(broken) if broken else None)
