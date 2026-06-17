"""
infrastructure/paths.py — where Amagra reads/writes on each OS.

Two distinct notions:

  base_dir()        Where durable app data lives (databases, provider config).
                    Default = the project directory, so a checkout/dev run is
                    unchanged. Set AMAGRA_DATA_DIR to relocate everything — a
                    packaged desktop build points this at the OS user-data dir
                    so an app installed to /opt or Program Files can still write.

  user_data_dir()   The OS-appropriate per-user data location. The launcher/
                    installer uses this to choose what AMAGRA_DATA_DIR should be:
                      Linux    $XDG_DATA_HOME/amagra  (~/.local/share/amagra)
                      macOS    ~/Library/Application Support/Amagra
                      Windows  %APPDATA%\\Amagra

Keeping the default as the project dir means adopting this module is reversible
and migrates no data — same posture as AMAGRA_DB single-file mode.
"""

from __future__ import annotations

import os
import platform

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def base_dir() -> str:
    """Durable-data root: AMAGRA_DATA_DIR if set, else the project directory."""
    override = os.environ.get("AMAGRA_DATA_DIR", "").strip()
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    return _PROJECT_ROOT


def user_data_dir(app: str = "amagra") -> str:
    """OS-appropriate per-user data directory (created if missing)."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        target = os.path.join(base, app.capitalize())
    elif system == "Darwin":
        target = os.path.join(os.path.expanduser("~"), "Library", "Application Support", app.capitalize())
    else:  # Linux and other POSIX
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        target = os.path.join(base, app)
    os.makedirs(target, exist_ok=True)
    return target
