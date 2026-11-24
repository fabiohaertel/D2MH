"""Items on the ground (unit table type 4): the single pass per tick, used by the runes (runes.py) and the drops (drops.py).

- A dropped item goes through dwMode 5 (being dropped) and then 3 (on the ground).
- Position: an item's pPath points to an ItemPath (xPos at 0x10, yPos at 0x14), in world coordinates.
"""
from collections import namedtuple

from fabiomh.game.memory import read_struct
from fabiomh.game.structs import ItemPath
from fabiomh.game.units import UNIT_TYPE_ITEM, iter_units

ITEM_MODES_ON_GROUND = (3, 5)  # 3 = on the ground, 5 = being dropped

GroundItem = namedtuple("GroundItem", "unit x y")


def read_ground_items(proc, address):
    """Returns [GroundItem(unit, x, y)] of all items on the ground."""
    items = []

    for unit in iter_units(proc, address, UNIT_TYPE_ITEM):
        if unit.dwMode not in ITEM_MODES_ON_GROUND or not unit.pPath:
            continue

        try:
            path = read_struct(proc, unit.pPath, ItemPath)
        except Exception:
            continue

        items.append(GroundItem(unit, path.xPos, path.yPos))

    return items
