# ⚙️ User settings

# Runes shown on the map when they are on the ground (edit freely)
RUNES_TO_SHOW = ["El", "Eld", "Tir", "Nef", "Eth", "Ith", "Tal", "Ral", "Ort", "Thul", "Amn", "Sol", "Shael", "Dol",
                 "Hel", "Io", "Lum", "Ko", "Fal", "Lem", "Pul", "Um", "Mal", "Ist", "Gul", "Vex", "Ohm", "Lo",
                 "Sur", "Ber", "Jah", "Cham", "Zod"]

# Areas where the super chests are marked
SUPER_CHEST_LEVELS = {79}  # Lower Kurast (80 = Kurast Bazaar, 81 = Upper Kurast, if you want to include them)

# Dashed path from the player to the next area: area → destination area (the exit with that id, or the border passage
# to it). Area ids: the "==> Level ID" printed by the script when entering the area.
ROUTE_TARGETS = {
    #4: 10,  # Stony Field → Underground Passage Level 1
}

# Monster kinds with an immunity ring on the map (unique, champion, minion, normal). set() turns it off
IMMUNITY_KINDS = {"unique", "champion", "minion"}

# Interval between memory reads (seconds)
TICK_SECONDS = 0.15

# Prints why the map does not appear (player not found, map not generated, player outside the map), only when the
# reason changes
DEBUG_LOG = True

# Overlay window size (main.py, browser)
WINDOW_SIZE = (900, 900)

# Mode of the map over the game (main_win.py): "panel" (the whole area in WIN_MAP_RECT) or "center" (isometric,
# following the player at the center of the screen, like the Tab automap)
WIN_MAP_MODE = "center"

# "center" mode: screen pixels per world unit (calibrate with the game's automap) and center adjustment (x, y) in pixels
WIN_ISO_ZOOM = 2.0
WIN_ISO_OFFSET = (0, 0)

# "panel" mode: map panel in screen pixels (x, y, width, height)
WIN_MAP_RECT = (1280, 40, 600, 600)  # top right corner of a 1920 px monitor

# Opacity of the map walls in the overlay over the game (0 = invisible, 255 = solid)
WIN_MAP_ALPHA = 200

# Frames per second of the overlay over the game
WIN_FPS = 60

# Name of the destination area above each exit (magenta and green diamonds) in the overlay over the game
WIN_EXIT_NAMES = True

# Key to hide/show the overlay over the game (Windows virtual-key codes): Shift (0x10) + Tab (0x09)
WIN_TOGGLE_KEYS = (0x10, 0x09)

# Hides the overlay on its own when the foreground window is not D2R's (game minimized, Alt+Tab, another window).
# Only the drawing stops: memory keeps being read (drop alert, corpses), and the map comes back right away
WIN_HIDE_UNFOCUSED = True

# "center" mode: the arrow keys move the map in the pressed direction (to see what was left off screen). It re-centers
# on its own when the player walks or changes area. Keys (virtual-key codes): left, up, right, down
WIN_PAN_KEYS = (0x25, 0x26, 0x27, 0x28)
WIN_PAN_SPEED = 700  # pixels per second with the arrow key held
