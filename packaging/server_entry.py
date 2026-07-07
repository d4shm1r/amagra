"""Frozen entrypoint for the Amagra desktop sidecar.

PyInstaller freezes this into a single `amagra-server` binary (see
`packaging/amagra-server.spec`). The desktop shell (`desktop/main.js`) spawns it as

    amagra-server --host 127.0.0.1 --port 8000

so it must accept those flags and boot `api:app`, which serves both the JSON API
and the bundled `ui/build` on one port — the same contract as `packaging/AppRun`.

Also runnable directly for a dev smoke test:

    python packaging/server_entry.py --host 127.0.0.1 --port 8000
"""
import argparse
import os
import sys

# When frozen, PyInstaller unpacks the app to sys._MEIPASS and that dir holds
# api.py + the bundled packages; in dev it's the repo root (this file's parent's
# parent). Put it first on sys.path so `import api` resolves either way.
ROOT = getattr(sys, "_MEIPASS", None) or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
sys.path.insert(0, ROOT)


def main() -> None:
    # Windows consoles/pipes default to a legacy code page (cp1252) that can't
    # encode the emoji/unicode the app logs (e.g. api.py's "⚠" startup banner) —
    # a bare print() then raises UnicodeEncodeError and aborts uvicorn startup.
    # Force UTF-8 on the std streams so the frozen server logs identically on every
    # OS; errors="replace" is a belt so no stray glyph can ever kill the process.
    # Done before `import api` below so import-time banners are covered too.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(prog="amagra-server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    import uvicorn
    from api import app  # noqa: E402 — path set up above

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
