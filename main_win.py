# Same logic as main.py, but drawing over the game (fabiomh/overlay/window.py) instead of the browser.
# The loop is raylib's frame loop; memory is read every TICK_SECONDS and the map is generated in a thread,
# so the ~0.3 s of d2-mapgen.exe do not freeze the drawing.
# WIN_MAP_MODE: "panel" (whole area in a fixed panel) or "center" (isometric, following the player; the flattened
# texture is also generated in the loader thread).
# Without D2R.exe: the window opens anyway and the loop stays idle, looking for the process every ATTACH_RETRY_SECONDS.
# If the game closes with the script running, the read fails (readSeq, error 299): the process is released, the game
# state is cleared and the loop goes back to waiting.
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from config import TICK_SECONDS, WIN_HIDE_UNFOCUSED, WIN_ISO_ZOOM, WIN_MAP_MODE, WIN_PAN_SPEED
from fabiomh.game import memory
from fabiomh.game.cadaver import CadaverTracker
from fabiomh.game.drops import DropTracker
from fabiomh.game.items import read_ground_items
from fabiomh.game.monsters import TOWN_LEVELS, read_monsters
from fabiomh.game.player import monitor_player, read_other_players
from fabiomh.game.runes import rune_units
from fabiomh.log import report
from fabiomh.mapgen.generator import run_map_generator
from fabiomh.overlay.points import (build_iso_path, build_iso_points, build_path, build_points, build_static_points,
                                    build_static_world_points, inside_map)
from fabiomh.overlay.window import (IsoMapLayer, MapLayer, build_iso_png, close_window, draw_alerts, draw_path,
                                    draw_points, game_focused, hotkey_down, open_window, pan_direction, pm,
                                    screen_center)

# If the map does not load, try again after this interval (seconds), even if the state does not change
MAP_RETRY_SECONDS = 2

# With the overlay hidden (hotkey), only the hotkey is checked, at this interval (seconds)
HIDDEN_SLEEP_SECONDS = 0.1

CENTER = WIN_MAP_MODE == "center"

# D2R out of the foreground (config.WIN_HIDE_UNFOCUSED): memory keeps being read every tick, but nothing is drawn
# and the loop sleeps this long (s) per frame. Unlike the hotkey, which also stops the reading
UNFOCUSED_SLEEP_SECONDS = 0.1

# Arrow keys ("center" mode, config.WIN_PAN_KEYS): one frame's step uses at most this interval (s), so a late frame
# (or the return from hidden) does not cause a jump
PAN_MAX_STEP_SECONDS = 0.1

# Without D2R.exe open: looks for the process at this interval (s) and sleeps IDLE_SLEEP_SECONDS per frame, with the
# overlay window open and empty. Closing the game with the script running goes back to this state (see the loop's except)
ATTACH_RETRY_SECONDS = 2
IDLE_SLEEP_SECONDS = 0.1

# With a map loading, pause per frame (s) so the loader thread can run (see the end of the loop)
LOADER_YIELD_SECONDS = 0.005

# "center" mode: PNG of the isometric texture per (seed, difficulty, levelNo), like the generator's map_cache.
# Generating it takes up to ~0.1 s (the image has ~8× the pixels of the panel one); with the cache, going back to an
# area does not redo it. Only the loader thread touches it.
iso_cache = {}


def load_map(seed, difficulty, levelNo):
    """Runs in the loader thread: (meta, bbox, edges, "center" mode png or None) or None."""
    map_data = run_map_generator(seed, difficulty, levelNo)
    if not map_data:
        return None
    meta, bbox, edges = map_data
    if not CENTER:
        return meta, bbox, edges, None

    key = (seed, difficulty, levelNo)
    if key not in iso_cache:
        iso_cache[key] = build_iso_png(meta, edges)
    return meta, bbox, edges, iso_cache[key]


def make_map(meta, bbox, edges, png):
    """In the overlay thread: (meta, bbox, fixed points, layer) of the chosen mode."""
    if CENTER:
        return meta, bbox, build_static_world_points(meta), IsoMapLayer(meta, png)
    return meta, bbox, build_static_points(meta, bbox), MapLayer(meta, bbox, edges)


def main():
    proc = None
    window_open = False
    loader = ThreadPoolExecutor(max_workers=1)

    try:
        # The window opens right away, even without the game: D2R.exe is looked for in the loop (idle until it opens; see the top)
        open_window()
        window_open = True
        ui_address = unit_address = None
        attach_at = 0          # when to look for D2R.exe again
        waiting = False        # already said it is waiting for D2R.exe

        last_state = None      # (seed, difficulty, levelNo) of the last valid read
        pending = None         # future of the run_map_generator in progress
        current_map = None     # (meta, bbox, static_points, layer) of the map shown
        retry_at = 0           # when to retry a map that did not load
        points = []
        path = []              # dashed path to the next area (mapgen/route.py)
        next_tick = 0
        hidden = False         # hidden by the hotkey: does not read memory or draw
        toggle_was_down = False
        was_unfocused = False  # D2R out of the foreground in the previous frame
        # Arrow keys, "center" mode: pan = map offset (px); tick_pan = the pan the last tick built the points with
        # (the drawing moves pan − tick_pan until the next tick); pan_anchor = player position (walked: back to center)
        pan = [0.0, 0.0]
        tick_pan = (0.0, 0.0)
        pan_anchor = None
        last_frame = time.monotonic()
        tracker = DropTracker()
        cadavers = CadaverTracker()
        last_error = None      # last loop traceback printed

        while pm.overlay_loop():
            # Without D2R.exe (not open yet, or closed with the script running): idle, empty frame, looking for it
            # again every ATTACH_RETRY_SECONDS
            if proc is None:
                if time.monotonic() >= attach_at:
                    attach_at = time.monotonic() + ATTACH_RETRY_SECONDS
                    if memory.game_running():
                        try:
                            proc, ui_address, unit_address = memory.attach()
                            print("==> D2R.exe encontrado")
                            waiting = False
                            next_tick = 0
                        except Exception as e:
                            # It just opened and the module has not loaded yet, for example: try at the next interval
                            report("processo", f"D2R.exe aberto, mas não deu para ler a memória: {e}")
                    elif not waiting:
                        print("==> D2R.exe não está aberto; aguardando")
                        waiting = True
                if proc is None:
                    pm.begin_drawing()
                    pm.end_drawing()
                    time.sleep(IDLE_SLEEP_SECONDS)
                    continue


            # Hotkey: toggles only on the rising edge, so holding the key does not make the overlay blink
            down = hotkey_down()
            if down and not toggle_was_down:
                hidden = not hidden
                print("==> Overlay", "oculto" if hidden else "visível")
                if not hidden:
                    next_tick = 0
            toggle_was_down = down

            # Hidden: empty frame (clears the map from the screen) and wait. overlay_loop keeps being called
            # so the window is not flagged as "not responding". A map being generated is used on return.
            if hidden:
                pm.begin_drawing()
                pm.end_drawing()
                time.sleep(HIDDEN_SLEEP_SECONDS)
                continue

            # D2R out of the foreground (minimized, Alt+Tab): the tick runs normally, only the drawing stops (see the end of the loop)
            unfocused = WIN_HIDE_UNFOCUSED and not game_focused(proc["pid"])
            if unfocused != was_unfocused:
                print("==> Overlay", "oculto: D2R fora de foco" if unfocused else "visível: D2R em foco")
                if not unfocused:
                    next_tick = 0  # without waiting for the tick to update the points
                was_unfocused = unfocused

            # Arrow keys: only with the game in focus (the key is global). 4 GetAsyncKeyState per frame
            now = time.monotonic()
            if CENTER and not unfocused:
                dx, dy = pan_direction()
                if dx or dy:
                    step = WIN_PAN_SPEED * min(now - last_frame, PAN_MAX_STEP_SECONDS)
                    pan[0] += dx * step
                    pan[1] += dy * step
            last_frame = now

            try:
                # New map ready: the texture is created here, in the overlay thread
                if pending and pending.done():
                    # pending is cleared before result(): a load_map that raised an exception does not stay stuck forever
                    future, pending = pending, None
                    try:
                        map_data = future.result()
                    except Exception:
                        print("Error in load_map:\n" + traceback.format_exc())
                        map_data = None
                    if current_map:
                        current_map[3].unload()
                    current_map = None
                    if map_data:
                        current_map = make_map(*map_data)
                        report("carregar", None)
                    else:
                        report("carregar", f"mapa {last_state} (seed, difficulty, área) não carregou; "
                                           f"tentando de novo a cada {MAP_RETRY_SECONDS} s")
                        retry_at = time.monotonic() + MAP_RETRY_SECONDS

                if time.monotonic() >= next_tick:
                    next_tick = time.monotonic() + TICK_SECONDS
                    points = []
                    path = []
                    result = monitor_player(proc, unit_address, ui_address)

                    if result is None:
                        tracker.out_of_game()
                        cadavers.out_of_game(proc, unit_address, ui_address)
                    else:
                        difficulty, levelNo, seed, player_pos = result
                        state = (seed, difficulty, levelNo)

                        retry = current_map is None and time.monotonic() >= retry_at
                        if (state != last_state or retry) and not pending:
                            if state != last_state:
                                print("==> Difficulty:", difficulty)
                                print(f"==> Level ID: {levelNo}")
                                print(f"==> Seed: {seed}")

                            pending = loader.submit(load_map, seed, difficulty, levelNo)
                            last_state = state

                        # Outside the if below: the drop alert and the corpse recording do not depend on the map
                        ground_items = read_ground_items(proc, unit_address)
                        drop_units = tracker.update(proc, ground_items, seed)
                        cadaver_units = cadavers.update(proc, unit_address, seed, levelNo, player_pos)

                        # 👾 REAL-TIME UNITS (only after the current area's map is on the screen)
                        if current_map and not pending:
                            units = [(player_pos[0], player_pos[1], "player")]
                            if levelNo not in TOWN_LEVELS:
                                units += read_monsters(proc, unit_address)
                            units += read_other_players(proc, unit_address, levelNo)
                            units += rune_units(ground_items, tracker.txts) + drop_units + cadaver_units

                            meta, bbox, static_points, layer = current_map
                            if inside_map(*player_pos, meta, bbox):
                                report("mapa", None)
                            else:
                                report("mapa", f"player fora do mapa (área {levelNo}, seed {seed}): "
                                               "seed ou área errados?", f"pos={player_pos}, bbox={bbox}")
                            if CENTER:
                                # The player walked (or changed area): the map re-centers
                                if player_pos != pan_anchor:
                                    pan = [0.0, 0.0]
                                    pan_anchor = player_pos
                                tick_pan = tuple(pan)
                                # Texture and points move together, in the same tick
                                cx, cy = screen_center()
                                center = (cx + pan[0], cy + pan[1])
                                layer.set_player(player_pos, center)
                                points = build_iso_points(units, static_points, player_pos, center, WIN_ISO_ZOOM,
                                                          (pm.get_screen_width(), pm.get_screen_height()))
                                path = build_iso_path(meta, player_pos, center, WIN_ISO_ZOOM)
                            else:
                                points = build_points(units, static_points, meta, bbox)
                                path = build_path(meta, bbox, player_pos)

            except Exception as e:
                if not memory.game_running():
                    # D2R.exe closed (the error is readSeq/ReadProcessMemory 299): releases the process, clears what
                    # belonged to the game and goes back to waiting. A map being generated is discarded (the result is never read)
                    print("==> D2R.exe fechou; aguardando ele abrir de novo")
                    try:
                        memory.close(proc)
                    except Exception:
                        pass
                    proc = None
                    waiting = True
                    attach_at = time.monotonic() + ATTACH_RETRY_SECONDS
                    if current_map:
                        current_map[3].unload()
                    current_map = None
                    pending = None
                    last_state = None
                    retry_at = 0
                    points = []
                    path = []
                    tracker = DropTracker()
                    cadavers = CadaverTracker()
                    last_error = None
                    continue

                # The whole traceback, but only when the error changes (the loop retries every 2 s)
                message = traceback.format_exc()
                if message != last_error:
                    print(f"Error in loop: {e}\n{message}")
                    last_error = message
                points = []
                path = []
                next_tick = time.monotonic() + 2

            if unfocused:
                # Empty frame (like hidden by the hotkey); the sleep also yields the CPU to a loading map
                pm.begin_drawing()
                pm.end_drawing()
                time.sleep(UNFOCUSED_SLEEP_SECONDS)
                continue

            pm.begin_drawing()
            if current_map and points:
                if CENTER:
                    current_map[3].shift(pan[0] - tick_pan[0], pan[1] - tick_pan[1])
                current_map[3].draw()
                draw_path(current_map[3], path)
                draw_points(current_map[3], points)
            draw_alerts(tracker.active_alerts())
            pm.end_drawing()
            # Map loading: yields the CPU to the loader thread. pyMeow's drawing calls hold the GIL, and without this
            # load_map barely moved (measured: the Lower Kurast map with the chest routes only showed up when hiding
            # the overlay, whose loop sleeps)
            if pending:
                time.sleep(LOADER_YIELD_SECONDS)

    except KeyboardInterrupt:
        pass

    except Exception as e:
        print(f"Error: {e}")

    finally:
        loader.shutdown(wait=False)
        if window_open:
            close_window()
        if proc:
            memory.close(proc)


if __name__ == "__main__":
    main()
