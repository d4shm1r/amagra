# Packaging Amagra as a desktop app

Amagra runs as a single process: FastAPI serves the API **and** the built React UI
on one port (`api.py` mounts `ui/build` at `/`). The desktop build wraps that in an
AppImage so a user double-clicks one file — no Python, Node, or terminal needed.

## Linux — AppImage (primary target)

```bash
packaging/build-appimage.sh            # → dist/Amagra-x86_64.AppImage
packaging/build-appimage.sh --py 3.12  # pick the bundled Python version
```

What it does:
1. `vite build` the UI to static files.
2. Pull a **relocatable Python** (from the python-appimage project) as the base, so the
   interpreter, stdlib, and `libpython` ship inside the AppImage.
3. `pip install -r requirements.txt` into that bundle.
4. Overlay the app code + built UI, plus [`AppRun`](AppRun), [`amagra.desktop`](amagra.desktop), and the icon.
5. Repack with `appimagetool`.

**Prerequisites:** `npm`, `curl`, and FUSE (to run `appimagetool` and the resulting AppImage).
The script downloads the Python base and `appimagetool` itself.

**Run it:**
```bash
chmod +x dist/Amagra-x86_64.AppImage
./dist/Amagra-x86_64.AppImage
```
It serves on `http://127.0.0.1:8000`, opens your browser, and stores all data under
`~/.local/share/amagra` (so the read-only AppImage never tries to write to itself).

Env overrides: `AMAGRA_PORT`, `AMAGRA_DATA_DIR`, `AMAGRA_NO_BROWSER=1`.

### glibc / portability note
An AppImage built on Ubuntu 24.04 runs on 24.04 and newer, not necessarily older
distros (glibc is forward-compatible only). Ubuntu-first is the goal here. For the
widest reach, run the build inside an older `manylinux`/Ubuntu container.

### Ollama
Ollama is **not** bundled (it's large and self-updating). If a user wants fully-local
models, they install Ollama separately; Amagra's onboarding pulls the required models.
With the in-app **Settings → Model** tab a user can instead point Amagra at a hosted
API and skip Ollama entirely.

## Verifying without packaging (works today)

You don't need an AppImage to confirm single-process mode:
```bash
( cd ui && npx vite build )
python -m uvicorn api:app --port 8000      # then open http://127.0.0.1:8000
```

## macOS / Windows (later)

The single-process server is already cross-platform; only the *wrapper* differs.
Recommended path: a **Tauri** shell (tiny, uses the OS webview) with this Python
server shipped as a sidecar. `infrastructure/paths.py` already resolves the correct
per-OS data directory for all three platforms. The sandbox tool (`tools/sandbox.py`)
stays POSIX-only and remains opt-in (`AMAGRA_SANDBOX=1`).
