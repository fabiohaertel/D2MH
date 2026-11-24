"""Runes on the ground, from the items read by items.read_ground_items.

- Measured in game: El = 625 … Zod = 657, in RUNE_NAMES order (Eth = 629, Ral = 632).
  The value 610, quoted by several tools, is wrong for this D2R version.
- The list of runes shown is in config.RUNES_TO_SHOW.
"""
from config import RUNES_TO_SHOW

RUNE_NAMES = ["El", "Eld", "Tir", "Nef", "Eth", "Ith", "Tal", "Ral", "Ort", "Thul", "Amn", "Sol", "Shael", "Dol",
              "Hel", "Io", "Lum", "Ko", "Fal", "Lem", "Pul", "Um", "Mal", "Ist", "Gul", "Vex", "Ohm", "Lo",
              "Sur", "Ber", "Jah", "Cham", "Zod"]
FIRST_RUNE_TXT_FILE_NO = 625  # El

# txtFileNo -> name. A wrong name in RUNES_TO_SHOW raises ValueError right at startup
RUNE_TXT_FILE_NOS = {FIRST_RUNE_TXT_FILE_NO + RUNE_NAMES.index(name): name for name in RUNES_TO_SHOW}


def runes_from(first_name):
    """[(txtFileNo, name)] from rune first_name up. A wrong name raises ValueError right at startup."""
    start = RUNE_NAMES.index(first_name)
    return [(FIRST_RUNE_TXT_FILE_NO + i, RUNE_NAMES[i]) for i in range(start, len(RUNE_NAMES))]


def rune_units(items, skip_txts=()):
    """items: [GroundItem]. Returns [(x, y, "rune", name)] of the monitored runes, except those in skip_txts (the ones
    that already have the drop marker, so as not to draw two in the same place)."""
    return [(item.x, item.y, "rune", RUNE_TXT_FILE_NOS[item.unit.dwTxtFileNo])
            for item in items
            if item.unit.dwTxtFileNo in RUNE_TXT_FILE_NOS and item.unit.dwTxtFileNo not in skip_txts]
