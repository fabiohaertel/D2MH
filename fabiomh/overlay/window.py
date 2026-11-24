"""Overlay over the game (main_win.py): pyMeow raylib window, transparent, always on top and click-through.

- `overlay_init("Full", ...)` covers the main monitor. In exclusive fullscreen D2R stays on top of everything:
  use borderless window.
- The map is a fixed panel at config.WIN_MAP_RECT, with the whole area, like in the browser.
- The map border becomes a texture (PNG in memory, no file), drawn with a 45° rotation by raylib.
  raylib rotates around the texture corner, clockwise (y down), which gives the same math as
  coords.world_to_map and overlay.html's updateMap: px = k·(u − v) + cos45·H, py = k·(u + v).
  Any change to the rotation has to go to all three places.
- "center" mode (config.WIN_MAP_MODE): IsoMapLayer, isometric like the Tab automap, with the player at the center of the
  screen (coords.world_to_iso). pyMeow only draws textures with rotation and uniform scale (no DrawTexturePro or
  matrix), so the texture is already generated flattened (build_iso_png, PIL affine transform, in the loader thread)
  and only changes position every tick. It is one more place with the rotation.
- The styles (UNIT_STYLES, rune, dashed path) are a copy of the ones in overlay.html: keep both the same. Exception: the
  "cadaver" only exists here (game/cadaver.py), because main.py does not use it.
- Everything here has to run in the overlay thread (the OpenGL context belongs to it).
- The hide hotkey (config.WIN_TOGGLE_KEYS) uses pm.key_pressed (GetAsyncKeyState, global): the window is
  click-through and never has focus, so raylib's keys do not arrive. The key is not consumed (the game also gets it).
- The overlay is TOPMOST and would stay on top of any window: game_focused (config.WIN_HIDE_UNFOCUSED) tells main_win.py
  when D2R is not in the foreground, so it draws nothing.
"""
import base64
import ctypes
import io
from ctypes import wintypes
import math
import os
import sys
import time

import numpy as np  # type: ignore
from PIL import Image  # type: ignore

from config import (WIN_EXIT_NAMES, WIN_FPS, WIN_ISO_OFFSET, WIN_ISO_ZOOM, WIN_MAP_ALPHA, WIN_MAP_RECT, WIN_PAN_KEYS,
                    WIN_TOGGLE_KEYS)
from fabiomh.mapgen.coords import COS45, world_to_iso

sys.path.append(r"c:/dev/pyMeow-1.73.42")
import pyMeow as pm  # type: ignore

MAP_EDGE_COLOR = (170, 170, 170)

# Maximum side of the isometric texture (safe GPU limit): above that it is generated smaller and scaled up when drawn
ISO_MAX_TEXTURE = 8192


def color(hex_color, alpha=255):
    return pm.new_color(int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16), alpha)


UNIT_STYLES = {
    "player":     {"color": color("#00ff00"), "radius": 5},
    "otherplayer": {"color": color("#00ff00"), "radius": 6, "shape": "cross"},  # other players: cross, the local one is a circle
    "unique":     {"color": color("#ffd700"), "radius": 5},
    "champion":   {"color": color("#3399ff"), "radius": 4},
    "minion":     {"color": color("#ff9900"), "radius": 3},
    "normal":     {"color": color("#ff3333"), "radius": 3},
    "summon":     {"color": color("#ffffff"), "radius": 3},  # necromancer and druid summons (monsters.py)
    "cadaver":    {"color": color("#c0c0c0"), "radius": 5, "shape": "square"},  # only here, see the top of the module
    "superchest": {"color": color("#00ffff"), "radius": 5, "shape": "square"},
    # Fixed markers, with the colors the d2-mapgenerator PNG used
    "exit":       {"color": color("#ff00ff"), "radius": 6, "shape": "diamond"},
    "goodexit":   {"color": color("#00ff00"), "radius": 8, "shape": "diamond"},  # the right tomb in the Canyon of the Magi
    "waypoint":   {"color": color("#ffff00"), "radius": 6, "shape": "diamond"},
    "quest":      {"color": color("#00ff00"), "radius": 5, "shape": "diamond"},
    "boss":       {"color": color("#ff0000"), "radius": 7},
}

OUTLINE = color("#000000")
WHITE = color("#ffffff")

# Immunity ring of the elites (game/monsters.py): the fill is still the monster kind's. With more than one
# immunity, the ring is split into equal arcs
IMMUNITY_COLORS = {
    "fire":     color("#ff4400"),
    "cold":     color("#66e0ff"),
    "light":    color("#ffff00"),
    "poison":   color("#44ff44"),
    "magic":    color("#e040ff"),
    "physical": color("#ffffff"),
}
IMMUNITY_RING_SEGMENTS = 24

# Rune: light core with a violet glow (do not use magenta: the exits are magenta diamonds)
RUNE_FILL = color("#f2e6ff")
RUNE_GLOW = "#b266ff"
RUNE_SIZE = 7
RUNE_FONT_SIZE = 14
PULSE_SECONDS = 1.0

# Name of the destination area above the exits (config.WIN_EXIT_NAMES), on a dark background, in the diamond's color
# lightened. The raylib default font (scaled-up 10 px bitmap) was blurry and pure magenta with a 1 px outline vanished
# on the gray floor: uses a Windows TTF (LABEL_FONTS, the first one that exists). pm.load_font loads the TTF at 32 px
# and raylib scales it down without filtering: below ~16 px the letters get jagged (measured in a test window)
EXIT_KINDS = ("exit", "goodexit")
EXIT_FONT_SIZE = 16
EXIT_LABEL_COLORS = {"exit": color("#ff80ff"), "goodexit": color("#80ff80")}
EXIT_LABEL_BACKGROUND = color("#000000", 170)
LABEL_FONTS = ("C:/Windows/Fonts/verdanab.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf")
LABEL_FONT_ID = 1
label_font = None  # LABEL_FONT_ID after open_window; None = raylib default font

# Monitored drop (game/drops.py): same drawing as the rune, in gold
DROP_FILL = color("#fff2b3")
DROP_GLOW = "#ffb000"

# Drop banner, in screen pixels: serves the "panel" and "center" modes. ASCII only: the raylib default font does not
# guarantee accents
ALERT_FONT_SIZE = 28
ALERT_TOP = 0.08  # fraction of the screen height
ALERT_PADDING = 12
ALERT_GAP = 8
ALERT_BACKGROUND = color("#000000", 210)
ALERT_TEXT = color("#ffd700")

# Path to the next area (mapgen/route.py), the same as overlay.html's: white dashes with a black outline
PATH_COLOR = color("#ffffff")
PATH_WIDTH = 2
PATH_DASH = (6, 4)  # dash, gap (pixels)


def open_window():
    global label_font
    pm.overlay_init("Full", WIN_FPS, "FabioMH", 5, -1, False)
    # The font belongs to the OpenGL context: only after overlay_init
    for path in LABEL_FONTS:
        if os.path.exists(path):
            try:
                pm.load_font(path, LABEL_FONT_ID)
                label_font = LABEL_FONT_ID
                break
            except Exception:
                continue


def close_window():
    pm.overlay_close()


_user32 = ctypes.WinDLL("user32")
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD


def game_focused(pid):
    """True if the foreground window belongs to process `pid` (config.WIN_HIDE_UNFOCUSED). Costs microseconds.

    Comparing by the owner process avoids finding and keeping the game's HWND. The overlay window is click-through and
    never gets focus, so it does not confuse the test. Discarded option: making D2R the owner (GWLP_HWNDPARENT) of the
    overlay. Across processes Windows links the input queues of both (a delay in the script could stall the game), and
    pyMeow creates the window TOPMOST.
    """
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return False
    owner = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    return owner.value == pid


def hotkey_down():
    """True while all the WIN_TOGGLE_KEYS keys are held (the caller detects the edge)."""
    return all(pm.key_pressed(vk) for vk in WIN_TOGGLE_KEYS)


def pan_direction():
    """(dx, dy) in -1/0/1 from the WIN_PAN_KEYS arrows (left, up, right, down). Global, like the hotkey."""
    left, up, right, down = (pm.key_pressed(vk) for vk in WIN_PAN_KEYS)
    return right - left, down - up


class MapLayer:
    """Map border texture + position in the panel. Create and unload in the overlay thread."""

    def __init__(self, meta, bbox, edges):
        width, height = meta["originalwidth"], meta["originalheight"]
        left, top, right, bottom = bbox
        rect_x, rect_y, rect_w, rect_h = WIN_MAP_RECT

        self.zoom = min(rect_w / (right - left), rect_h / (bottom - top))
        # Map corner centered in the panel (like overlay.html's flex)
        self.x = rect_x + (rect_w - (right - left) * self.zoom) / 2
        self.y = rect_y + (rect_h - (bottom - top) * self.zoom) / 2

        cells = np.unpackbits(np.frombuffer(base64.b64decode(edges), np.uint8))[:width * height]
        mask = cells.reshape(height, width).astype(bool)
        # Scaled down, raylib samples by point and the 1-cell border partly vanishes: thicken it to the right/bottom
        if self.zoom * meta["serverScale"] < 1:
            mask[:, 1:] |= mask[:, :-1]
            mask[1:, :] |= mask[:-1, :]

        rgba = np.zeros((height, width, 4), np.uint8)
        rgba[mask] = (*MAP_EDGE_COLOR, WIN_MAP_ALPHA)
        png = io.BytesIO()
        Image.fromarray(rgba, "RGBA").save(png, format="PNG", compress_level=1)
        self.texture = pm.load_texture_bytes(".png", png.getvalue())

        # Position of the texture's (0, 0) corner: the translation of the coords.world_to_map matrix, minus the bbox, × zoom
        self.texture_x = self.x + self.zoom * (COS45 * height * meta["serverScale"] - left)
        self.texture_y = self.y - self.zoom * top
        self.texture_scale = self.zoom * meta["serverScale"]

    def draw(self):
        pm.draw_texture(self.texture, self.texture_x, self.texture_y, WHITE, 45, self.texture_scale)

    def unload(self):
        pm.unload_texture(self.texture)


def iso_texture_zoom(meta):
    return min(WIN_ISO_ZOOM, ISO_MAX_TEXTURE / (meta["originalwidth"] + meta["originalheight"]))


def build_iso_png(meta, edges):
    """PNG (bytes) of the map border, already isometric. Can run outside the overlay thread (does not use raylib).

    The local corner (a, b) goes to u = (a − b + h)·z, v = (a + b)·z/2: the local corner (0, 0) lands at (h·z, 0).
    PIL receives the inverse (output pixel → cell).
    """
    width, height = meta["originalwidth"], meta["originalheight"]
    zoom = iso_texture_zoom(meta)

    cells = np.unpackbits(np.frombuffer(base64.b64decode(edges), np.uint8))[:width * height]
    mask = cells.reshape(height, width).astype(bool)
    # With less than ~2 px per cell the sampling skips cells and the border gets dotted: thicken it
    if zoom < 2:
        mask[:, 1:] |= mask[:, :-1]
        mask[1:, :] |= mask[:-1, :]

    size = (math.ceil((width + height) * zoom), math.ceil((width + height) * zoom / 2))
    inverse = (1 / (2 * zoom), 1 / zoom, -height / 2, -1 / (2 * zoom), 1 / zoom, height / 2)
    alpha = Image.fromarray(mask.astype(np.uint8) * WIN_MAP_ALPHA, "L").transform(
        size, Image.Transform.AFFINE, inverse, Image.Resampling.NEAREST)

    rgba = Image.merge("RGBA", [Image.new("L", size, c) for c in MAP_EDGE_COLOR] + [alpha])
    png = io.BytesIO()
    rgba.save(png, format="PNG", compress_level=1)
    return png.getvalue()


class IsoMapLayer:
    """"center" mode: isometric texture that follows the player. Create, move and unload in the overlay thread.

    The points (points.build_iso_points) already come in screen pixels, hence zoom = 1 in draw_points. x, y = arrow
    key offset since the last tick (shift): the drawing moves right away, without waiting for the tick to redo the
    points.
    """

    x = y = 0
    zoom = 1

    def __init__(self, meta, png):
        self.meta = meta
        self.texture = pm.load_texture_bytes(".png", png)
        self.texture_scale = WIN_ISO_ZOOM / iso_texture_zoom(meta)
        self.texture_x = self.texture_y = 0

    def set_player(self, player_pos, center):
        sx, sy = world_to_iso(self.meta["offsetx"], self.meta["offsety"], player_pos, center, WIN_ISO_ZOOM)
        self.texture_x = sx - self.meta["originalheight"] * WIN_ISO_ZOOM
        self.texture_y = sy

    def shift(self, dx, dy):
        self.x, self.y = dx, dy

    def draw(self):
        pm.draw_texture(self.texture, self.texture_x + self.x, self.texture_y + self.y, WHITE, 0, self.texture_scale)

    def unload(self):
        pm.unload_texture(self.texture)


def screen_center():
    return pm.get_screen_width() / 2 + WIN_ISO_OFFSET[0], pm.get_screen_height() / 2 + WIN_ISO_OFFSET[1]


def draw_points(layer, points):
    """points: [{x, y, kind, label?}] from build_points, in pixels of the rotated and cropped map."""
    phase = (time.monotonic() % PULSE_SECONDS) / PULSE_SECONDS

    for point in points:
        x = layer.x + point["x"] * layer.zoom
        y = layer.y + point["y"] * layer.zoom
        if point["kind"] == "rune":
            draw_rune(x, y, point.get("label"), phase)
        elif point["kind"] == "drop":
            draw_rune(x, y, point.get("label"), phase, DROP_FILL, DROP_GLOW)
        elif point["kind"] in EXIT_KINDS:
            style = UNIT_STYLES[point["kind"]]
            draw_unit(x, y, style)
            if WIN_EXIT_NAMES and point.get("label"):
                draw_label(x, y, style["radius"], point["label"], EXIT_FONT_SIZE, EXIT_LABEL_COLORS[point["kind"]],
                           EXIT_LABEL_BACKGROUND)
        else:
            style = UNIT_STYLES.get(point["kind"], UNIT_STYLES["normal"])
            # On monsters, the build_points "label" carries the immunities (monsters.read_immunities)
            if point.get("label"):
                draw_immunities(x, y, style["radius"], point["label"])
            draw_unit(x, y, style)


def draw_immunities(x, y, radius, immunities):
    """2 px ring around the monster, with a black outline. draw_unit, on top, covers the inner part.

    pyMeow's argument order, measured in a test window, is not raylib's: draw_ring(x, y, segments, inner, outer, start,
    end, color). In raylib's order, the angle becomes a radius and a 180° arc covers the map.
    """
    pm.draw_circle(x, y, radius + 4, OUTLINE)
    arc = 360 / len(immunities)
    for index, immunity in enumerate(immunities):
        pm.draw_ring(x, y, IMMUNITY_RING_SEGMENTS, radius + 1, radius + 3, index * arc, (index + 1) * arc,
                     IMMUNITY_COLORS[immunity])


def draw_path(layer, path):
    """path: [[x, y], ...] from points.build_path/build_iso_path. The dashes continue from one segment to the next."""
    dashes = []
    period = PATH_DASH[0] + PATH_DASH[1]
    walked = 0  # length already covered, for the dash phase

    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        x1, y1 = layer.x + x1 * layer.zoom, layer.y + y1 * layer.zoom
        x2, y2 = layer.x + x2 * layer.zoom, layer.y + y2 * layer.zoom
        length = math.hypot(x2 - x1, y2 - y1)
        if not length:
            continue
        # From the start of the segment, the first dash begins where the previous period stopped
        t = -(walked % period)
        while t < length:
            a, b = max(t, 0), min(t + PATH_DASH[0], length)
            if b > a:
                dashes.append((x1 + (x2 - x1) * a / length, y1 + (y2 - y1) * a / length,
                               x1 + (x2 - x1) * b / length, y1 + (y2 - y1) * b / length))
            t += period
        walked += length

    for dash in dashes:
        pm.draw_line(*dash, OUTLINE, PATH_WIDTH + 2)
    for dash in dashes:
        pm.draw_line(*dash, PATH_COLOR, PATH_WIDTH)


def draw_unit(x, y, style):
    radius = style["radius"]
    shape = style.get("shape")

    if shape == "square":
        pm.draw_rectangle(x - radius - 1, y - radius - 1, radius * 2 + 2, radius * 2 + 2, OUTLINE)
        pm.draw_rectangle(x - radius, y - radius, radius * 2, radius * 2, style["color"])
    elif shape == "cross":
        # Two rectangles (horizontal and vertical), with arms 2·t thick; the outline is 1 px larger
        t = max(1, round(radius * 0.3))
        pm.draw_rectangle(x - radius - 1, y - t - 1, radius * 2 + 2, t * 2 + 2, OUTLINE)
        pm.draw_rectangle(x - t - 1, y - radius - 1, t * 2 + 2, radius * 2 + 2, OUTLINE)
        pm.draw_rectangle(x - radius, y - t, radius * 2, t * 2, style["color"])
        pm.draw_rectangle(x - t, y - radius, t * 2, radius * 2, style["color"])
    elif shape == "diamond":
        pm.draw_poly(x, y, 4, radius + 1, 0, OUTLINE)
        pm.draw_poly(x, y, 4, radius, 0, style["color"])
    else:
        pm.draw_circle(x, y, radius + 1, OUTLINE)
        pm.draw_circle(x, y, radius, style["color"])


# Rune (and drop, with other colors): diamond with a pulsing halo, a "ping" ring that expands and fades, and the name on top
def draw_rune(x, y, label, phase, fill=RUNE_FILL, glow=RUNE_GLOW):
    pulse = (math.sin(phase * 2 * math.pi) + 1) / 2  # 0..1

    # Ping: ring that grows and disappears every cycle
    radius = RUNE_SIZE + phase * 18
    pm.draw_ring(x, y, radius - 1, radius + 1, 0, 360, 48, color(glow, int(255 * (1 - phase))))

    # Halo (instead of the canvas shadowBlur)
    pm.draw_circle(x, y, RUNE_SIZE + 2 + pulse * 5, color(glow, 70))

    pm.draw_poly(x, y, 4, RUNE_SIZE + 1.5, 0, color(glow))
    pm.draw_poly(x, y, 4, RUNE_SIZE, 0, fill)

    if label:
        draw_label(x, y, RUNE_SIZE, label, RUNE_FONT_SIZE, WHITE)


def draw_label(x, y, size, text, font_size, text_color, background=None):
    """Text centered above the point (size = marker radius): on a `background` rectangle or, without it, with a 1 px
    black outline. Uses the open_window TTF (label_font) when it loaded."""
    if label_font is None:
        width = pm.measure_text(text, font_size)
        draw = lambda tx, ty, c: pm.draw_text(text, tx, ty, font_size, c)  # noqa: E731
    else:
        width = pm.measure_font(label_font, text, font_size, 0)["x"]
        draw = lambda tx, ty, c: pm.draw_font(label_font, text, tx, ty, font_size, 0, c)  # noqa: E731

    text_x = round(x - width / 2)  # whole pixel: the font is drawn without filtering
    text_y = round(y - size - 4 - font_size)
    if background is not None:
        pm.draw_rectangle(text_x - 3, text_y - 1, width + 6, font_size + 2, background)
    else:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            draw(text_x + dx, text_y + dy, OUTLINE)
    draw(text_x, text_y, text_color)


def draw_alerts(alerts):
    """Drop banners (DropTracker.active_alerts), stacked at the top of the screen, with a blinking frame."""
    if not alerts:
        return

    phase = (time.monotonic() % PULSE_SECONDS) / PULSE_SECONDS
    frame = color(DROP_GLOW, int(255 * (math.sin(phase * 2 * math.pi) + 1) / 2))
    screen_width = pm.get_screen_width()
    y = pm.get_screen_height() * ALERT_TOP
    height = ALERT_FONT_SIZE + ALERT_PADDING * 2

    for text in alerts:
        width = pm.measure_text(text, ALERT_FONT_SIZE) + ALERT_PADDING * 2
        x = (screen_width - width) / 2
        pm.draw_rectangle(x - 3, y - 3, width + 6, height + 6, frame)
        pm.draw_rectangle(x, y, width, height, ALERT_BACKGROUND)
        pm.draw_text(text, x + ALERT_PADDING, y + ALERT_PADDING, ALERT_FONT_SIZE, ALERT_TEXT)
        y += height + ALERT_GAP
