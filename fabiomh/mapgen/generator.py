"""Map from the d2-mapgen.exe JSON (dep/mapgen/mapgen/), with no PNG or file.

- `./game --seed S --difficulty D --act A` prints one `{"type":"map", ...}` line per area of the act (~0.3 s).
  We run it per act, not per area (`--map`, ~0.2 s), for two reasons: the border exits need the neighboring areas
  (objects.edge_exits), and the whole act stays in `act_cache`, so changing area within the same act is instant.
  d2-mapgenerator.exe (the wrapper that generated the PNG) took ~1.3 s per new area, plus the crop.
- `map` is the collision in RLE, one list per row y, alternating "skip" and "fill" starting with "skip".
  The filled cells are the **walkable** ones. Rows missing at the end are empty.
- What we draw is the border of the walkable area (walkable cell with a non-walkable 4-connected neighbor), like the
  gray of the old PNG. It may differ from it by 1 px on the right/bottom borders, which does not show.
- The bbox is the rectangle of the border after the coords.world_to_map rotation. It replaces the image crop.
- `edges` goes to the JS as bits (np.packbits, row by row) in base64: a 720×960 map gives ~115 KB.
- `meta["route"]`: the path to the next area (mapgen/route.py), or None. Computed here so it stays in the cache.
- `name` comes from the JSON with the internal Levels.txt name (e.g. 114 = "Cellar of Pity", 111 = "Rigid Highlands"),
  which is not what the game shows on the waypoint. `read_act` replaces it with the game name (`LEVEL_NAMES`; the
  missing ones already match).
- The caches live in memory: after changing the map logic, restart the script.
"""
import base64
import json
import math
import subprocess

import numpy as np  # type: ignore

from fabiomh.log import report
from fabiomh.mapgen.coords import COS45, world_to_map
from fabiomh.mapgen.objects import read_markers
from fabiomh.mapgen.route import build_route
from fabiomh.paths import INNER_MAPGEN_EXE, MAPGEN_DIR

# First area of each act (Rogue Encampment, Lut Gholein, Kurast Docks, Pandemonium Fortress, Harrogath)
ACT_FIRST_LEVEL = (1, 40, 75, 103, 109)

# Pixels per map cell
MAP_SCALE = 1

# Game name (the waypoint one) of the areas whose internal name in the d2-mapgen.exe JSON is different
LEVEL_NAMES = {
    18: "Crypt",
    52: "Palace Cellar Level 1",
    66: "Tal Rasha's Tomb", 67: "Tal Rasha's Tomb", 68: "Tal Rasha's Tomb", 69: "Tal Rasha's Tomb",
    70: "Tal Rasha's Tomb", 71: "Tal Rasha's Tomb", 72: "Tal Rasha's Tomb",
    75: "Kurast Docks",
    84: "Arachnid Lair",
    108: "Chaos Sanctuary",
    111: "Frigid Highlands",
    113: "Crystalline Passage",
    114: "Frozen River",
    115: "Glacial Trail",
    116: "Drifter Cavern",
    117: "Frozen Tundra",
    118: "The Ancients' Way",
    119: "Icy Cellar",
    120: "Arreat Summit",
    121: "Nihlathak's Temple",
    123: "Halls of Pain",
    125: "Abaddon",
    126: "Pit of Acheron",
    127: "Infernal Pit",
    128: "Worldstone Keep Level 1",
    129: "Worldstone Keep Level 2",
    130: "Worldstone Keep Level 3",
    132: "Worldstone Chamber",
    133: "Matron's Den",
    134: "Forgotten Sands",
    135: "Furnace of Pain",
}

act_cache = {}  # (seed, difficulty, act) -> {levelNo: area JSON}
map_cache = {}  # (seed, difficulty, levelNo) -> (meta, bbox, edges)


def run_map_generator(seed, difficulty, levelNo):
    """Returns (meta, bbox, edges) or None. meta carries the offset, the size and the markers, in local coordinates."""
    cache_key = (seed, difficulty, levelNo)

    if cache_key in map_cache:
        print(f"Cache hit: {cache_key}")
        return map_cache[cache_key]

    act_levels = read_act(seed, difficulty, level_act(levelNo))
    level = act_levels.get(levelNo)
    if not level:
        report("mapgen", f"área {levelNo} não veio no ato {level_act(levelNo)} (seed {seed}, difficulty {difficulty})",
               f"áreas: {sorted(act_levels)}")
        return None
    report("mapgen", None)

    grid = decode_collision(level)
    edges = find_edges(grid)

    meta = {
        "offsetx": level["offset"]["x"],
        "offsety": level["offset"]["y"],
        "originalwidth": grid.shape[1],
        "originalheight": grid.shape[0],
        "serverScale": MAP_SCALE,
    }
    meta.update(read_markers(level, grid, act_levels))
    meta["route"] = build_route(level, grid, act_levels)

    bbox = rotated_bbox(edges, meta)
    if not bbox:
        print("⚠️ Mapa sem células andáveis")
        return None

    map_data = (meta, bbox, base64.b64encode(np.packbits(edges)).decode("ascii"))
    map_cache[cache_key] = map_data
    print(f"Cache saved: {cache_key}")
    return map_data


def level_act(levelNo):
    return sum(levelNo >= first for first in ACT_FIRST_LEVEL) - 1


def read_act(seed, difficulty, act):
    """Runs d2-mapgen.exe once per act and returns {levelNo: area JSON}."""
    cache_key = (seed, difficulty, act)
    if cache_key in act_cache:
        return act_cache[cache_key]

    cmd = [
        str(INNER_MAPGEN_EXE),
        "./game",
        "--seed", str(seed),
        "--difficulty", str(difficulty),
        "--act", str(act)
    ]

    print("Generating map...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=MAPGEN_DIR)
    except Exception as e:
        print(f"Error running map generator: {e}")
        return {}

    levels = {}
    for line in result.stdout.splitlines():
        if line.startswith('{"type":"map"'):
            level = json.loads(line)
            level["name"] = LEVEL_NAMES.get(level["id"], level["name"])
            levels[level["id"]] = level

    if not levels:
        print(f"Map generator error (returncode {result.returncode}):")
        print(result.stderr)
        return {}

    act_cache[cache_key] = levels
    return levels


def decode_collision(level):
    """RLE → uint8 grid (height, width), 1 = walkable."""
    grid = np.zeros((level["size"]["height"], level["size"]["width"]), np.uint8)

    for y, row in enumerate(level["map"]):
        x = 0
        for i, count in enumerate(row):
            if i % 2:
                grid[y, x:x + count] = 1
            x += count

    return grid


def find_edges(grid):
    """Walkable cells with some non-walkable 4-connected neighbor (outside the map counts as non-walkable)."""
    padded = np.pad(grid, 1)
    inner = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    return grid & (1 - inner)


def rotated_bbox(edges, meta):
    """(left, top, right, bottom) of the border after the rotation, in whole pixels, or None if there is no border."""
    ys, xs = np.nonzero(edges)
    if not len(xs):
        return None

    # Center of each cell; rotated, the cell takes ±COS45 around the center (×scale)
    px, py = world_to_map(xs + 0.5 + meta["offsetx"], ys + 0.5 + meta["offsety"], meta, (0, 0))
    half = COS45 * meta["serverScale"]
    return (
        math.floor(px.min() - half),
        math.floor(py.min() - half),
        math.ceil(px.max() + half),
        math.ceil(py.max() + half),
    )
