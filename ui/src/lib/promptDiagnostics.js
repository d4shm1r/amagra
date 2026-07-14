// Prompt diagnostics — the "AST projection" layer for the Prompt IDE (#71).
//
// NOT a new analysis. This is an *index layer* over the same heuristics the
// metrics panel already uses (the VAGUE / PASSIVE / FILLER word lists, long
// sentences, and {{template variables}}), but it anchors each finding to a
// character span so Monaco can render it inline (squiggle + hover) and offer a
// click-to-fix. The whole-prompt scores stay in computeMetrics(); this just
// gives the span-anchored findings a stable location.
//
// computeDiagnostics(text) → [{ startLine, startCol, endLine, endCol,
//                               message, severity, fix }]
//   severity: "warning" | "info" | "hint"
//   fix:      "remove" (safe to delete) | undefined

const VAGUE = ["something", "things", "stuff", "etc", "maybe", "perhaps", "kind of",
  "sort of", "a bit", "somehow", "basically", "generally", "usually", "quite",
  "simply", "obviously", "actually", "literally", "very", "really", "just"];
const PASSIVE = ["should be", "would be", "could be", "might be", "seems to",
  "appears to", "tends to"];
const FILLER = ["please note", "as mentioned", "it goes without saying",
  "feel free", "of course", "needless to say"];

const PER_CATEGORY_CAP = 8;   // keep the gutter calm — flag the first N of each

function escapeRegExp(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

// Precompute line-start offsets so offset→(line,col) is O(log n)-ish per lookup.
function makeLineIndex(text) {
  const starts = [0];
  for (let i = 0; i < text.length; i++) if (text[i] === "\n") starts.push(i + 1);
  return starts;
}
function posAt(starts, offset) {
  // Monaco is 1-based for both line and column.
  let lo = 0, hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= offset) lo = mid; else hi = mid - 1;
  }
  return { line: lo + 1, col: offset - starts[lo] + 1 };
}

function pushSpan(out, starts, start, end, d) {
  const a = posAt(starts, start), b = posAt(starts, end);
  out.push({
    startLine: a.line, startCol: a.col, endLine: b.line, endCol: b.col,
    message: d.message, severity: d.severity, fix: d.fix,
  });
}

function matchTerms(text, terms, out, starts, make) {
  for (const term of terms) {
    const re = new RegExp("\\b" + escapeRegExp(term) + "\\b", "gi");
    let m, n = 0;
    while ((m = re.exec(text)) && n < PER_CATEGORY_CAP) {
      pushSpan(out, starts, m.index, m.index + m[0].length, make(m[0]));
      n++;
    }
  }
}

export function computeDiagnostics(text) {
  if (!text || !text.trim()) return [];
  const starts = makeLineIndex(text);
  const out = [];

  // Vague words — replace with something concrete.
  matchTerms(text, VAGUE, out, starts, (w) => ({
    severity: "warning",
    message: `Vague word "${w}" — replace it with a specific noun or quantity.`,
  }));

  // Passive / hedging — state it directly.
  matchTerms(text, PASSIVE, out, starts, (w) => ({
    severity: "info",
    message: `Hedging phrase "${w}" — prefer a direct instruction.`,
  }));

  // Filler — safe to cut (offers a click-to-fix).
  matchTerms(text, FILLER, out, starts, (w) => ({
    severity: "info", fix: "remove",
    message: `Filler "${w}" — adds no instruction. Safe to remove.`,
  }));

  // Long sentences (> 28 words) — anchored at the sentence span.
  {
    const re = /[^.!?\n]+[.!?]?/g;
    let m, n = 0;
    while ((m = re.exec(text)) && n < PER_CATEGORY_CAP) {
      const s = m[0];
      if (s.trim().split(/\s+/).length > 28) {
        const lead = s.length - s.trimStart().length;
        pushSpan(out, starts, m.index + lead, m.index + s.trimEnd().length, {
          severity: "hint",
          message: "Long sentence (over 28 words) — split it into focused instructions.",
        });
        n++;
      }
    }
  }

  // {{template variables}} — flag so they aren't sent unfilled.
  {
    const re = /\{\{\s*([^}]*?)\s*\}\}/g;
    let m, n = 0;
    while ((m = re.exec(text)) && n < PER_CATEGORY_CAP * 2) {
      const name = m[1].trim();
      pushSpan(out, starts, m.index, m.index + m[0].length, name
        ? { severity: "info", message: `Template variable {{${name}}} — fill in before sending.` }
        : { severity: "warning", message: "Empty template variable {{ }} — name it or remove it." });
      n++;
    }
  }

  return out;
}

// Distinct messages by location, for a status-bar count.
export function diagnosticCount(diags) { return diags.length; }
