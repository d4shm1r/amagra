# Deploying the marketing site (amagra.dev) — Cloudflare Pages

The **app** is self-hosted by users (`docker compose up` on their hardware) — you don't
host it. This doc is only about the **marketing landing page** at amagra.dev. It's a static
build, hosted free on Cloudflare Pages, auto-deployed on every push to `main`.

Total cost: **$0** (plus the domain, which you already own). No server, no card.

---

## One-time setup

### 1. Connect the repo in Cloudflare
1. Cloudflare dashboard → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**.
2. Pick `d4shm1r/amagra`, branch **`main`**.
3. Build settings:

   | Field | Value |
   |---|---|
   | Framework preset | **None** |
   | Root directory | **`ui`** |
   | Build command | **`npm run build`** |
   | Build output directory | **`build`** |

   (Node version is pinned to 20 via `ui/.nvmrc` — no env var needed.)
4. **Save and Deploy.** First build runs `vite build`; you get a `*.pages.dev` URL to verify.

### 2. Point the domain
1. In the new Pages project → **Custom domains** → **Set up a domain** → enter `amagra.dev`.
2. If the domain's DNS is already on Cloudflare, it wires the record automatically.
   Otherwise add the record Cloudflare shows you (a `CNAME` for the apex, which Cloudflare
   flattens) at your registrar. SSL is issued automatically — nothing to buy.

### 3. Verify
- `https://<project>.pages.dev/` shows the **landing page** (not the dashboard) — confirms the
  `_redirects` root rewrite works.
- `https://amagra.dev/social-preview.png` returns the image — confirms OG/Twitter cards render.
- Paste `https://amagra.dev` into the [OpenGraph debugger](https://www.opengraph.xyz/) to see
  the card before you post the launch.

---

## How it works after setup
Every `git push` to `main` → Cloudflare runs `npm run build` in `ui/` → publishes `ui/build/`.
No further action. Preview deploys are created automatically for PRs.

## Why `/` serves landing.html
`ui/public/_redirects` rewrites `/ → /landing.html` (HTTP 200). The Vite entry `index.html` is
the **dashboard** app, which only works against a local backend — it has no purpose on the
public domain. If you ever want the dashboard reachable publicly, it's still at `/index.html`.

## Files involved
- `ui/public/_redirects` — root rewrite (Cloudflare Pages reads this from the output root)
- `ui/.nvmrc` — pins Node 20 for the build
- `ui/public/social-preview.png` — OG/Twitter card image, served at the web root
- `ui/public/landing.html` — the marketing page itself
