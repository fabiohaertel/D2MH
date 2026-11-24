"""World coordinate → pixel of the rotated and cropped map.

The meta (mapgen/generator.py) carries offsetx/offsety (world coordinate of the map origin), originalwidth/originalheight
(area size in cells) and serverScale. The map is rotated 45° **clockwise** around its center:
    px = c + (dx - dy)·cos45,  py = c + (dx + dy)·cos45,  c = (w + h)·cos45 / 2
and then the bbox is subtracted. overlay.html (updateMap) draws with this same math, as a canvas matrix:
any change here has to go there too.
Also works with numpy arrays instead of x/y (generator.rotated_bbox).
"""
COS45 = 0.7071067811865476


def world_to_map(x, y, meta, bbox):
    scale = meta["serverScale"]
    w = meta["originalwidth"] * scale
    h = meta["originalheight"] * scale

    dx = (x - meta["offsetx"]) * scale - w / 2
    dy = (y - meta["offsety"]) * scale - h / 2

    rotated_center = (w + h) * COS45 / 2
    px = rotated_center + (dx - dy) * COS45
    py = rotated_center + (dx + dy) * COS45

    return px - bbox[0], py - bbox[1]


def local_to_map(x, y, meta, bbox):
    """For mapgen local coordinates (objects, waypoints): adds the offset and converts."""
    return world_to_map(x + meta["offsetx"], y + meta["offsety"], meta, bbox)


def world_to_iso(x, y, player, center, zoom):
    """World → screen pixel in main_win's "center" mode (isometric, like D2's Tab automap).

    The same rotation as world_to_map, without the cos45 and flattened by half vertically (each cell becomes a 2:1
    diamond), with the player at the center of the screen. window.IsoMapLayer builds the texture with this same math.
    """
    dx = x - player[0]
    dy = y - player[1]
    return center[0] + (dx - dy) * zoom, center[1] + (dx + dy) * zoom / 2
