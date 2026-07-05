# PyInstaller spec — freezes the FastAPI backend into a single `amagra-server`
# binary that the desktop shell spawns as its sidecar.
#
#   pip install pyinstaller
#   pyinstaller --clean --noconfirm packaging/amagra-server.spec
#
# Output: dist/amagra-server (dist/amagra-server.exe on Windows). Deps are light
# (numpy-only — no torch/faiss), so this is a small, fast freeze.
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

# SPECPATH is injected by PyInstaller = the dir holding this spec (packaging/);
# the repo root is its parent. Derive paths from it so the freeze doesn't depend
# on the current working directory.
ROOT = os.path.dirname(SPECPATH)
sys.path.insert(0, ROOT)

# The backend imports its routers/agents statically from api.py, so most of the
# tree is reachable by the module graph. But several packages use lazy, in-function
# imports (evaluation + training are pulled in by cognition/coherence.py,
# orchestration/coordinator.py, routes/*) so collect their submodules explicitly.
LOCAL_PKGS = [
    "agents", "cognition", "core", "decision", "memory", "memory_core",
    "models", "orchestration", "providers", "routes", "tools",
    "infrastructure", "evaluation", "training",
]
hiddenimports = []
for pkg in LOCAL_PKGS + ["uvicorn"]:
    hiddenimports += collect_submodules(pkg)

# Bundle the built UI so the single binary serves API + UI (api.py mounts
# ui/build off its own directory, which becomes sys._MEIPASS when frozen), plus
# the config dir so profile defaults resolve.
datas = []
ui_build = os.path.join(ROOT, "ui", "build")
if os.path.isdir(ui_build):
    datas.append((ui_build, "ui/build"))
config_dir = os.path.join(ROOT, "config")
if os.path.isdir(config_dir):
    datas.append((config_dir, "config"))

a = Analysis(
    [os.path.join(SPECPATH, "server_entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Dev/CLI-only trees the server never imports — keep them out to shrink the binary.
    excludes=["tkinter", "matplotlib", "pytest", "research"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="amagra-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
