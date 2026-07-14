// docMeta.js — how the Library reads a document's filename.
// Pure data helpers: no rendering, no styling. A file type maps to a TONE (a
// meaning), which the kit resolves to a color at paint time.

const TYPE_META = {
  pdf:  { label: "PDF",      tone: "error"   },
  md:   { label: "Markdown", tone: "gold"    },
  txt:  { label: "Text",     tone: "subtle"  },
  csv:  { label: "Data",     tone: "success" },
  json: { label: "Data",     tone: "success" },
  yaml: { label: "Config",   tone: "teal"    },
  yml:  { label: "Config",   tone: "teal"    },
  html: { label: "Web",      tone: "clay"    },
  css:  { label: "Web",      tone: "clay"    },
};

const CODE_EXT = new Set(["py", "js", "ts", "jsx", "tsx", "sh", "sql", "toml", "cfg", "conf", "rst"]);

/** The file types the Library will accept — shared by the picker and the drop zone. */
export const ACCEPTED = [
  ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
  ".html", ".css", ".sh", ".sql", ".csv", ".pdf", ".toml", ".cfg", ".conf", ".rst",
].join(",");

export function typeOf(filename) {
  const ext = (filename.split(".").pop() || "").toLowerCase();
  if (TYPE_META[ext]) return { ext, ...TYPE_META[ext] };
  if (CODE_EXT.has(ext)) return { ext, label: "Code", tone: "blue" };
  return { ext, label: "Document", tone: "subtle" };
}

/** "quarterly-review_v2.pdf" → "Quarterly Review V2" */
export function prettyTitle(filename) {
  const stem = filename.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim();
  if (!stem) return filename;
  return stem.replace(/\b\w/g, c => c.toUpperCase());
}

export function prettyDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso.includes("T") ? iso : iso.replace(" ", "T"));
    if (isNaN(d)) return "";
    const days = (Date.now() - d.getTime()) / 86400000;
    if (days < 1)  return "today";
    if (days < 2)  return "yesterday";
    if (days < 30) return `${Math.floor(days)}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch { return ""; }
}

export function readLength(chars) {
  if (!chars) return null;
  const min = Math.max(1, Math.round(chars / 1200));
  return min >= 60 ? `${Math.round(min / 60)}h read` : `${min} min read`;
}

/** The one-line "Markdown · 3d ago · 4 min read" caption under a doc title. */
export function docSubtitle(doc) {
  return [typeOf(doc.filename).label, prettyDate(doc.added), readLength(doc.chars)]
    .filter(Boolean)
    .join(" · ");
}
