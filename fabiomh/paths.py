from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEP_DIR = ROOT / "dep"
MAPGEN_DIR = DEP_DIR / "mapgen"                      # cwd of d2-mapgenerator.exe (uses ./game and ./mapgen)
MAPGENERATOR_EXE = MAPGEN_DIR / "d2-mapgenerator.exe"
INNER_MAPGEN_EXE = MAPGEN_DIR / "mapgen" / "d2-mapgen.exe"
RUSTDECRYPT_DLL = DEP_DIR / "rustdecrypt.dll"

OVERLAY_HTML = Path(__file__).resolve().parent / "overlay" / "overlay.html"
