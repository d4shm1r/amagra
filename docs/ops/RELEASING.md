# Releasing Amagra

A release is cut by pushing a `v*` tag. Three workflows fan out from that tag:

| Workflow | Produces | Runners |
|---|---|---|
| `release-appimage.yml` | Linux `Amagra-x86_64.AppImage` (python-appimage) | ubuntu-22.04 |
| `release-desktop.yml` | macOS `.dmg` (arm64 + x64), Windows `AMAGRA-Setup.exe` (Electron + frozen sidecar) | macos-14, macos-13, windows-latest |
| `publish.yml` | (existing publish steps) | — |

Linux ships the lightweight AppImage; macOS/Windows ship the Electron app with the
FastAPI backend frozen in as a PyInstaller sidecar (`packaging/amagra-server.spec`).

## Cutting a release

1. **Bump the version in all four sources — they must match** (drift ships a build
   that reports the wrong version):
   - `infrastructure/version.py` → `__version__` (backend / FastAPI / `/health`)
   - `ui/src/config/constants.js` → `VERSION` (in-app UI marker)
   - `ui/package.json` → `version`
   - `desktop/package.json` → `version`

   Then regenerate the social card so its badge matches:
   `python tools/gen_social_card.py` (reads `version.py`). Optionally refresh the
   README release badge and the landing hero badge (`ui/public/landing.html`).
2. Update the changelog / release notes.
3. Commit, then tag and push:
   ```bash
   git tag v1.6.5
   git push origin v1.6.5
   ```
4. The three workflows attach their installers to the GitHub Release for that tag.
   `workflow_dispatch` runs the desktop build without a tag and uploads the
   installers as CI artifacts only (handy for a dry run).

## Known caveat — unsigned desktop builds

The macOS/Windows installers are **not code-signed** (no certs in CI). On first
launch users hit a warning:

- **macOS** — "AMAGRA can't be opened because Apple cannot check it." Right-click
  the app → *Open*, or `xattr -dr com.apple.quarantine /Applications/AMAGRA.app`.
- **Windows** — SmartScreen "Windows protected your PC." Click *More info* → *Run anyway*.

See [TROUBLESHOOTING_WINDOWS.md](TROUBLESHOOTING_WINDOWS.md) for the full
install/first-launch walkthrough and how to recover from startup failures.

Removing this requires an Apple Developer ID (notarization) and an Authenticode
cert. When those exist, add them as repo secrets and set `CSC_LINK`/`CSC_KEY_PASSWORD`
(and `APPLE_ID`/`APPLE_APP_SPECIFIC_PASSWORD`/`APPLE_TEAM_ID` for notarization) in
`release-desktop.yml`, and drop `CSC_IDENTITY_AUTO_DISCOVERY=false`.

## Data location

A packaged app installs read-only, so the backend writes to the OS per-user data
dir (set via `AMAGRA_DATA_DIR` by `desktop/main.js`):

- macOS `~/Library/Application Support/AMAGRA`
- Windows `%APPDATA%\AMAGRA`
- Linux (AppImage) `~/.local/share/amagra`
