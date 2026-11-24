"""Fixed map markers (exits, waypoint, quest, bosses, super chests), from the d2-mapgen.exe JSON.

- Everything in the area's local coordinates: add offsetx/offsety before world_to_map (see coords.local_to_map).
- Exits: the `type == "exit"` objects only cover doors/stairs. The border passages between outdoor areas
  (e.g. River of Flame → Chaos Sanctum) are not in the JSON: d2-mapgenerator deduced them from the neighborhood of the
  act's areas. We do the same in `edge_exits`: touching neighboring area + walkable cells on the border → center of the
  longest stretch.
- "Right" exit: `isGoodExit: true` in the JSON. It only shows up in the Canyon of the Magi (46), on Tal Rasha's tomb
  with the right symbol. The old PNG painted that one green, and the others magenta.
  Beyond the old PNG (requested by the user): in GOOD_EXIT_TARGETS, the exit to the next area is also green. The `id`
  of an exit object is the destination area (Durance of Hate 2 = 101 has exits 100 and 102; Underground Passage 1
  = 10 has 4 (Stony Field), 5 (Dark Wood) and 14 (level 2, without an exit)).
- Super chest: d2-mapgen.exe puts class "chest-super" on ids 580 and 581, but that is a heuristic of its own (the old
  d2-mapgenerator.exe did not mark any in Lower Kurast, and in game both become ordinary chests, txt 181/183).
  Measured on 40 Lower Kurast seeds: 581 is a loose one, in ordinary huts (2 to 6 per map), and is not super. 580
  always comes in a trio with the same geometry, (x, y), (x+15, y-5), (x+48, y-45): it is the camp piece with the
  bonfire (in game, the bonfire, object 160 with a ring of torches 117, was at (x+44, y-6)). There are 1 or 2 trios per
  map, which matches the 2 or 4 known super chests (2 per bonfire). Only 580 is marked (SUPER_CHEST_IDS), and only in
  the areas of config.SUPER_CHEST_LEVELS, because these ids show up in ~20 other areas without being super.
- The sparkly chests (397/455) were removed on purpose.
- Bosses and quests: the same lists d2-mapgenerator used (`bosses:`/`quest_items:` from the old .txt), measured by
  running the old generator on the 136 areas and cross-checking with the JSON (it matches in all of them).
  - The NPC ids repeat with another meaning in other areas (e.g. 803 also shows up in the Barracks), so the NPCs are
    per (area, id).
  - Quest is a list of ids, not `class == "quest"`: the old generator ignored the other 4 Cairn stones, the
    Compelling Orb and the sewer lever, and marked objects without a class (Tome, Inifuss...).
- Nihlathak (Halls of Vaught, 124), exception to the old PNG: npc 803 in the JSON, which the old generator called
  "Nihlithak", is not him. Measured on 41 seeds: 803 is at one of 4 fixed points, one per arm of the cross, and only
  one arm has the big hall at the end (~1340 walkable cells, against ~820 for the others), always the one opposite
  803's. Measured in game: with 803 to the south (207, 393), Nihlathak (txt 526) was at (205, 20), in the north hall.
  The other three NIHLATHAK_HALLS positions are estimated from the hall's layout, not yet checked in game.
- Lilith (Matron's Den, 133, Uber Tristram), beyond the old PNG (requested by the user): the JSON has two npcs 802,
  one in the closed room with the chest (chest 397) and another at the end of the lower arm. Measured in game (seed
  1780961211, Hell): Lilith (txt 707, unique) was at (213, 129), with the chest's 802 at (220, 142) and the chest at
  (211, 140); the other 802 was at (256, 260). Only the 802 closest to chest 397 is marked (LILITH_*), because the
  layout changes with the seed. There are seeds without npc 802 (e.g. 12345), and then the chest itself is marked
  (Lilith was ~11 from it, closer than from the 802).
- Shrines and wells were in the .txt, but the old PNG did not draw them.
- Exit name (requested by the user, the old PNG did not write it): the exits come as (x, y, destination area name).
  The name is the area's `name` in the act JSON (`act_levels[id]`; on the border, the `neighbor`'s). Destination
  outside the act: "".
"""
import numpy as np  # type: ignore

from config import SUPER_CHEST_LEVELS
from fabiomh.log import report

SUPER_CHEST_IDS = {580}  # 581, which d2-mapgen also calls "chest-super", is not (see the top)

# Exits highlighted like the right tomb, area → destination area: Underground Passage 1 → Dark Wood,
# Durance of Hate 2 → 3
GOOD_EXIT_TARGETS = {10: 5, 101: 102}

# Bosses, area → NPC id: Radament, Maggot King, Summoner, Izual (Nihlathak is separate, see below)
BOSS_NPCS = {49: 744, 64: 749, 74: 250, 105: 256}

# Nihlathak: npc 803 only tells which arm is opposite his hall. Position of npc 803 → position of Nihlathak
NIHLATHAK_LEVEL = 124
NIHLATHAK_MARKER_NPC = 803
NIHLATHAK_HALLS = {
    (207, 393): (205, 20),   # 803 to the south → north hall (measured in game)
    (206, 32): (205, 400),   # 803 to the north → south hall (estimated)
    (388, 216): (20, 210),   # 803 to the east → west hall (estimated)
    (30, 208): (400, 210),   # 803 to the west → east hall (estimated)
}

# Lilith: of the Matron's Den npcs 802, only the one closest to chest 397 (see the top)
LILITH_LEVEL = 133
LILITH_MARKER_NPC = 802
LILITH_CHEST = 397

# Quest NPCs, area → id: Anya
QUEST_NPCS = {114: 793}

# Quest objects: StoneLambda (Cairn), Inifuss, Tome (Summoner), gidbinn altar, Hellforge, Seals (392–396),
# LamTome, orifice, taintedsunaltar, cagedwussie1 (Qual-Kehk's prisoners)
QUEST_OBJECT_IDS = {21, 30, 357, 251, 376, 392, 393, 394, 395, 396, 193, 152, 149, 473}


def read_markers(level, grid, act_levels):
    """Returns {"exits", "good_exits", "waypoints", "quests", "bosses", "super_chests"}: lists of local (x, y).

    On the exits ("exits", "good_exits"), (x, y, destination area name).
    """
    markers = {"exits": [], "good_exits": [], "waypoints": [], "quests": [], "bosses": [], "super_chests": []}
    exit_ids = set()

    for obj in level["objects"]:
        point = (obj["x"], obj["y"])
        if obj["type"] == "exit":
            good = obj.get("isGoodExit") or GOOD_EXIT_TARGETS.get(level["id"]) == obj["id"]
            name = act_levels.get(obj["id"], {}).get("name", "")
            markers["good_exits" if good else "exits"].append((*point, name))
            exit_ids.add(obj["id"])
        elif obj["type"] == "npc":
            if BOSS_NPCS.get(level["id"]) == obj["id"]:
                markers["bosses"].append(point)
            elif level["id"] == NIHLATHAK_LEVEL and obj["id"] == NIHLATHAK_MARKER_NPC:
                if point in NIHLATHAK_HALLS:
                    markers["bosses"].append(NIHLATHAK_HALLS[point])
                else:
                    report("mapgen", f"npc {obj['id']} numa posição nova {point}: Nihlathak sem marcador")
            elif QUEST_NPCS.get(level["id"]) == obj["id"]:
                markers["quests"].append(point)
        elif obj["type"] == "object":
            cls = obj.get("class")
            if cls == "waypoint":
                markers["waypoints"].append(point)
            elif obj["id"] in QUEST_OBJECT_IDS:
                markers["quests"].append(point)
            elif obj["id"] in SUPER_CHEST_IDS and level["id"] in SUPER_CHEST_LEVELS:
                markers["super_chests"].append(point)

    if level["id"] == LILITH_LEVEL:
        lilith = lilith_marker(level)
        if lilith:
            markers["bosses"].append(lilith)

    for neighbor in act_levels.values():
        if neighbor["id"] not in exit_ids:
            markers["exits"] += [(x, y, neighbor.get("name", "")) for x, y in edge_exits(level, grid, neighbor)]

    return markers


def lilith_marker(level):
    """Local (x, y) of the npc 802 closest to chest 397 in Matron's Den (without 802, the chest), or None without the
    chest."""
    npcs = [(o["x"], o["y"]) for o in level["objects"] if o["type"] == "npc" and o["id"] == LILITH_MARKER_NPC]
    chests = [(o["x"], o["y"]) for o in level["objects"] if o["type"] == "object" and o["id"] == LILITH_CHEST]
    if not chests:
        report("mapgen", f"Matron's Den sem o baú {LILITH_CHEST}: Lilith sem marcador")
        return None
    cx, cy = chests[0]
    if not npcs:
        return cx, cy
    return min(npcs, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)


def edge_exits(level, grid, neighbor):
    """Border passage to `neighbor`: local [(x, y)] in the middle of the longest walkable stretch of the shared border, or []."""
    x0, y0 = level["offset"]["x"], level["offset"]["y"]
    w, h = level["size"]["width"], level["size"]["height"]
    nx0, ny0 = neighbor["offset"]["x"], neighbor["offset"]["y"]
    nw, nh = neighbor["size"]["width"], neighbor["size"]["height"]

    # Shared border: local row (horizontal) or column (vertical) of the area, and the overlapping stretch
    if ny0 + nh == y0 or ny0 == y0 + h:
        a, b = max(x0, nx0) - x0, min(x0 + w, nx0 + nw) - x0
        cells = grid[0 if ny0 + nh == y0 else h - 1, max(a, 0):b]
        horizontal = True
    elif nx0 + nw == x0 or nx0 == x0 + w:
        a, b = max(y0, ny0) - y0, min(y0 + h, ny0 + nh) - y0
        cells = grid[max(a, 0):b, 0 if nx0 + nw == x0 else w - 1]
        horizontal = False
    else:
        return []

    if b <= a or not cells.any():
        return []

    # Longest continuous stretch of walkable cells
    padded = np.concatenate(([0], cells, [0]))
    changes = np.flatnonzero(np.diff(padded))
    starts, ends = changes[::2], changes[1::2]
    longest = np.argmax(ends - starts)
    middle = max(a, 0) + (starts[longest] + ends[longest]) // 2

    if horizontal:
        return [(int(middle), 0 if ny0 + nh == y0 else h - 1)]
    return [(0 if nx0 + nw == x0 else w - 1, int(middle))]
