# FabioMH

Maphack for Diablo 2 Resurrected (`D2R.exe`, 64-bit). Run it from the root with `python main_win.py`: the map is drawn
on a transparent panel on top of the game (pyMeow raylib overlay, `window.py`).

**Requirement: every change is made only in the `main_win.py` architecture** (it, `window.py` and the `fabiomh/`
modules it uses). The old architecture (`python main.py`, the map in a Chrome window driven by Selenium +
`overlay.html` and `browser.py`) is no longer used: do not change or test those files, and there is no need to keep
compatibility with them. Wherever this document says to change `overlay.html` too, ignore that part.

The user writes in Portuguese, but the code comments and docstrings are in English (translated at the user's request),
as is the documentation (this file, `GLOSSARY.md`): write new comments in English. Runtime text (log messages, prints,
`scan_offsets.py` prompts, e.g. `==> Item no chão:`) is still in Portuguese.
Not a git repository yet, but it has a `.gitignore` ready for one. It must keep ignoring `dep/mapgen/game/`, which
holds the Diablo II game files that `d2-mapgen.exe` needs (copyrighted, ~2 GB), and `dep/mapgen/Save/` (~80 MB of
runtime data).

## Documentation

Every change made and confirmed through a prompt must be documented in this CLAUDE.md file, to make future decisions
easier.

## Where everything is

| Feature | File |
| --- | --- |
| User configuration (runes, super chest areas, `ROUTE_TARGETS` for the dashed path, tick, window, panel over the game `WIN_MAP_MODE` "panel"/"center" + `WIN_ISO_ZOOM`/`WIN_ISO_OFFSET`, hide hotkey `WIN_TOGGLE_KEYS`, hide while D2R is out of focus `WIN_HIDE_UNFOCUSED`, arrow keys that move the "center" mode map `WIN_PAN_KEYS`/`WIN_PAN_SPEED`, area name on exits `WIN_EXIT_NAMES`, kinds with an immunity ring `IMMUNITY_KINDS`, `DEBUG_LOG`) | `config.py` |
| Monitored drops (rules by `txt` + filters, among them `sockets` = exact number of sockets, + `enabled`, runes from `DROP_RUNES_FROM` up, banner duration, speech `DROP_SPEAK`/`DROP_SPEECH_VOICE`/`DROP_SPEECH_RATE`, sound `DROP_PLAY_SOUND`, `DROP_LOG_ALL`) | `drops.py` |
| One-off diagnosis of a game without a map (players, pointer chain, seed, map) | `diag.py` |
| Immunity diagnosis: scans the monsters' stat list and measures the time. Run it again if the rings disappear after a patch | `diag_stats.py` |
| Find the static offsets again after a patch (guided UI, unit table and roster by structure) | `scan_offsets.py` |
| Log that only prints when the reason changes (`report`) | `fabiomh/log.py` |
| Drop tracker sound (speaks the item name through SAPI, or a "ting" generated in memory, without blocking the loop) | `fabiomh/sound.py` |
| Main loop, map switching (browser) | `main.py` |
| Main loop, map switching (over the game; mapgen in a thread) | `main_win.py` |
| Paths (`dep/`, exes, DLL, overlay) | `fabiomh/paths.py` |
| pyMeow, static offsets, `read_struct` | `fabiomh/game/memory.py` |
| ctypes structs | `fabiomh/game/structs.py` |
| Unit hash table (`iter_units`) | `fabiomh/game/units.py` |
| Local player (difficulty, area, seed, position) and other players (green cross; party members far away come from the roster) | `fabiomh/game/player.py` |
| Seed decryption | `fabiomh/game/seed.py` |
| Monsters | `fabiomh/game/monsters.py` |
| Items on the ground (the single pass per tick) | `fabiomh/game/items.py` |
| Runes on the ground | `fabiomh/game/runes.py` |
| Corpses: remembers where the body was left, per area (only in `main_win.py`) | `fabiomh/game/cadaver.py` |
| Drop tracker (new item on the ground → rule → banner + marker + sound) | `fabiomh/game/drops.py` |
| Map generation (JSON from `d2-mapgen.exe`, RLE → border, bbox) + cache | `fabiomh/mapgen/generator.py` |
| Exits, waypoint, quest, super chests | `fabiomh/mapgen/objects.py` |
| Path to the next area (Dijkstra over the collision, once per map; player trace on every tick) | `fabiomh/mapgen/route.py` |
| World → pixel (45° rotation) | `fabiomh/mapgen/coords.py` |
| Selenium / window | `fabiomh/overlay/browser.py` |
| Points to draw + drawing order | `fabiomh/overlay/points.py` |
| Overlay over the game: map texture, unit drawing, Shift+Tab hotkey (`hotkey_down`), D2R in the foreground (`game_focused`) | `fabiomh/overlay/window.py` |
| Canvas drawing, animation | `fabiomh/overlay/overlay.html` |

## Flow (every `TICK_SECONDS`)

`monitor_player` → if `(seed, difficulty, levelNo)` changed: `load_map` (generates the act, border + bbox + markers +
`meta["route"]`, `show_map` → `updateMap` in JS) → items on the ground → `DropTracker.update` (even without a map) →
monsters + other players + runes + drops + player → `build_points` (world → pixel, discards what falls outside) +
`build_path` (path from the player to the `ROUTE_TARGETS` exit) → `show_points` → `updateUnits` in JS; the banners go
through `show_alerts` → `updateAlerts`. Nothing is written to disk.

## Rules

- The details of each area (offsets, IDs measured in game, formulas, decisions) are in the comment at the top of the
  module. Read the module before touching it.
- Map that does not appear: with `DEBUG_LOG`, `player:`, `units:`, `mapgen:`, `carregar:` and `mapa:` tell at which stage
  it stopped (only when the reason changes). In the game that failed, run `python diag.py`. A map that does not load is
  redone every 2 s.
  Already measured: the player table has 10 to 12 "ghosts" (`pAct=0`), recreated every game. The next one in a bucket's
  list is `UnitAny+0x158`; with the old 0x150, only the first unit of each bucket showed up (items, players and monsters
  disappeared by `dwUnitId % 128` collision). If even so the local player is not found in the table, plan C finds it
  through the items (ItemData → inventory → owner unit). The local test (`pInventory+0x70 != 0`) has also given 0 on the
  player itself (right after dying, with the corpse in front): corpses are discarded and plan B kicks in (the only
  living player). The log says which plan was used. See the top of `player.py`.
- Unit hash table: each bucket is a linked list through `UnitAny.pListNext`, at **0x158** (measured in all tables).
  The old 0x150 only showed the first unit of each bucket (82 of 187 items, 10 of 13 players), and the symptom was
  random: drops, runes or other units that sometimes were not marked. The case was found by scanning the process memory
  for the `UnitAny` signature and looking for what pointed to the hidden item. If a unit visible in the game does not
  appear in the table, repeat that before concluding it does not exist.
- The memory readers use `except Exception: continue`. A missing import (`NameError`) fails **silently**:
  if something is not drawn, check the imports first.
- The offsets belong to a specific D2R version and break on patches. To find them again: `python scan_offsets.py`
  inside a game, opening and closing the inventory/character screen when it asks. Signatures (AOB) do not work: they do
  not survive patches and only ~27% of `.text` is readable. The script uses only `.data`. See the top of the script.
- `act_cache`/`map_cache` live in memory: after changing the map logic, restart the script.
- The rotation exists in four places: `coords.world_to_map`, the `updateMap` matrix (overlay.html),
  `MapLayer` (window.py) and, flattened in the "center" mode of `main_win.py`, `coords.world_to_iso` +
  `build_iso_png`/`IsoMapLayer` (window.py). The unit styles (including the `square`, `diamond` and `cross` shapes, the
  green cross of other players) and the dashed path live in `overlay.html` and in `window.py`. Change everything
  together. Exception: the corpse marker only exists in `window.py`.
- Overlay out of focus: the pyMeow window is TOPMOST and stayed on top of everything with the game minimized. With
  `WIN_HIDE_UNFOCUSED`, `main_win.py` checks every frame (`window.game_focused`, < 1 µs: `GetForegroundWindow` +
  owner process == `proc["pid"]`) and, with D2R out of the foreground, draws an empty frame and sleeps 0.1 s. Unlike
  the hotkey, the tick keeps running (drop alert, corpses, map generation), and on return the map appears right
  away. Discarded: making D2R the owner of the overlay (`GWLP_HWNDPARENT`), because across processes Windows links the
  input queues of both (risk of stalling the game) and pyMeow creates the window TOPMOST.
- Arrow keys ("center" mode, requested by the user to see what was left off screen, e.g. a far-away waypoint):
  `WIN_PAN_KEYS` move the map in the pressed direction at `WIN_PAN_SPEED` px/s. `main_win.py` keeps `pan` (added to
  the screen center in the tick, which redoes points, path and the clipping of what leaves the screen) and, between
  ticks, draws shifted by `pan − tick_pan` (`IsoMapLayer.shift`), without rereading memory: the cost is 4
  `GetAsyncKeyState` per frame. When the player's position changes (walked or changed area), `pan` resets and the map
  goes back to the center. The keys are global and not consumed (the game also receives them); they only apply with
  D2R in focus. The "panel" mode ignores the arrows.
- Dashed path: for a new area, just add `area: destination area` to `config.ROUTE_TARGETS`. The destination is the exit
  with that id, or the border passage to that area. If it is not found, the `rota:` log says which area.
- Monitoring a new drop: with `DROP_LOG_ALL`, drop the item on the ground, read the `txt` in the log
  (`==> Item no chão:`) and add the rule to `DROP_RULES` (`drops.py`). Do not trust public ids: the rune ids are shifted
  in this version. 4-socket polearms: Colossus Voulge = 254 to Giant Thresher = 258, in sequence. Measured in game: the
  Colossus Voulge (254) and the Cryptic Axe (256): when the rules used 255 to 259, the Cryptic Axe alerted as
  "Thresher" and the Voulge did not alert. The `sockets` filter was confirmed on both.
- The fixed markers (`mapgen/objects.py`) must be **the same as the ones the old `d2-mapgenerator.exe` PNG drew**. It
  applied rules that the JSON does not provide ready-made, and each one that was missing became a bug:
  - **border exit:** neighboring outdoor areas, deduced from the position of the areas in the act (e.g. River of
    Flame → Chaos);
  - **right tomb:** the `isGoodExit` exit (Tal Rasha's tomb with the right symbol, in the Canyon of the Magi) is
    green, and the others are magenta. Exception requested by the user, which the old PNG did not do:
    `GOOD_EXIT_TARGETS` (Durance of Hate 2 → 3) also paints the exit to the next area green;
  - **bosses:** only the NPCs of their own area, in red (the ids repeat in other areas). Exception, because the old PNG
    got it wrong: Nihlathak (Halls of Vaught) is in the hall of the arm opposite npc 803 (`NIHLATHAK_HALLS`, see the
    top of `objects.py`). Another exception, requested by the user: Lilith (Matron's Den, 133) is marked at the npc
    802 closest to chest 397, or at the chest itself in seeds without 802 (`lilith_marker`; measured in game, txt 707,
    near the chest);
  - **quests:** a fixed list of ids, not `class == "quest"`.
  - **exit name** (requested by the user, the old PNG did not write it): exits are `(x, y, name)`, with the `name` of
    the destination area in the act JSON; `window.py` writes it above the diamond, in its color. The JSON `name` is
    the internal Levels.txt name (e.g. 114 = "Cellar of Pity"), so `read_act` (`generator.py`) replaces it with the
    game/waypoint name from `LEVEL_NAMES` (e.g. "Frozen River"). Wrong name on the map: add the area to that table.
    The text uses a Windows TTF (`LABEL_FONTS`, Verdana Bold, loaded in `open_window`) at 16 px, on a semi-transparent
    black rectangle, in the diamond's color lightened (`EXIT_LABEL_COLORS`): the default raylib font blurred and pure
    magenta vanished against the floor. Below ~16 px the TTF gets jagged (pyMeow loads it at 32 px and scales it down
    without filtering). The rune/drop names also use the TTF, but with an outline, no background.
  When touching these markers, compare with the old generator. It is still in `dep/mapgen/d2-mapgenerator.exe`:
  `generate --seed S --difficulty D --map L --rotate` writes the `.png` and the `.txt` (with `exits:`, `bosses:` and
  `quest_items:`) to `%TEMP%`.
- To test without the game, simulate the memory by replacing `fabiomh.game.memory.pm.r_bytes`. `run_map_generator`
  works on its own (it only needs `dep/mapgen`), and the overlay runs in headless Chrome (`show_map` +
  `save_screenshot`). `dep/mapgen/res.txt` is a sample of the `d2-mapgen.exe` output.

## History

- The Farm_LK (Lower Kurast super chests) and Farm_Summoner bots were removed at the user's request (never used, did not
  work well), together with their `FARM_LK_*`/`FARM_SUMMONER_*` settings, the `diag_belt.py`/`diag_chests.py`/
  `diag_shop.py` diagnostics and the data the mapgen kept only for them (`meta["grid"]`, `meta["exits_by_id"]`,
  `meta["npcs_by_id"]`, `Route.distances`).
- All Python comments and docstrings were translated from Portuguese to English (user request), except in the old
  architecture files (`main.py`, `browser.py`). Verified by comparing the AST of each file, without docstrings, against
  the original: no code changed. Log/print strings were left as they were.
