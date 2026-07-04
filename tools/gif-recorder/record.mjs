// ─────────────────────────────────────────────────────────────────────────────
// Line-1 demo GIF recorder  (issue #115)
//
// Drives a REAL, LOCAL Amagra instance and records the three demo shots as video.
// It cannot fabricate output — it types into the actual app and waits for your
// real models to answer. That honesty is the whole point of the GIFs.
//
// Prereqs (all on YOUR machine, where the product actually runs):
//   • UI running:      cd ui && npm run dev        (→ http://localhost:3000)
//   • Backend running: ai-start / your usual boot  (→ http://localhost:8000)
//   • At least one model configured (Ollama or a provider key) so answers return
//   • Some decision history exists (any prior chat query) for shot 2
//
// Run:  cd tools/gif-recorder && npm install && npm run record
// Out:  ./out/shot1-divergence.webm, shot2-replay.webm, (shot3-offline.webm)
// Then: ./to-gif.sh   (converts every .webm in ./out to an optimized .gif)
//
// Override anything via env: AMAGRA_UI, AMAGRA_API, DEMO_PROMPT, INCLUDE_OFFLINE=1
// ─────────────────────────────────────────────────────────────────────────────
import { chromium } from "playwright";
import { mkdirSync, readdirSync, renameSync, statSync } from "node:fs";
import { join } from "node:path";

const UI  = process.env.AMAGRA_UI  || "http://localhost:3000";
const OUT = process.env.OUT_DIR    || join(process.cwd(), "out");
const PROMPT = process.env.DEMO_PROMPT || "Is it safe to store JWTs in localStorage?";
const VW = 1280, VH = 800;

mkdirSync(OUT, { recursive: true });

// Pre-seed localStorage so the first-run wizard never appears and the full
// (advanced) nav is available — the Decisions tab lives in the advanced surface.
const seedStorage = () => {
  try {
    localStorage.setItem("onboarding_done_v1", "1");
    localStorage.setItem("ui_mode_v1", "advanced");
  } catch {}
};

async function newRecordedContext(browser, name) {
  const dir = join(OUT, "_raw", name);
  mkdirSync(dir, { recursive: true });
  const ctx = await browser.newContext({
    viewport: { width: VW, height: VH },
    deviceScaleFactor: 2,                 // crisp text; downscaled at GIF time
    recordVideo: { dir, size: { width: VW, height: VH } },
  });
  await ctx.addInitScript(seedStorage);
  return { ctx, dir };
}

// Playwright writes the video only after the page+context close; then we rename
// the newest .webm in the per-shot dir to a stable name.
async function saveVideo(ctx, dir, outName) {
  for (const p of ctx.pages()) await p.close();
  await ctx.close();
  const newest = readdirSync(dir)
    .filter(f => f.endsWith(".webm"))
    .map(f => ({ f, t: statSync(join(dir, f)).mtimeMs }))
    .sort((a, b) => b.t - a.t)[0];
  if (!newest) throw new Error(`no video captured in ${dir}`);
  renameSync(join(dir, newest.f), join(OUT, outName));
  console.log(`   ✔ ${outName}`);
}

// Open the ☰ launcher, search, click the matching app tile. Tiles are buttons
// whose accessible name is the tab label (AppLauncher.jsx Tile → aria-label).
async function goToTab(page, label) {
  await page.getByRole("button", { name: "Open menu" }).click();
  const search = page.getByLabel(/search apps/i);
  await search.click();
  await search.fill(label);
  await page.getByRole("button", { name: label, exact: true }).first().click();
  await page.waitForTimeout(800);
}

async function type(page, locator, text) {
  await locator.click();
  await locator.fill("");
  await locator.pressSequentially(text, { delay: 42 });   // human-ish cadence
}

// ── Shot 1: divergence run (the hook) ────────────────────────────────────────
async function shotDivergence(browser) {
  console.log("▶ Shot 1 — divergence run");
  const { ctx, dir } = await newRecordedContext(browser, "divergence");
  const page = await ctx.newPage();
  await page.goto(UI, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);

  await goToTab(page, "Consensus");
  await type(page, page.getByPlaceholder(/ask something worth verifying/i), PROMPT);
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: /find consensus/i }).click();

  // Wait for the RESULT, not the page header. "Consensus" alone also matches the
  // <h1> title (always present), so we key off the candidates strip — "N models
  // consulted" only renders once real answers come back.
  await page
    .getByText(/\d+\s+models?\s+consulted/i)
    .first()
    .waitFor({ timeout: 120_000 });
  await page.waitForTimeout(3000);          // let the agreement gauge animate + settle

  await saveVideo(ctx, dir, "shot1-divergence.webm");
}

// Surface JS/console errors and dump a screenshot when a shot breaks, so a
// white-screen or a failing endpoint tells us exactly what went wrong.
function watchErrors(page, tag) {
  page.on("pageerror", e => console.error(`   [${tag}] page error: ${e.message}`));
  page.on("console", m => { if (m.type() === "error") console.error(`   [${tag}] console: ${m.text()}`); });
  page.on("response", r => {
    if (r.url().includes("/replay/") ) console.error(`   [${tag}] ${r.request().method()} ${r.url()} → ${r.status()}`);
  });
}
async function debugShot(page, name) {
  const d = join(OUT, "_debug"); mkdirSync(d, { recursive: true });
  try { await page.screenshot({ path: join(d, `${name}.png`), fullPage: true });
        console.error(`   ↳ debug screenshot: out/_debug/${name}.png`); } catch {}
}

// ── Shot 2: decision replay (the differentiator) ─────────────────────────────
async function shotReplay(browser) {
  console.log("▶ Shot 2 — decision replay");
  const { ctx, dir } = await newRecordedContext(browser, "replay");
  const page = await ctx.newPage();
  watchErrors(page, "replay");
  try {
  await page.goto(UI, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);

  await goToTab(page, "Decisions");

  // Rows are clickable divs; clicking any text inside them ("Brain→") bubbles to
  // the row's onClick, so we don't need a brittle row selector.
  const firstRow = page.getByText("Brain→").first();
  await firstRow.waitFor({ timeout: 20_000 }).catch(() => {
    throw new Error(
      "No decision rows found. Shot 2 needs prior decision history — run any " +
      "chat query first, then re-run. (If rows exist but weren't found, the " +
      "selector is DecisionTimeline.jsx:658 — add data-testid=\"decision-row\".)"
    );
  });
  await firstRow.click();
  // Confirm the inspector actually opened before clicking REPLAY.
  const replayBtn = page.getByRole("button", { name: /REPLAY/i });
  await replayBtn.waitFor({ timeout: 15_000 });
  await page.waitForTimeout(1200);          // linger on the reconstructed decision

  await replayBtn.click();

  // The inspector shows EITHER "Replay Result" or "Replay failed" — wait for
  // whichever resolves, then surface the error case clearly.
  await page.getByText(/Replay Result|Replay failed/i).first().waitFor({ timeout: 60_000 });
  if (await page.getByText(/Replay failed/i).count()) {
    await debugShot(page, "replay-endpoint-error");
    throw new Error(
      "The /replay/{id} call failed on this instance (the view showed 'Replay " +
      "failed'). That's a backend issue, not the recorder — check the API is up " +
      "and try a more recent decision."
    );
  }
  await page.waitForTimeout(2500);          // hold on the result so it's fully painted

  await saveVideo(ctx, dir, "shot2-replay.webm");
  } catch (e) {
    await debugShot(page, "replay-fail");
    try { await ctx.close(); } catch {}
    throw e;
  }
}

// ── Shot 3: offline proof (the philosophy) — OPTIONAL ────────────────────────
// The most convincing version is captured MANUALLY (toggle OS wifi/airplane mode
// on camera — see README). This automated variant instead *proves no cloud
// dependency* by aborting every request to a known cloud AI host while leaving
// localhost intact, then asking a question that your local model answers.
async function shotOffline(browser) {
  console.log("▶ Shot 3 — offline proof (cloud hosts blocked)");
  const { ctx, dir } = await newRecordedContext(browser, "offline");
  const page = await ctx.newPage();
  await page.route("**/*", route => {
    const host = new URL(route.request().url()).hostname;
    if (/openai|anthropic|googleapis|cohere|mistral/i.test(host)) return route.abort();
    return route.continue();
  });
  await page.goto(UI, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);

  const input = page.getByPlaceholder(/ask anything/i);
  await type(page, input, PROMPT);
  await input.press("Enter");
  await page.waitForTimeout(18_000);        // local model answers, no cloud

  await saveVideo(ctx, dir, "shot3-offline.webm");
}

(async () => {
  // Headed by default: headless Chromium blanks out the styled result panels
  // (background-clip:text header, animated SVG gauge, drop-shadow) in the video.
  // A real window renders them faithfully. Set HEADLESS=1 to force headless.
  const browser = await chromium.launch({ headless: process.env.HEADLESS === "1" });
  try {
    await shotDivergence(browser);
    await shotReplay(browser);
    if (process.env.INCLUDE_OFFLINE === "1") await shotOffline(browser);
    console.log("\n✅ Done. Convert with:  ./to-gif.sh");
  } catch (e) {
    console.error("\n✗ Recording failed:", e.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
