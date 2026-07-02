# Deploying the marketing site (amagra.dev) — Cloudflare Workers (Static Assets)

The **app** is self-hosted by users (`docker compose up` on their hardware) — you don't
host it. This doc is only about the **marketing landing page** at amagra.dev: a static
build, hosted free on Cloudflare Workers Static Assets, auto-deployed on every push to `main`.

Total cost: **$0** (plus the domain, which you already own). No server, no card.

---

## How the repo is wired (so the connected Worker just works)

Cloudflare's Git connection created a **Worker** (deploy command `npx wrangler deploy`).
Two repo files make that succeed with **no dashboard changes**:

- **`package.json`** (root) — gives the dashboard's `npm run build` (run at root `/`)
  something to do: it installs + builds the Vite app in `ui/`, then copies
  `ui/build/landing.html → ui/build/index.html` so `/` serves the **marketing page**
  (the Vite `index.html` is the local dashboard, not wanted publicly).
- **`wrangler.toml`** — assets-only config so `npx wrangler deploy` uploads `ui/build/`
  as a static site. `name = "amagra"` **must match your Worker's name** — change it if
  your Worker is named differently.

Your current dashboard settings already match this:

| Field | Value |
|---|---|
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy` |
| Root directory | `/` |
| Production branch | `main` |

So: **merge this, then hit "Retry build" (or push to `main`) and it should go green.**

---

## After it builds
1. Cloudflare gives you a `*.workers.dev` URL. Open it — you should see the **landing page**
   (not the dashboard), and `/<that url>/social-preview.png` should return the image.
2. **Custom domain:** Worker → **Settings → Domains & Routes → Add → Custom domain** →
   `amagra.dev`. If the domain's DNS is on Cloudflare it wires automatically; SSL is free
   and automatic.
3. Paste `https://amagra.dev` into the [OpenGraph debugger](https://www.opengraph.xyz/) to
   confirm the social card before you post the launch.

Every `git push` to `main` then auto-builds and deploys. Nothing else to wire.

---

## Troubleshooting
- **Build still fails on `npm run build`** — confirm Root directory is `/` (not `ui`); the
  root `package.json` is what makes that command work.
- **Deploy fails: "worker name doesn't match"** — set `name` in `wrangler.toml` to your
  Worker's exact name.
- **`/` shows the dashboard, not the landing page** — the `cp landing.html → index.html`
  step didn't run; check the build log shows it after the Vite build.

## Files involved
- `package.json` (root) — build entrypoint (`npm run build`)
- `wrangler.toml` — Workers Static Assets config (serves `ui/build/`)
- `ui/.nvmrc` — pins Node 20 for the build
- `ui/public/social-preview.png` — OG/Twitter card image, served at the web root
- `ui/public/landing.html` — the marketing page (copied to `index.html` at build time)

> Prefer Cloudflare **Pages** instead? Delete the Worker, create a Pages project (root dir
> `ui`, build `npm run build`, output `build`), and re-add a `ui/public/_redirects` with
> `/ /landing.html 200`. Both work; this repo is set up for the Worker you already created.
