// Shot 3 (offline proof) — network-triggered capture.
//
// Unlike shots 1 and 2, this one can't be fully scripted end to end: the point
// is a viewer seeing the OS network actually go down, which needs a real
// screen recording (not Playwright's own recordVideo, which only captures the
// tab) and a real, physical wifi toggle. Coordinating that by asking the human
// to reply in chat doesn't work — conversational round-trips run longer than
// any reasonable timeout. So instead this script polls the real interface
// link state and reacts the instant it changes — no manual signal at all.
//
// Flow: open a real visible browser, type the demo prompt, wait for the wifi
// interface to actually go down (submit + capture the local answer the
// instant it does), then wait for it to come back up (hold a couple seconds
// on "back online", then close). You just flip wifi off, watch it answer,
// flip it back on — nothing to type or signal in between.
//
// Run:  IFACE=wlo1 node record-offline-manual.mjs
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const UI  = process.env.AMAGRA_UI || "http://localhost:3000";
const PROMPT = process.env.DEMO_PROMPT || "Is it safe to store JWTs in localStorage?";
const IFACE = process.env.IFACE || "wlo1";
const OPERSTATE_PATH = `/sys/class/net/${IFACE}/operstate`;

function linkState() {
  try { return readFileSync(OPERSTATE_PATH, "utf8").trim(); }
  catch { return "unknown"; }
}

async function waitForLinkState(target, timeoutMs, label) {
  console.log(`Waiting for ${IFACE} to go ${label} (currently: ${linkState()})...`);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const s = linkState();
    if (target === "down" ? s !== "up" : s === "up") {
      console.log(`  -> ${IFACE} is now ${s}.`);
      return true;
    }
    await new Promise(r => setTimeout(r, 400));
  }
  console.error(`Timed out waiting for ${IFACE} to go ${label} (still ${linkState()}).`);
  return false;
}

const seedStorage = () => {
  try {
    localStorage.setItem("onboarding_done_v1", "1");
    localStorage.setItem("ui_mode_v1", "advanced");
  } catch {}
};

(async () => {
  const browser = await chromium.launch({
    headless: false,
    args: ["--window-position=0,0", "--window-size=1280,800"],
  });
  const ctx = await browser.newContext({ viewport: null });
  await ctx.addInitScript(seedStorage);
  const page = await ctx.newPage();
  await page.goto(UI, { waitUntil: "load" });
  await page.waitForTimeout(1000);

  const input = page.getByPlaceholder(/ask anything/i);
  await input.click();
  await input.fill("");
  await input.pressSequentially(PROMPT, { delay: 42 });

  console.log(`\nREADY — prompt typed, not submitted. Turn wifi off whenever you like.`);

  const wentDown = await waitForLinkState("down", 30 * 60_000, "down");
  if (!wentDown) { await browser.close(); process.exit(1); }

  console.log("Offline detected — submitting prompt now...");
  await input.press("Enter");
  await page.waitForTimeout(22_000); // local model answers, no cloud
  console.log("Answer captured. Turn wifi back on whenever you're ready.");

  const cameBack = await waitForLinkState("up", 30 * 60_000, "back up");
  await page.waitForTimeout(cameBack ? 2500 : 0); // linger on "back online" if it happened

  await browser.close();
  console.log("Browser closed. Stop the screen recording now.");
})();
