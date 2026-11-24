# Janela do overlay: Chrome em modo --app, controlado pelo Selenium. O desenho fica no overlay.html
from selenium import webdriver  # type: ignore
from selenium.webdriver.chrome.options import Options  # type: ignore

from config import WINDOW_SIZE
from fabiomh.paths import OVERLAY_HTML


def open_overlay():
    options = Options()
    options.add_argument(f"--app=file:///{OVERLAY_HTML.as_posix()}")
    options.add_argument(f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")

    return webdriver.Chrome(options=options)


def show_map(driver, meta, bbox, edges):
    """edges: bits da borda em base64 (mapgen/generator.py). O JS rotaciona e corta com a mesma conta de coords.py."""
    driver.execute_script("updateMap(arguments[0])", {
        "width": meta["originalwidth"],
        "height": meta["originalheight"],
        "scale": meta["serverScale"],
        "bbox": list(bbox),
        "edges": edges,
    })


def show_points(driver, points, path=()):
    """points: [{x, y, kind, label?}] e path: [[x, y], ...] (caminho tracejado), em pixels do mapa já rotacionado e
    cortado."""
    driver.execute_script("updateUnits(arguments[0], arguments[1])", points, list(path))


def show_alerts(driver, alerts):
    """alerts: textos dos banners dos drops (DropTracker.active_alerts)."""
    driver.execute_script("updateAlerts(arguments[0])", alerts)
