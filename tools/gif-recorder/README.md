# Line-1 demo GIF recorder

Automated capture of the three demo GIFs from [issue #115](https://github.com/d4shm1r/amagra/issues/115):
**divergence run → decision replay → offline proof**. Built for Route A — a
Playwright script drives the *real, local* app and records each shot; ffmpeg
converts the video to an optimized GIF.

> **It records reality, not a mock.** The script types into your actual Amagra
> and waits for your real models to answer. That's deliberate — the GIFs are the
> product's honesty claim, so they have to show real output. Nothing here can (or
> should) fake a result.

## Prerequisites (on your machine, where Amagra runs)

| Need | Why |
|---|---|
| **UI running** — `cd ui && npm run dev` → `http://localhost:3000` | the script navigates the live UI |
| **Backend running** — your usual `ai-start` → `http://localhost:8000` | real answers |
| **≥1 model configured** (Ollama or a provider key) | Consensus + Chat need something to answer |
| **Some decision history** (run any chat query once) | shot 2 replays an existing decision |
| **ffmpeg** | GIF conversion (already standard) |

## Run

```bash
cd tools/gif-recorder
npm install          # installs Playwright + the Chromium it drives
npm run record       # → out/shot1-divergence.webm, shot2-replay.webm
./to-gif.sh          # → out/*.gif  (960px @ 15fps; pass "800 12" for smaller)
```

Watch it work (non-headless): open `record.mjs`, set `chromium.launch({ headless: false })`.

### Config (env vars)

| Var | Default | |
|---|---|---|
| `AMAGRA_UI` | `http://localhost:3000` | UI origin |
| `DEMO_PROMPT` | *"Is it safe to store JWTs in localStorage?"* | the prompt used in shots 1 & 3 (pick one that makes models genuinely diverge) |
| `INCLUDE_OFFLINE` | *(off)* | set `1` to also record the automated shot 3 |
| `OUT_DIR` | `./out` | where videos/GIFs land |

## Shot 3 (offline) — record this one manually

Shots 1 and 2 automate cleanly. Shot 3's *point* is a viewer seeing the network
physically cut, and a browser script can't convincingly show the OS wifi icon go
dark (and `context.setOffline` would also kill localhost, breaking the app). So:

1. Start a chat with a **local** model selected.
2. Begin recording (Kooha / Peek / `wf-recorder` on Linux; QuickTime on macOS).
3. **Toggle wifi off** (or airplane mode) on camera — the menu-bar icon changing
   is the shot.
4. Send the prompt; it still answers. Stop recording.
5. Drop the clip into `out/` as `shot3-offline.webm` (or `.mp4`) and run `./to-gif.sh`.

`INCLUDE_OFFLINE=1` records a weaker automated substitute (aborts requests to
known cloud AI hosts, keeps localhost, then asks locally) — useful as a backup,
but the manual wifi-toggle version is the one to ship.

## After conversion

- Wire the three GIFs into the README hero and attach them to issue #115.
- Target < 5 MB each (GitHub inlines them; Reddit/HN like them small). If one is
  heavy: `./to-gif.sh 800 12`, or use the `gifski` path printed by the script.

## If a selector breaks

The script uses accessible names and text, which track the current UI:

- **Launcher** — the `Open menu` button + the search box (`AppLauncher.jsx`).
- **Tabs** — tile buttons named by their label (`Consensus`, `Decisions`).
- **Consensus** — placeholder *"Ask something worth verifying…"*, button
  *"Find consensus"*, verdict badge (`ConsensusTab.jsx`).
- **Replay** — clicking a row's `Brain→` text selects the decision (the click
  bubbles to the row `onClick`); then the `REPLAY` button (`DecisionTimeline.jsx`).

The single fragile spot is the decision row. If shot 2 can't find one, the
one-line hardening is a `data-testid="decision-row"` on `DecisionTimeline.jsx:658`
— then change the shot-2 selector to `page.getByTestId("decision-row").first()`.
