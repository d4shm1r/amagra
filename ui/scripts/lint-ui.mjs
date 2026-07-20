#!/usr/bin/env node
// lint-ui.mjs — enforces the one architectural rule of ui/src.
//
//   Colors, shapes and style objects may only be written in
//   src/styles/ (tokens) and src/components/ui|forms/ (the kit).
//   Everything else — tabs, panels, feature components — composes the kit.
//
// A view that needs a look the kit doesn't have must ADD IT TO THE KIT, so the
// next view gets it for free. That is the whole point: the design system is
// where design decisions live, and this script is what keeps them there.
//
// It works as a RATCHET. Files listed in DEBT below were already violating the
// rule when the kit landed; they are reported but tolerated. Every other file
// must be clean, so a converted tab can never silently regress and a new tab
// can never be born dirty.
//
//   node scripts/lint-ui.mjs           → fail on any non-DEBT violation
//   node scripts/lint-ui.mjs --debt    → also list what's left to convert
//
// Removing a file from DEBT is the last step of converting it. Never add one.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src", import.meta.url));

// The kit itself — the only place design decisions may be written.
const KIT = ["styles/", "components/ui/", "components/forms/"];

// Pre-existing violations, to be converted tab by tab. This list only shrinks.
const DEBT = new Set([
  "App.jsx",
  "main.jsx",
  "components/layout/AppLauncher.jsx",
  "components/layout/Onboarding.jsx",
  "components/panels/AgentContextPanel.jsx",
  "components/panels/CognitiveMapPanel.jsx",
  "components/panels/InspectOverviewPanel.jsx",
  "components/panels/PlanGraphPanel.jsx",
  "components/panels/PolicyPanel.jsx",
  "components/panels/PromptVersionDiff.jsx",
  "components/panels/TracesPanel.jsx",
  "config/constants.js",
  "config/history.js",
  "lib/monacoSetup.js",
  "tabs/ChatTab.jsx",
  "tabs/ConsensusTab.jsx",
  "tabs/ContextInspectorTab.jsx",
  "tabs/DataTab.jsx",
  "tabs/DecisionTimelineTab.jsx",
  "tabs/ExplainProjectTab.jsx",
  "tabs/GoalsTab.jsx",
  "tabs/HomeTab.jsx",
  "tabs/KnowledgeGraphTab.jsx",
  "tabs/MemoryBrowserTab.jsx",
  "tabs/MindMapTab.jsx",
  "tabs/ProjectStateTab.jsx",
  "tabs/PromptEditorTab.jsx",
  "tabs/ProviderSettingsTab.jsx",
  "tabs/ResearchTab.jsx",
  "tabs/RunsTab.jsx",
  "tabs/SkillsTab.jsx",
  "tabs/TasksTab.jsx",
  "tabs/TimelineTab.jsx",
  "tabs/VersionHistoryTab.jsx",
]);

const RULES = [
  { id: "hex-color",    re: /#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3}(?:[0-9a-fA-F]{2})?)?\b/,
    msg: "raw hex color — pass a tone instead (tone.js), or add the color to the kit" },
  { id: "rgb-color",    re: /\brgba?\s*\(/,
    msg: "raw rgb()/rgba() color — pass a tone instead (tone.js)" },
  { id: "inline-style", re: /style=\{\{/,
    msg: "inline style object — compose kit primitives (Stack/Row/Grid/Card/Text)" },
  { id: "style-block",  re: /<style>/,
    msg: "<style> block — CSS belongs in styles/index.css" },
  { id: "token-import", re: /from\s+["']@\/styles\/theme["']/,
    msg: "imports raw design tokens — a view should only import from @/components/ui|forms" },
  // The app has already lost this fight once: a past phase stripped `maxWidth +
  // margin: 0 auto` from 16 tab roots to make App the sole layout authority, and
  // four files had quietly grown it back by the time the kit landed. The width of
  // the page is LAYOUT.content, rendered by <Column>. Nothing else centers.
  { id: "self-centering", re: /margin(Left|Right)?:\s*["'`][^"'`]*\bauto\b/,
    msg: "a view must not center itself — the shell owns the column (<Column>, LAYOUT in theme.js)" },
];

function walk(dir) {
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return walk(path);
    return /\.jsx?$/.test(name) ? [path] : [];
  });
}

const showDebt = process.argv.includes("--debt");
const violations = [];
const debtFiles = [];

for (const path of walk(SRC)) {
  const rel = relative(SRC, path);
  if (KIT.some(k => rel.startsWith(k))) continue;

  const hits = [];
  readFileSync(path, "utf8").split("\n").forEach((line, i) => {
    // Comments describe the rule; they don't break it.
    const code = line.replace(/\/\/.*$/, "").replace(/\/\*.*?\*\//g, "");
    for (const rule of RULES) {
      if (rule.re.test(code)) hits.push({ line: i + 1, rule, text: line.trim() });
    }
  });
  if (!hits.length) continue;

  if (DEBT.has(rel)) debtFiles.push({ rel, count: hits.length });
  else violations.push({ rel, hits });
}

const clean = walk(SRC).filter(p => {
  const rel = relative(SRC, p);
  return !KIT.some(k => rel.startsWith(k)) && !DEBT.has(rel);
}).length;

if (violations.length) {
  console.error("\n✗ Design-system violations — these files must compose the kit, not restyle it:\n");
  for (const { rel, hits } of violations) {
    console.error(`  ${rel}`);
    for (const h of hits.slice(0, 8)) {
      console.error(`    ${String(h.line).padStart(4)}  ${h.rule.id.padEnd(12)} ${h.rule.msg}`);
      console.error(`          ${h.text.slice(0, 90)}`);
    }
    if (hits.length > 8) console.error(`    …and ${hits.length - 8} more`);
    console.error("");
  }
  console.error("Fix: add the missing primitive to src/components/ui, then compose it here.\n");
  process.exit(1);
}

// ── The nav must only name icons that exist ──────────────────────────────────
// navConfig names its marks ("icon: chat") instead of pasting a glyph, which is
// what makes the menu one set. The cost of a name is that a typo renders
// nothing at all — a silently empty chip. So check it here: every icon the nav
// asks for must be in the set, and every icon in the set should be used.
{
  const nav = readFileSync(join(SRC, "config/navConfig.js"), "utf8");
  const set = readFileSync(join(SRC, "components/ui/Icon.jsx"), "utf8");

  const asked = [...nav.matchAll(/\bicon:\s*"([\w-]+)"/g)].map(m => m[1]);
  const drawn = new Set([...set.matchAll(/^\s{2}([\w-]+):\s*</gm)].map(m => m[1]));

  const missing = [...new Set(asked)].filter(n => !drawn.has(n));
  if (missing.length) {
    console.error("\n✗ navConfig names icons that components/ui/Icon.jsx doesn't draw:\n");
    for (const n of missing) console.error(`    icon: "${n}"  → not in the set (renders an empty chip)`);
    console.error("\nFix: draw it in components/ui/Icon.jsx, on the same 24×24 grid.\n");
    process.exit(1);
  }

  // ── Every entry carries an icon AND a description ──────────────────────────
  // A tile with no description is a shorter tile, and one short tile in a grid
  // row makes the whole row look broken. All-or-nothing is the only stable rule.
  const entries = (nav.match(/\{\s*id:\s*"/g) || []).length;
  const descs   = [...nav.matchAll(/\bdesc:\s*"([^"]*)"/g)].map(m => m[1]);
  if (entries !== asked.length || entries !== descs.length) {
    console.error(`\n✗ navConfig: ${entries} entries but ${asked.length} icons and ${descs.length} descriptions.`);
    console.error("  Every surface and every tab needs both.\n");
    process.exit(1);
  }

  // ── One voice ─────────────────────────────────────────────────────────────
  // The menu used to speak in three at once: Title-Case imperatives on the
  // surfaces ("Monitor system health"), lower-case verbs on some tabs ("talk to
  // your agents"), lower-case nouns on the rest ("the routing skill graph"). No
  // two tiles scanned the same way. One voice: a noun phrase, lower case, no
  // full stop, "and" not "&", short enough for one line.
  const VERBS = /^(talk|write|choose|tune|browse|open|view|see|run|manage|explore|inspect|monitor|analyz|configur|work|set|start|make|show)/i;
  const bad = [];
  for (const d of descs) {
    if (/^[A-Z]/.test(d) && !/^Amagra/.test(d)) bad.push([d, "starts upper case — it's a subtitle, not a sentence"]);
    else if (/\.$/.test(d))                     bad.push([d, "ends in a full stop"]);
    else if (/&/.test(d))                       bad.push([d, `uses "&" — write "and"`]);
    else if (VERBS.test(d))                     bad.push([d, "starts with a verb — name what the thing IS, not what you do there"]);
    else if (d.length > 34)                     bad.push([d, `${d.length} chars — too long for one line (max 34)`]);
  }
  if (bad.length) {
    console.error("\n✗ navConfig descriptions break the one-voice rule:\n");
    for (const [d, why] of bad) console.error(`    "${d}"\n        ${why}`);
    console.error("");
    process.exit(1);
  }
}

const totalDebt = debtFiles.reduce((n, d) => n + d.count, 0);
console.log(`✓ ui: ${clean} file(s) clean · ${debtFiles.length} file(s) awaiting conversion (${totalDebt} violations)`);

if (showDebt && debtFiles.length) {
  console.log("\n  Remaining, worst first — convert, then delete from DEBT in this script:\n");
  for (const d of debtFiles.sort((a, b) => b.count - a.count)) {
    console.log(`    ${String(d.count).padStart(4)}  ${d.rel}`);
  }
  console.log("");
}
