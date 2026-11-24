from fabiomh.mapgen.coords import local_to_map, world_to_iso, world_to_map

# Drawing order: what comes later is drawn on top
DRAW_ORDER = {"exit": -7, "goodexit": -6, "waypoint": -5, "quest": -4, "boss": -3, "superchest": -2, "summon": -1,
              "normal": 0, "minion": 1, "champion": 2, "unique": 3, "cadaver": 4, "otherplayer": 5, "player": 6, "rune": 7,
              "drop": 8}

# Meta list (mapgen/objects.py) → kind in overlay.html/window.py, already in drawing order
STATIC_KINDS = (("exits", "exit"), ("good_exits", "goodexit"), ("waypoints", "waypoint"), ("quests", "quest"),
                ("bosses", "boss"), ("super_chests", "superchest"))


def build_static_points(meta, bbox):
    """Fixed map points (exits, waypoint, quest, bosses, super chests): computed once per map."""
    static_points = []
    for key, kind in STATIC_KINDS:
        for x, y, *label in meta[key]:  # on exits, the label is the name of the destination area (objects.read_markers)
            px, py = local_to_map(x, y, meta, bbox)
            point = {"x": px, "y": py, "kind": kind}
            if label and label[0]:
                point["label"] = label[0]
            static_points.append(point)

    return static_points


def build_points(units, static_points, meta, bbox):
    """units: [(x, y, kind)] or [(x, y, kind, label)] in world coordinates. Discards what falls outside the image."""
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    points = list(static_points)

    for x, y, kind, *label in sorted(units, key=lambda unit: DRAW_ORDER[unit[2]]):
        px, py = world_to_map(x, y, meta, bbox)
        if 0 <= px <= width and 0 <= py <= height:
            point = {"x": px, "y": py, "kind": kind}
            if label:
                point["label"] = label[0]
            points.append(point)

    return points


def build_static_world_points(meta):
    """main_win's "center" mode: the fixed markers in world coordinates (x, y, kind[, label]), once per map."""
    return [(x + meta["offsetx"], y + meta["offsety"], kind, *[name for name in label if name])
            for key, kind in STATIC_KINDS for x, y, *label in meta[key]]


def build_iso_points(units, static_world, player, center, zoom, screen):
    """"center" mode: everything in screen pixels (coords.world_to_iso). Discards what falls off screen (screen = (w, h))."""
    points = []

    for x, y, kind, *label in static_world + sorted(units, key=lambda unit: DRAW_ORDER[unit[2]]):
        px, py = world_to_iso(x, y, player, center, zoom)
        if 0 <= px <= screen[0] and 0 <= py <= screen[1]:
            point = {"x": px, "y": py, "kind": kind}
            if label:
                point["label"] = label[0]
            points.append(point)

    return points


def trace_route(meta, player):
    """Path (mapgen/route.py) from the player to the next area, in world coordinates, or [] without a route."""
    route = meta.get("route")
    if not route:
        return []
    ox, oy = meta["offsetx"], meta["offsety"]
    return [(x + ox, y + oy) for x, y in route.trace(player[0] - ox, player[1] - oy)]


def build_path(meta, bbox, player):
    """Path in pixels of the rotated and cropped map: [[x, y], ...] (dashed polyline)."""
    return [list(world_to_map(x, y, meta, bbox)) for x, y in trace_route(meta, player)]


def build_iso_path(meta, player, center, zoom):
    """"center" mode: the path in screen pixels. Nothing is discarded: the line can leave the screen."""
    return [list(world_to_iso(x, y, player, center, zoom)) for x, y in trace_route(meta, player)]


def inside_map(x, y, meta, bbox):
    """Whether the world position falls inside the map image (the same test as build_points)."""
    px, py = world_to_map(x, y, meta, bbox)
    return 0 <= px <= bbox[2] - bbox[0] and 0 <= py <= bbox[3] - bbox[1]
