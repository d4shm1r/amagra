import { useState, useEffect, useRef, useCallback } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

const T = {
  bg:      "#F4F0E8",
  surface: "#FAF7F2",
  surface2:"#F4F0E8",
  border:  "#E0D6C4",
  text:    "#2E2010",
  muted:   "#9A7A60",
  mutedLt: "#5C4030",
};

const fBody = "Georgia, Cambria, 'Times New Roman', serif";
const fUI   = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
const fMono = "Consolas, 'Courier New', monospace";
const ARTICLE_MAX = 860;

// ── KaTeX math rendering ───────────────────────────────────────
function KTex({ src, display = false }) {
  try {
    const html = katex.renderToString(src, { displayMode: display, throwOnError: false, strict: false });
    return <span dangerouslySetInnerHTML={{ __html: html }} />;
  } catch {
    return <code style={{ color: "#B42318", fontSize: 12 }}>{src}</code>;
  }
}
function KTexBlock({ src, n }) {
  return (
    <div style={{ background: T.bg, border: `1px solid ${T.border}`, borderRadius: 6, padding: "20px 28px", margin: "24px 0", display: "flex", alignItems: "center", justifyContent: "space-between", overflowX: "auto", gap: 20 }}>
      <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
        <KTex src={src} display />
      </div>
      {n && <span style={{ fontSize: 13, color: T.muted, flexShrink: 0, fontFamily: fBody, fontStyle: "italic" }}>({n})</span>}
    </div>
  );
}

// ── Shared prose ───────────────────────────────────────────────
function M({ children }) {
  return <span style={{ fontFamily: fBody, fontStyle: "italic", color: "#1E5A8A" }}>{children}</span>;
}
function P({ children }) {
  return <p style={{ fontSize: 15, color: "#3A2A14", lineHeight: 1.92, marginBottom: 20, fontFamily: fBody }}>{children}</p>;
}
function Code({ children }) {
  return <code style={{ fontFamily: fMono, fontSize: 12.5, background: T.surface2, color: "#1E5A8A", padding: "2px 7px", borderRadius: 3, border: `1px solid ${T.border}`, letterSpacing: "0.01em" }}>{children}</code>;
}
function H2({ children, color = "#0F766E" }) {
  return <h2 style={{ fontSize: 19, fontWeight: 700, color, marginTop: 42, marginBottom: 14, paddingBottom: 10, borderBottom: `1px solid ${T.border}`, fontFamily: fUI, letterSpacing: "-0.3px" }}>{children}</h2>;
}
function Callout({ label, value, color = "#0F766E", sub }) {
  return (
    <div style={{ background: T.bg, border: `1px solid ${color}25`, borderTop: `2px solid ${color}`, borderRadius: 6, padding: "14px 18px" }}>
      <span style={{ fontSize: 28, fontWeight: 800, color, fontFamily: fMono, display: "block", marginBottom: 6 }}>{value}</span>
      <div style={{ fontSize: 12, fontWeight: 700, color: T.mutedLt, fontFamily: fUI }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: T.muted, marginTop: 3, fontFamily: fUI }}>{sub}</div>}
    </div>
  );
}
function CalloutGrid({ children }) {
  return <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 12, margin: "22px 0" }}>{children}</div>;
}
function Note({ children, color = "#9A6C00" }) {
  return (
    <div style={{ background: `${color}08`, borderLeft: `3px solid ${color}`, padding: "12px 18px", fontSize: 14, color: "#5C4030", lineHeight: 1.8, margin: "22px 0", fontFamily: fBody, fontStyle: "italic" }}>
      {children}
    </div>
  );
}
function DataTable({ headers, rows, caption }) {
  return (
    <div style={{ margin: "22px 0" }}>
      <div style={{ overflowX: "auto", borderRadius: 6, border: `1px solid ${T.border}`, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>{headers.map(h => <th key={h} style={{ background: T.surface2, color: T.mutedLt, padding: "9px 14px", textAlign: "left", borderBottom: `1px solid ${T.border}`, fontWeight: 700, fontFamily: fUI, fontSize: 12, letterSpacing: "0.02em" }}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>{row.map((cell, j) => <td key={j} style={{ color: "#5C4030", padding: "8px 14px", borderBottom: `1px solid ${T.border}22`, background: i % 2 === 0 ? "transparent" : `${T.surface2}88`, fontFamily: fUI, fontSize: 12.5 }}>{cell}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {caption && <div style={{ fontSize: 12.5, color: T.muted, marginTop: 8, fontStyle: "italic", textAlign: "center", fontFamily: fBody }}>{caption}</div>}
    </div>
  );
}

// ── Paper structural elements ──────────────────────────────────
function Abstract({ children }) {
  return (
    <div style={{ borderLeft: "3px solid #0F766E", padding: "14px 22px", margin: "28px 0" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "#0F766E", letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: 10, fontFamily: fUI }}>Abstract</div>
      <p style={{ fontSize: 14.5, color: "#5C4030", lineHeight: 1.9, margin: 0, fontStyle: "italic", fontFamily: fBody }}>{children}</p>
    </div>
  );
}
function SectionNum({ id, n, children, color = "#0F766E" }) {
  return (
    <h2 id={id} style={{ display: "flex", alignItems: "baseline", gap: 12, fontSize: 19, fontWeight: 700, color, marginTop: 52, marginBottom: 14, paddingBottom: 10, borderBottom: `1px solid ${T.border}`, scrollMarginTop: 16, fontFamily: fUI, letterSpacing: "-0.3px" }}>
      <span style={{ fontFamily: fMono, fontSize: 13, color: T.muted, fontWeight: 400 }}>{n}</span>
      {children}
    </h2>
  );
}
function SubSection({ id, n, children }) {
  return (
    <h3 id={id} style={{ display: "flex", alignItems: "baseline", gap: 9, fontSize: 15.5, fontWeight: 700, color: "#9A6C00", marginTop: 32, marginBottom: 10, scrollMarginTop: 16, fontFamily: fUI }}>
      <span style={{ fontFamily: fMono, fontSize: 12, color: T.muted, fontWeight: 400 }}>{n}</span>
      {children}
    </h3>
  );
}
function Definition({ n, title, children }) {
  return (
    <div style={{ background: T.bg, border: `1px solid ${T.border}`, borderLeft: "3px solid #0F766E", borderRadius: 6, padding: "16px 22px", margin: "22px 0" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "#0F766E", marginBottom: 12, fontFamily: fUI, letterSpacing: "0.1em", textTransform: "uppercase" }}>
        Definition {n}{title ? ` — ${title}` : ""}
      </div>
      <div style={{ fontSize: 14.5, color: "#5C4030", lineHeight: 1.85, fontFamily: fBody }}>{children}</div>
    </div>
  );
}

function Figure({ n, caption, children }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <div style={{ margin: "24px 0", border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden" }}>
        <div style={{ background: T.surface2, padding: "16px 20px" }}>{children}</div>
        <div style={{ padding: "10px 20px", background: T.surface, borderTop: `1px solid ${T.border}`, display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
          <span style={{ fontSize: 13, color: "#9A7A60", fontStyle: "italic", fontFamily: fBody, lineHeight: 1.6 }}>
            <strong style={{ fontStyle: "normal", fontFamily: fUI, fontWeight: 700, fontSize: 11, color: "#8A7058", letterSpacing: "0.05em", textTransform: "uppercase", marginRight: 6 }}>Fig. {n}</strong>
            {caption}
          </span>
          <button
            onClick={() => setExpanded(true)}
            onMouseEnter={e => e.currentTarget.style.background = "#C4880820"}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            style={{ background: "transparent", border: "none", color: "#C48808", fontSize: 11, cursor: "pointer", flexShrink: 0, padding: "3px 8px", borderRadius: 3, fontFamily: fUI }}
          >↗ Expand</button>
        </div>
      </div>
      {expanded && (
        <div onClick={() => setExpanded(false)} style={{ position: "fixed", inset: 0, background: "rgba(72,52,28,0.88)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", cursor: "zoom-out" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: 28, maxWidth: "92vw", maxHeight: "92vh", overflow: "auto", cursor: "auto", boxShadow: "0 24px 64px rgba(72,52,28,0.8)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: T.mutedLt }}>Figure {n}</span>
              <button onClick={() => setExpanded(false)} style={{ background: "transparent", border: `1px solid ${T.border}`, color: T.muted, cursor: "pointer", fontSize: 14, borderRadius: 4, width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
            </div>
            {children}
            <div style={{ fontSize: 12, color: T.muted, marginTop: 14, fontStyle: "italic", maxWidth: 640 }}>{caption}</div>
          </div>
        </div>
      )}
    </>
  );
}

function Expandable({ title, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: `1px solid ${T.border}`, borderRadius: 6, margin: "18px 0", overflow: "hidden" }}>
      <button
        onClick={() => setOpen(o => !o)}
        onMouseEnter={e => e.currentTarget.style.background = "#F4F0E8"}
        onMouseLeave={e => e.currentTarget.style.background = T.surface2}
        style={{ width: "100%", textAlign: "left", padding: "10px 18px", background: T.surface2, border: "none", color: T.mutedLt, cursor: "pointer", display: "flex", alignItems: "center", gap: 10, fontFamily: fUI, fontSize: 13 }}
      >
        <span style={{ fontSize: 9, color: T.muted, flexShrink: 0 }}>{open ? "▼" : "▶"}</span>
        <span style={{ fontWeight: 600 }}>{title}</span>
      </button>
      {open && (
        <div style={{ padding: "18px 22px", borderTop: `1px solid ${T.border}`, background: T.bg }}>
          {children}
        </div>
      )}
    </div>
  );
}

const QS_REFS = [
  { n: 1, authors: "Robertson, S. & Zaragoza, H.", year: 2009, title: "The Probabilistic Relevance Framework: BM25 and Beyond", venue: "Foundations and Trends in Information Retrieval, 3(4)" },
  { n: 2, authors: "Johnson, J., Douze, M. & Jégou, H.", year: 2021, title: "Billion-Scale Similarity Search with GPUs", venue: "IEEE Transactions on Big Data, 7(3)" },
  { n: 3, authors: "Zhao, W. X. et al.", year: 2023, title: "A Survey of Large Language Models", venue: "arXiv:2303.18223" },
  { n: 4, authors: "Vaswani, A. et al.", year: 2017, title: "Attention Is All You Need", venue: "Advances in Neural Information Processing Systems (NeurIPS)" },
  { n: 5, authors: "Amagra Team", year: 2026, title: "Amagra — Phase Log v3: Causal Intelligence", venue: "Internal project documentation, /docs/tracker-v3.md", note: "Phase 12–25 routing development record." },
];

function Cite({ n }) {
  const [show, setShow] = useState(false);
  const ref = QS_REFS.find(r => r.n === n);
  return (
    <span style={{ position: "relative", display: "inline" }}
          onMouseEnter={() => setShow(true)}
          onMouseLeave={() => setShow(false)}>
      <span style={{ color: "#C48808", cursor: "pointer", fontFamily: "Consolas, monospace", fontSize: 12 }}>[{n}]</span>
      {show && ref && (
        <span style={{ position: "absolute", bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)", width: 310, background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 7, padding: "12px 16px", zIndex: 2000, boxShadow: "0 6px 28px rgba(72,52,28,0.8)", pointerEvents: "none", display: "block" }}>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: T.mutedLt, display: "block", marginBottom: 5, fontFamily: fUI }}>{ref.authors} ({ref.year})</span>
          <span style={{ fontSize: 12, color: "#1E5A8A", fontStyle: "italic", display: "block", marginBottom: 5, fontFamily: fBody, lineHeight: 1.5 }}>{ref.title}</span>
          <span style={{ fontSize: 11, color: T.muted, display: "block", fontFamily: fUI }}>{ref.venue}</span>
          {ref.note && <span style={{ fontSize: 10.5, color: T.muted, display: "block", marginTop: 5, opacity: 0.7, fontFamily: fUI }}>{ref.note}</span>}
        </span>
      )}
    </span>
  );
}

function References({ refs }) {
  return (
    <div id="refs" style={{ marginTop: 52, paddingTop: 28, borderTop: `2px solid ${T.border}`, scrollMarginTop: 16 }}>
      <div style={{ fontSize: 17, fontWeight: 700, color: T.mutedLt, marginBottom: 22, fontFamily: fUI, letterSpacing: "-0.2px" }}>References</div>
      <ol style={{ paddingLeft: 24, display: "flex", flexDirection: "column", gap: 14 }}>
        {refs.map((r, i) => (
          <li key={i} style={{ fontSize: 14, color: T.muted, lineHeight: 1.7, fontFamily: fBody }}>
            <span style={{ color: "#5C4030", fontWeight: 600 }}>{r.authors}</span>{" "}
            ({r.year}).{" "}
            <span style={{ fontStyle: "italic", color: "#1E5A8A" }}>{r.title}.</span>{" "}
            <span style={{ color: "#9A7A60" }}>{r.venue}.</span>
            {r.note && <span style={{ color: T.muted, fontSize: 12.5 }}> {r.note}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

// ── Visualizations ─────────────────────────────────────────────
function PipelineDiagram() {
  const Box = ({ label, sub, color = "#E0D6C4", accent = "#0F766E" }) => (
    <div style={{ background: T.bg, border: `1px solid ${color}`, borderTop: `2px solid ${accent}`, borderRadius: 5, padding: "10px 18px", textAlign: "center", minWidth: 140 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: T.mutedLt }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 3, fontFamily: "Consolas, monospace" }}>{sub}</div>}
    </div>
  );
  const Arrow = () => <div style={{ textAlign: "center", color: T.muted, fontSize: 16, lineHeight: 1 }}>↓</div>;
  const Diamond = ({ label }) => (
    <div style={{ background: "#ECEAF6", border: "1px solid #9A6C0066", borderRadius: 5, padding: "10px 20px", textAlign: "center", fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 13, color: "#9A6C00" }}>
      {label}
    </div>
  );
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, padding: "12px 0" }}>
      <Box label="Raw Query" sub="q ∈ ℒ" accent="#9A7A60" color="#E0D6C4" />
      <Arrow />
      <Box label="Normalize & Tokenize" sub="query_normalizer.py" />
      <Arrow />
      <Box label="Domain Scoring" sub="S(d, q)  for all  d ∈ 𝒟" accent="#9A6C00" />
      <Arrow />
      <Diamond label="conf(d *, q) ≥ θ = 0.33 ?" />
      <div style={{ display: "flex", width: "100%", justifyContent: "center", gap: 48, marginTop: 4 }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#15803D", letterSpacing: "0.06em" }}>YES · ~97 %</div>
          <div style={{ color: T.muted, fontSize: 14 }}>↓</div>
          <Box label="Signal Route" sub="deterministic, &lt; 1 ms" accent="#15803D" />
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#B42318", letterSpacing: "0.06em" }}>NO · ~3 %</div>
          <div style={{ color: T.muted, fontSize: 14 }}>↓</div>
          <Box label="LLM Fallback" sub="phi4-mini, 600–900 ms" accent="#B42318" />
        </div>
      </div>
      <div style={{ color: T.muted, fontSize: 14, marginTop: 2 }}>↓</div>
      <Box label="Specialist Agent" sub="python_dev | it_networking | dotnet_dev | …" accent="#C48808" />
    </div>
  );
}

function AccuracyChart() {
  const rows = [
    { label: "Baseline",    desc: "Keyword-only",            val: 70, color: "#B42318" },
    { label: "Phase 12",    desc: "Confidence scoring added", val: 82, color: "#C2410C" },
    { label: "Phase 15",    desc: "Signal-first path",        val: 92, color: "#9A6C00" },
    { label: "Phase 22",    desc: "Terse factual shape",      val: 94, color: "#15803D" },
    { label: "Phase 25",    desc: "Full ablation verified",   val: 97, color: "#0F766E" },
    { label: "Signal-only", desc: "No LLM fallback (ablation)", val: 99, color: "#7E3F8F" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 76, fontSize: 10, color: T.muted, textAlign: "right", fontFamily: "Consolas, monospace", flexShrink: 0 }}>{r.label}</div>
          <div style={{ flex: 1, background: "#ECEAF6", borderRadius: 3, height: 24, overflow: "hidden", position: "relative" }}>
            <div style={{ width: `${r.val}%`, height: "100%", background: `linear-gradient(90deg, ${r.color}99, ${r.color})`, borderRadius: 3, display: "flex", alignItems: "center", paddingLeft: 8 }}>
              <span style={{ fontSize: 10, fontWeight: 800, color: "#1F1408", fontFamily: "Consolas, monospace" }}>{r.val}%</span>
            </div>
            <div style={{ position: "absolute", top: 0, bottom: 0, left: "97%", width: 1, background: "#0F766E66" }} />
          </div>
          <div style={{ width: 160, fontSize: 10, color: T.muted, flexShrink: 0 }}>{r.desc}</div>
        </div>
      ))}
      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ width: 76, flexShrink: 0 }} />
        <div style={{ flex: 1, display: "flex", justifyContent: "flex-end", paddingRight: "3%" }}>
          <span style={{ fontSize: 9, color: "#0F766E66" }}>▲ target 97%</span>
        </div>
      </div>
    </div>
  );
}

function DomainHeatmap() {
  const domains  = ["Python", "Network", "Blazor", "AI / ML", "Terse", "Knowledge"];
  const keywords = ["python / pip", "dns / ssh / ip", "blazor / c#", "pytorch / llm", "command / syntax", "explain / what is"];
  const weights  = [
    [0.95, 0.05, 0.00, 0.12, 0.04, 0.08],
    [0.04, 0.95, 0.00, 0.08, 0.05, 0.10],
    [0.00, 0.04, 0.95, 0.04, 0.00, 0.08],
    [0.12, 0.08, 0.04, 0.90, 0.04, 0.14],
    [0.04, 0.04, 0.00, 0.04, 0.95, 0.08],
    [0.08, 0.08, 0.08, 0.14, 0.08, 0.88],
  ];
  const cell = (v) => {
    const alpha = Math.round(v * 220);
    const hex = alpha.toString(16).padStart(2, "0");
    const color = v > 0.7 ? "#0F766E" : v > 0.3 ? "#9A6C00" : "#9A7A60";
    return { bg: `${color}${hex}`, color: v > 0.5 ? T.mutedLt : T.muted };
  };
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 11, minWidth: 540 }}>
        <thead>
          <tr>
            <th style={{ padding: "6px 10px", textAlign: "right", color: T.muted, fontWeight: 400, fontSize: 10 }}>keyword group →</th>
            {domains.map(d => <th key={d} style={{ padding: "5px 10px", background: T.bg, color: T.muted, fontWeight: 700, border: `1px solid ${T.border}`, fontSize: 10, whiteSpace: "nowrap" }}>{d}</th>)}
          </tr>
        </thead>
        <tbody>
          {keywords.map((kw, i) => (
            <tr key={kw}>
              <td style={{ padding: "5px 10px", color: T.muted, fontSize: 10, textAlign: "right", whiteSpace: "nowrap", paddingRight: 12 }}>{kw}</td>
              {weights[i].map((v, j) => {
                const s = cell(v);
                return <td key={j} style={{ padding: "6px 10px", background: s.bg, border: `1px solid ${T.border}`, textAlign: "center", color: s.color, fontFamily: "Consolas, monospace", fontWeight: v > 0.7 ? 700 : 400 }}>{v.toFixed(2)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfidenceHistogram() {
  const buckets = [
    { label: "0.00–0.11", val: 2,  note: "LLM", color: "#B42318" },
    { label: "0.11–0.22", val: 4,  note: "LLM", color: "#C2410C" },
    { label: "0.22–0.33", val: 6,  note: "LLM", color: "#9A6C00" },
    { label: "0.33–0.50", val: 18, note: "signal", color: "#0F766E" },
    { label: "0.50–0.67", val: 26, note: "signal", color: "#0F766E" },
    { label: "0.67–0.84", val: 28, note: "signal", color: "#0F766E" },
    { label: "0.84–1.00", val: 16, note: "signal", color: "#C48808" },
  ];
  const maxVal = Math.max(...buckets.map(b => b.val));
  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 100, paddingBottom: 4 }}>
        {buckets.map((b, i) => (
          <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
            <div style={{ fontSize: 9, color: T.muted, fontFamily: "Consolas, monospace" }}>{b.val}%</div>
            <div style={{ width: "100%", height: `${(b.val / maxVal) * 76}px`, background: b.color, borderRadius: "2px 2px 0 0", opacity: b.note === "LLM" ? 0.55 : 1 }} />
          </div>
        ))}
      </div>
      <div style={{ position: "relative", height: 20, marginBottom: 4 }}>
        <div style={{ position: "absolute", left: "calc(3 / 7 * 100%)", top: 0, bottom: 0, width: 1, background: "#9A6C00", opacity: 0.7 }} />
        <div style={{ position: "absolute", left: "calc(3 / 7 * 100% + 4px)", top: 2, fontSize: 9, color: "#9A6C00", whiteSpace: "nowrap" }}>θ = 0.33</div>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {buckets.map((b, i) => (
          <div key={i} style={{ flex: 1, fontSize: 9, color: T.muted, textAlign: "center", overflow: "hidden", textOverflow: "ellipsis", fontFamily: "Consolas, monospace" }}>{b.label}</div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 10, justifyContent: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 10, height: 10, background: "#B42318", borderRadius: 2, opacity: 0.55 }} />
          <span style={{ fontSize: 10, color: T.muted }}>LLM fallback (~12%)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 10, height: 10, background: "#0F766E", borderRadius: 2 }} />
          <span style={{ fontSize: 10, color: T.muted }}>Signal route (~88%)</span>
        </div>
      </div>
    </div>
  );
}

// ── TOC component (scroll-spy) ─────────────────────────────────
function TOC({ items, activeId }) {
  return (
    <nav style={{ padding: "24px 16px 24px 18px" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 16, fontFamily: fUI }}>On this page</div>
      {items.map(item => {
        const active = activeId === item.id;
        const indent = (item.level - 1) * 11;
        return (
          <a key={item.id} href={`#${item.id}`}
            onClick={e => { e.preventDefault(); document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}
            style={{
              display: "block",
              padding: "4px 4px",
              paddingLeft: indent + 8 + "px",
              fontSize: item.level === 1 ? 12 : 11,
              fontWeight: item.level === 1 ? 600 : 400,
              color: active ? "#0F766E" : "#9A7A60",
              textDecoration: "none",
              borderLeft: `2px solid ${active ? "#0F766E" : "transparent"}`,
              marginLeft: "-2px",
              lineHeight: 1.65,
              transition: "color .15s, border-color .15s",
              fontFamily: fUI,
            }}
          >{item.label}</a>
        );
      })}
    </nav>
  );
}

const QS_TOC = [
  { id: "abstract", label: "Abstract",               level: 1 },
  { id: "s1",       label: "1. Introduction",         level: 1 },
  { id: "s2",       label: "2. Background",            level: 1 },
  { id: "s3",       label: "3. Architecture",          level: 1 },
  { id: "s3-1",     label: "3.1 Token Extraction",     level: 2 },
  { id: "s3-2",     label: "3.2 Domain Scoring",       level: 2 },
  { id: "s3-3",     label: "3.3 Confidence Routing",   level: 2 },
  { id: "s3-4",     label: "3.4 LLM Fallback",         level: 2 },
  { id: "s4",       label: "4. Action Classification", level: 1 },
  { id: "s5",       label: "5. Results",               level: 1 },
  { id: "s5-1",     label: "5.1 Accuracy",             level: 2 },
  { id: "s5-2",     label: "5.2 Heatmap",              level: 2 },
  { id: "s5-3",     label: "5.3 Confidence Dist.",     level: 2 },
  { id: "s5-4",     label: "5.4 Latency",              level: 2 },
  { id: "s6",       label: "6. Limitations",           level: 1 },
  { id: "s7",       label: "7. Conclusion",            level: 1 },
  { id: "refs",     label: "References",               level: 1 },
];

// ── QuerySignal paper ──────────────────────────────────────────
function ArticleQuerySignal() {
  return (
    <article>
      {/* Byline */}
      <div style={{ display: "flex", gap: 0, flexWrap: "wrap", borderBottom: `1px solid ${T.border}`, paddingBottom: 18, marginBottom: 8, fontFamily: fUI, fontSize: 13, color: T.muted }}>
        <span style={{ color: "#5C4030", fontWeight: 600, marginRight: 20 }}>Amagra Team</span>
        <span style={{ marginRight: 20 }}>7 June 2026</span>
        <span style={{ marginRight: 20 }}>Version 1.0</span>
        <span>phi4-mini · RTX 2050 4GB</span>
      </div>

      <div id="abstract" style={{ scrollMarginTop: 16 }}>
        <Abstract>
          Local agentic AI systems require fast, reliable intent routing without cloud dependency. Existing approaches
          rely either on brittle keyword matching or LLM-based classification — the former misses ambiguous queries,
          the latter adds 600–900 ms per decision and introduces non-determinism. We present <em>QuerySignal</em>, a
          confidence-threshold routing architecture that replaces LLM classification with deterministic domain
          scoring. On a 100-query labeled evaluation, QuerySignal achieves <strong>97% routing accuracy</strong> with
          sub-millisecond classification latency. An ablation study removing the LLM fallback entirely yields 99%,
          confirming the signal path's dominance. We further describe the action classification sub-system and the
          pattern-coverage fix that eliminated a 10% unknown-action rate.
        </Abstract>
      </div>

      {/* §1 Introduction */}
      <SectionNum id="s1" n="1.">Introduction</SectionNum>
      <P>
        Routing a natural-language query to the correct specialist agent is the critical path in any multi-agent
        system. Get it wrong and the user receives a generic response from an off-domain model; get it slow and
        the latency budget for the entire response is consumed before generation begins.
      </P>
      <P>
        The naive approach — forwarding every query to an LLM and asking "which agent should handle this?" —
        is accurate but expensive. On phi4-mini running locally on an RTX 2050, each such call costs 600–900 ms
        and produces inconsistent results: identical queries can yield different routing decisions across runs.
        The alternative — keyword matching alone — is fast and deterministic but brittle: queries with no
        matching keyword fall through to a catch-all path, degrading response quality.
      </P>
      <P>
        QuerySignal bridges this gap. It formalises keyword signal as a <em>domain confidence score</em> and
        routes deterministically when the score clears a threshold, reserving the LLM exclusively for queries
        where the signal is genuinely ambiguous. The result is simultaneously fast, deterministic, and accurate.
      </P>

      {/* §2 Background */}
      <SectionNum id="s2" n="2.">Background</SectionNum>
      <P>
        Keyword-based routing has a long history in information retrieval. BM25 <Cite n={1} /> scores documents
        against query terms using term frequency and inverse document frequency — a structure closely related
        to our domain scoring function. The key difference: BM25 ranks documents, while QuerySignal classifies
        intent with a confidence gate.
      </P>
      <P>
        LLM-based intent classification was popularised by dialogue systems (BERT for slot-filling, GPT for
        zero-shot classification). These approaches achieve high accuracy on unseen query types but require
        a model call per query <Cite n={3} />. For a locally-hosted system constrained to 4 GB VRAM, this is
        prohibitive on the routing path. Retrieval-augmented generation (RAG) architectures face the same problem:
        embedding-based retrieval <Cite n={2} /> is used for document selection but not for upstream intent routing.
      </P>

      {/* §3 Architecture */}
      <SectionNum id="s3" n="3.">The QuerySignal Architecture</SectionNum>
      <P>
        The pipeline has four stages: normalisation and tokenisation, domain scoring, confidence gating,
        and LLM fallback. Figure 1 shows the full flow.
      </P>
      <Figure n="1" caption="QuerySignal routing pipeline. Queries clearing the confidence threshold θ route deterministically in under 1 ms. Only ~3% of queries reach the LLM fallback.">
        <PipelineDiagram />
      </Figure>

      <SubSection id="s3-1" n="3.1">Token Extraction & Normalisation</SubSection>
      <P>
        The query <M>q</M> is lowercased, punctuation-stripped, and split into tokens. Common stopwords
        (articles, prepositions, auxiliary verbs) are discarded. The remaining token set{" "}
        <KTex src="T(q) = \{t_1, \ldots, t_n\}" /> is what the scoring function operates on.
      </P>
      <P>
        Multi-word patterns are matched before single-token lookup. The pattern <Code>"not working"</Code> is
        treated as a single debug signal rather than the tokens <Code>"not"</Code> (discarded) and{" "}
        <Code>"working"</Code> (ambiguous). This ordering is critical for queries like{" "}
        <em>"why is X not working"</em> which would otherwise score near-zero.
      </P>

      <SubSection id="s3-2" n="3.2">Domain Scoring</SubSection>
      <P>
        Each domain <M>d</M> ∈ <KTex src="\mathcal{D}" /> maintains a keyword registry <KTex src="K_d" /> — a
        mapping from token patterns to non-negative weights. The domain score is the normalised sum of matched
        weights:
      </P>
      <Definition n="1" title="Domain Score">
        For query <M>q</M> with token set <KTex src="T(q) = \{t_1, \ldots, t_n\}" />, the score for
        domain <M>d</M> is:
        <KTexBlock
          n="1"
          src="S(d, q) = \frac{1}{|q|} \sum_{i=1}^{n} w(t_i,\, d) \cdot \mathbf{1}[t_i \in K_d]"
        />
        where <KTex src="w(t, d)" /> is the weight of token <M>t</M> in domain <M>d</M>'s registry,{" "}
        <KTex src="\mathbf{1}[\cdot]" /> is the indicator function, and <KTex src="|q|" /> is the query
        length in tokens.
      </Definition>
      <Expandable title="Why normalise by |q| ?">
        <P>
          Without normalisation, longer queries dominate shorter ones. A 10-token Python query would score
          ~10× higher than a single-token "python?" — both should route to the same domain. The{" "}
          <KTex src="\frac{1}{|q|}" /> factor makes scores comparable across query lengths.
        </P>
        <P>
          IDF weighting was evaluated as an alternative normalisation. It was discarded because the keyword
          registry is domain-specific (not corpus-wide), so IDF estimates are unreliable at the vocabulary
          sizes used here (~50–100 tokens per domain).
        </P>
      </Expandable>
      <P>
        Weights reflect domain specificity. The token <Code>"python"</Code> carries weight 0.95 in the{" "}
        <em>python_dev</em> domain and 0.12 in <em>ai_ml</em> (Python is common in ML code). The token{" "}
        <Code>"network"</Code> carries 0.95 in <em>it_networking</em> and 0.08 in <em>ai_ml</em> (neural
        networks). The heatmap in §5.2 visualises this weight matrix.
      </P>

      <SubSection id="s3-3" n="3.3">Confidence-Threshold Routing</SubSection>
      <P>
        Given the domain scores for all domains, the winning domain{" "}
        <KTex src="d^* = \arg\max_{d}\, S(d, q)" /> is identified. Its confidence is:
      </P>
      <Definition n="2" title="Routing Confidence">
        <KTexBlock
          n="2"
          src="\text{conf}(d^*, q) = \frac{S(d^*, q)}{\displaystyle\sum_{d \in \mathcal{D}} S(d, q) + \varepsilon}"
        />
        where <KTex src="\varepsilon = 10^{-6}" /> prevents division by zero on zero-signal queries.
      </Definition>
      <P>The routing decision is governed by a fixed threshold <M>θ</M>:</P>
      <Definition n="3" title="Routing Decision">
        <KTexBlock
          n="3"
          src="\text{route}(q) = \begin{cases} d^* & \text{if } \text{conf}(d^*,\,q) \geq \theta \\ \text{LLM}(q) & \text{otherwise} \end{cases}"
        />
        where <KTex src="\theta = 0.33" /> is the routing confidence threshold, chosen empirically.
      </Definition>
      <P>
        The threshold <KTex src="\theta = 0.33" /> represents a qualitative boundary: a confidence above
        one-third means the winning domain scores higher than the sum of all other domains combined. Queries
        spanning two domains (e.g. AI/ML + Python) naturally score below 0.33 for any single domain and fall
        to the LLM, which handles compound intent correctly.
      </P>

      <SubSection id="s3-4" n="3.4">LLM Fallback Integration</SubSection>
      <P>
        The fallback path forwards <M>q</M> to phi4-mini <Cite n={3} /> with a structured classification
        prompt listing all available domains and requiring a JSON response with <Code>agent</Code> and{" "}
        <Code>confidence</Code> fields. The prompt is ≤ 80 tokens to minimise fill cost. Fallback decisions
        are logged separately, enabling offline analysis of which query types consistently require LLM
        disambiguation.
      </P>

      {/* §4 Action Classification */}
      <SectionNum id="s4" n="4.">Action Classification</SectionNum>
      <P>
        Parallel to domain routing, the brain classifies <em>what the user wants to do</em> — the action type.
        This determines downstream behaviour: whether to trigger reflection, which memory types to inject,
        and how to evaluate the response.
      </P>
      <DataTable
        headers={["Action", "Pattern triggers", "Downstream effect"]}
        rows={[
          ["lookup",   "show me, list all, command for, syntax of",      "No reflection · terse agent eligible"],
          ["build",    "write, create, implement, update, refactor",      "Full reflection if conf < 0.70"],
          ["debug",    "fix, error, broken, troubleshoot, why does",      "Full reflection always"],
          ["explain",  "what is, how does, meaning of, help me understand", "Light reflection"],
          ["compare",  "vs, versus, difference between, better than",    "Light reflection"],
          ["research", "analyze, investigate, summarize, formulate",      "Deep pipeline eligible"],
          ["plan",     "how to, how do I, best practice, walk me through","Light reflection"],
          ["unknown",  "no pattern match (pre-Phase 29)",                 "Slow fallback path — now ≈ 0%"],
        ]}
        caption="Table 1. Action type taxonomy, pattern triggers, and downstream routing effects."
      />
      <P>
        Before Phase 29, approximately 10% of queries returned action = <Code>unknown</Code> because their
        phrasing matched no pattern group. The fix required no model retraining — only pattern coverage.
      </P>
      <Expandable title="Pattern groups added in Phase 29">
        <P>Five regex groups covering 16 previously-unclassified query forms:</P>
        <DataTable
          headers={["Pattern", "Action", "Example"]}
          rows={[
            ["check if / verify that / is it",         "lookup", "check if port 443 is open"],
            ["rewrite / clean up / improve",            "build",  "rewrite this function to be cleaner"],
            ["why is / why would / why does",           "debug",  "why is my SSH connection timing out"],
            ["can you / could you (+ verb)",            "stripped → next verb", "can you create a script"],
            ["give me / show me the / print",           "lookup", "give me the command to flush DNS"],
          ]}
        />
      </Expandable>
      <Note color="#0F766E">
        Pattern gaps matter more than model capability at this scale. The LLM correctly handled these queries
        when they reached it — the bottleneck was the upstream classifier deciding they were unknown.
        Classification failures are infrastructure failures, not model failures.
      </Note>

      {/* §5 Results */}
      <SectionNum id="s5" n="5.">Experimental Results</SectionNum>
      <P>
        All results were measured on the Agentic AI system running phi4-mini (3.8B) via Ollama on an RTX 2050
        (4 GB VRAM), Intel Core i7-12th Gen, 16 GB RAM. The evaluation set consists of 100 manually-labelled
        queries covering all 7 agent domains, with ground-truth routing labels assigned by the author.
      </P>
      <Expandable title="Evaluation methodology">
        <P>
          The 100-query set was constructed to cover representative real-usage patterns: 14–15 queries per
          primary domain plus 10 multi-domain edge cases. Ground truth was assigned by asking "which agent
          should answer this?" — not by inspecting routing decisions. Labels were frozen before any eval run
          to prevent post-hoc bias.
        </P>
        <P>
          Each row in the accuracy chart reflects a distinct system configuration, run against the same frozen
          query set. The ablation row (signal-only, 99%) used a version of the system with the LLM fallback
          path removed entirely, forcing all low-confidence queries through the best-available signal route.
        </P>
      </Expandable>

      <SubSection id="s5-1" n="5.1">Accuracy Progression</SubSection>
      <Figure n="2" caption="Routing accuracy from baseline (keyword-only, 70%) to current state (Phase 25, 97%). The ablation row shows signal-only routing with the LLM fallback removed.">
        <AccuracyChart />
      </Figure>

      <SubSection id="s5-2" n="5.2">Domain Signal Heatmap</SubSection>
      <P>
        The heatmap shows the effective weight <KTex src="w(t, d)" /> for representative keyword groups
        across all six non-coordinator domains. High values (teal, bold) indicate strong domain specificity.
        Off-diagonal non-zero values indicate shared vocabulary — the source of genuine routing ambiguity.
      </P>
      <Figure n="3" caption="Domain signal weight matrix. Rows are keyword groups; columns are agent domains. High off-diagonal weights (e.g. python↔ai_ml, explain↔knowledge) represent true domain overlap.">
        <DomainHeatmap />
      </Figure>

      <SubSection id="s5-3" n="5.3">Confidence Distribution</SubSection>
      <P>
        Figure 4 shows the empirical distribution of routing confidence scores across the evaluation set.
        The bimodal shape — a small low-confidence mass and a larger high-confidence mass — confirms that
        most queries have strong, unambiguous domain signals.
      </P>
      <Figure n="4" caption="Routing confidence distribution over 100-query eval set. Queries below θ = 0.33 fall to LLM fallback (~12% here; ~3% in real sessions with less ambiguous phrasing).">
        <ConfidenceHistogram />
      </Figure>

      <SubSection id="s5-4" n="5.4">Latency Analysis</SubSection>
      <DataTable
        headers={["Path", "Median latency", "P95 latency", "Share of queries"]}
        rows={[
          ["Signal route (conf ≥ θ)",  "< 1 ms",  "< 1 ms",  "~97%"],
          ["LLM fallback (conf < θ)",  "720 ms",  "910 ms",  "~3%"],
          ["Blended average",          "~ 22 ms", "~900 ms", "100%"],
          ["Baseline (LLM-first)",     "750 ms",  "930 ms",  "100%"],
        ]}
        caption="Table 2. Routing latency by path. The blended average reflects the ~3% fallback rate in real sessions."
      />
      <P>
        The blended average latency of ~22 ms represents a <strong>34× improvement</strong> over the baseline
        750 ms, solely from reducing the fraction of queries reaching the LLM. The signal path itself
        contributes negligible latency — bounded by tokenisation and hash-map lookup, not inference.
      </P>

      {/* §6 Limitations */}
      <SectionNum id="s6" n="6.">Limitations</SectionNum>
      <P>
        <strong>Multi-domain queries.</strong> Queries spanning two domains (e.g. "implement a Python script
        to configure a Cisco switch") correctly fall to the LLM fallback, but the fallback picks one domain
        rather than decomposing the query. A deep pipeline that routes sub-questions independently is planned
        but not yet implemented.
      </P>
      <P>
        <strong>Short queries.</strong> Queries of 1–3 tokens rarely clear the confidence threshold regardless
        of domain. "VPN?" or "pytorch?" are unambiguous to a human but score below 0.33 due to the length
        normalisation in Equation (1). A minimum-token bypass — route directly if{" "}
        <KTex src="|q| \leq 2" /> and exactly one domain matches — would address this.
      </P>
      <P>
        <strong>Language drift.</strong> Non-English queries score poorly because the keyword registry is
        English-only. Albanian input, for instance, routes 100% to LLM fallback. Extending the registry
        with multi-language equivalents is feasible but not yet done.
      </P>

      {/* §7 Conclusion */}
      <SectionNum id="s7" n="7.">Conclusion</SectionNum>
      <P>
        QuerySignal demonstrates that deterministic geometric routing can match or exceed LLM-based
        classification on a constrained local system, at a fraction of the latency cost. The confidence
        score is not a statistical approximation — it is a hard signal that is either present or absent.
        When absent, the LLM handles the query correctly; when present, it is not needed.
      </P>
      <P>
        The deepest lesson from this system is architectural: the expensive component (LLM inference)
        should be on the <em>exception path</em>, not the common path. At 97% signal coverage, the LLM
        is only invoked when it genuinely adds value. The system is faster, more deterministic, and no
        less accurate than a pure-LLM routing approach — while using dramatically less compute per query.
        <Cite n={4} />
      </P>

      <References refs={QS_REFS} />
    </article>
  );
}

// ── Other articles ─────────────────────────────────────────────
function ArticleCoherence() {
  return (
    <article>
      <P>
        Coherence is a scalar metric — written <Code>C(t)</Code> — that tracks whether the system's reasoning
        quality is stable, improving, or degrading over time. It's computed continuously and surfaced in the
        dashboard header. A coherence score above 0.80 means the system is operating reliably. Below 0.60
        means something is drifting.
      </P>
      <H2>What C(t) Measures</H2>
      <P>Four signals feed into the coherence composite, each normalised to [0, 1] and combined with fixed weights:</P>
      <DataTable
        headers={["Signal", "Weight", "What it tracks"]}
        rows={[
          ["Routing quality", "0.35", "Weighted agreement between signal routing and LLM routing"],
          ["Calibration",     "0.30", "How well confidence scores predict actual response quality"],
          ["Memory quality",  "0.20", "Average quality score across the active memory store"],
          ["Feedback signal", "0.15", "Proportion of positive vs. negative user ratings"],
        ]}
      />
      <P>
        The formula is: <Code>C(t) = 0.35 × routing + 0.30 × calibration + 0.20 × memory + 0.15 × feedback</Code>.
        When feedback is sparse, the feedback term defaults to 0.75 — a neutral prior.
      </P>
      <H2>Why Routing Agreement Matters</H2>
      <P>
        The signal router and the LLM router are two independent classification systems. When they agree,
        confidence is high. When they disagree (a "conflict"), the query sits at a domain boundary.
        High conflict rate signals that the keyword registry needs updating, or that a query type is genuinely ambiguous.
      </P>
      <CalloutGrid>
        <Callout label="Current C(t)" value="~0.82" color="#0F766E" sub="above 0.80 target" />
        <Callout label="Conflict Rate" value="~6%" color="#15803D" sub="terse agent highest at 87%" />
        <Callout label="Calibration Error" value="low" color="#9A6C00" sub="recovering from eval bias" />
        <Callout label="Feedback Prior" value="0.75" color="#7E3F8F" sub="neutral — awaiting real ratings" />
      </CalloutGrid>
      <H2>The Calibration Problem</H2>
      <P>
        Calibration measures whether the brain's pre-decision confidence score actually predicts response quality.
        After the evaluation run, all agent weights dropped below 1.0 — 291 of 312 calibration samples were
        eval decisions, not real sessions. Weights recover with real usage.
      </P>
      <Note color="#0F766E">
        Calibration is the most important signal in C(t). A system can have high routing accuracy but poor
        calibration — meaning it routes correctly but doesn't know when it's uncertain. That's fragile.
      </Note>
    </article>
  );
}

function ArticleMemory() {
  return (
    <article>
      <P>
        The memory system stores every interaction as a typed semantic entry, retrieves relevant past knowledge
        at inference time, and manages quality degradation over time.
      </P>
      <H2>Memory Types</H2>
      <DataTable
        headers={["Type", "Written by", "Used for"]}
        rows={[
          ["episodic",   "Every response",         "Past experience retrieval — grows fastest"],
          ["procedural", "Task completions",        "Step-by-step execution traces"],
          ["lesson",     "Knowledge agent",         "Conceptual explanations and study material"],
          ["code",       "Python / Blazor agents",  "Reusable code patterns"],
          ["reflection", "Reflection pass (~15%)",  "Self-critique and rewrite records"],
          ["failure",    "Failure miner",           "Annotated bad decisions"],
          ["seed",       "Startup",                 "Initial knowledge base entries"],
        ]}
      />
      <H2>FAISS + LRU Cache</H2>
      <P>
        The FAISS backend uses <Code>IndexIDMap</Code> wrapping <Code>IndexFlatIP</Code> (inner product on
        normalised vectors ≡ cosine similarity). It rebuilds from the database on startup — at 592 entries,
        this takes ~10 ms. A 512-slot LRU cache wraps the query function; cache hit rate in real sessions: ~40%.
      </P>
      <CalloutGrid>
        <Callout label="Total Entries" value="592"    color="#1E5A8A" sub="post-consolidation" />
        <Callout label="Dedup Removed" value="236"    color="#15803D" sub="28.5% — cos > 0.93" />
        <Callout label="LRU Speedup"   value="52×"    color="#9A6C00" sub="on cache hit" />
        <Callout label="Prune at"      value="q < 0.55" color="#B42318" sub="quality + never recalled" />
      </CalloutGrid>
      <H2>Quality Lifecycle</H2>
      <P>
        A memory's quality score starts at the response performance value (0.90 thumbs-up · 0.25 thumbs-down ·
        0.75 non-reflected · 0.55 conflict). It decays on retrieval without feedback and recovers in
        high-quality sessions. Entries below <Code>q = 0.55</Code> that have never been recalled are marked prunable.
      </P>
      <Note>Episodic memories will dominate retrieval at scale — every response writes one. Recommended cap: max 3 episodic results per query injection.</Note>
    </article>
  );
}

function ArticleReflection() {
  return (
    <article>
      <P>
        Reflection is the system's self-correction mechanism. After generating a response it evaluates whether
        the answer is good enough — and if not, rewrites it. Full reflection adds 30–55 seconds. Triage
        introduced in Phase 19 decides which queries deserve it.
      </P>
      <H2>Three Levels</H2>
      <DataTable
        headers={["Level", "When", "What it does", "Added latency"]}
        rows={[
          ["none",  "terse, lookup, simple factual",                "Response returned as-is",                                       "0 s"],
          ["light", "explain, plan — moderate confidence",          "Grounded eval score only, no rewrite",                          "~3 s"],
          ["full",  "build, debug — low confidence or high regret", "Grounded eval + LLM critique + rewrite (≤ 3 iterations)",       "30–55 s"],
        ]}
      />
      <H2>Impact</H2>
      <CalloutGrid>
        <Callout label="Full Reflection Rate" value="15–20%" color="#0F766E" sub="was 58% before triage" />
        <Callout label="Latency Saved"        value="~35 s"  color="#15803D" sub="per skipped reflection" />
        <Callout label="Terse Agent"          value="0%"     color="#9A6C00" sub="reflection disabled entirely" />
        <Callout label="Trigger"              value="build+debug" color="#7E3F8F" sub="+ conf < 0.70" />
      </CalloutGrid>
      <H2>The Rewrite Loop</H2>
      <P>
        When full reflection fires, the critic (also phi4-mini) receives the original query, the draft response,
        and a structured critique prompt. It identifies specific weaknesses; the agent rewrites using the critique
        as additional context. This loops up to 3 times or until the grounded eval score exceeds 0.80.
      </P>
      <Note color="#15803D">
        The biggest latency win was disabling reflection on the terse agent entirely. A 3-iteration rewrite
        loop on "what's the command to list open ports?" is waste by design.
      </Note>
    </article>
  );
}

// ── Proposition / Remark primitives ───────────────────────────
function Proposition({ n, children }) {
  return (
    <div style={{ background: T.bg, border: `1px solid ${T.border}`, borderLeft: "3px solid #7E3F8F", borderRadius: 6, padding: "16px 22px", margin: "22px 0" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "#7E3F8F", marginBottom: 12, fontFamily: fUI, letterSpacing: "0.1em", textTransform: "uppercase" }}>
        Proposition {n}
      </div>
      <div style={{ fontSize: 14.5, color: "#5C4030", lineHeight: 1.85, fontFamily: fBody }}>{children}</div>
    </div>
  );
}
function Remark({ children }) {
  return (
    <div style={{ background: `#9A6C0008`, borderLeft: "3px solid #9A6C00", padding: "12px 18px", fontSize: 14, color: "#5C4030", lineHeight: 1.8, margin: "22px 0", fontFamily: fBody }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "#9A6C00", letterSpacing: "0.1em", textTransform: "uppercase", fontFamily: fUI, marginRight: 8 }}>Example</span>
      {children}
    </div>
  );
}
function Boxed({ children }) {
  return (
    <div style={{ background: T.bg, border: `2px solid #0F766E66`, borderRadius: 8, padding: "20px 28px", margin: "24px 0", overflowX: "auto" }}>
      {children}
    </div>
  );
}

// ── Methodology TOC ────────────────────────────────────────────
const METH_TOC = [
  { id: "m-overview",  label: "Overview",                  level: 1 },
  { id: "m-norm",      label: "1. Query Normalisation",    level: 1 },
  { id: "m-norm-conf", label: "1.1 Domain Confidence",     level: 2 },
  { id: "m-norm-shape","label": "1.2 Answer Shape",        level: 2 },
  { id: "m-norm-verb", label: "1.3 Verbosity",             level: 2 },
  { id: "m-route",     label: "2. Routing Decision",       level: 1 },
  { id: "m-route-props","label": "2.1 Failure Propositions", level: 2 },
  { id: "m-route-regret","label": "2.2 Regret",            level: 2 },
  { id: "m-learn",     label: "3. Learning Kernel",        level: 1 },
  { id: "m-mem",       label: "4. Memory Retrieval",       level: 1 },
  { id: "m-reflect",   label: "5. Reflection Triage",      level: 1 },
  { id: "m-cohere",    label: "6. Coherence Functional",   level: 1 },
  { id: "m-dual",      label: "7. Dual-Trajectory Eval",   level: 1 },
  { id: "m-summary",   label: "Summary Table",             level: 1 },
];

// ── Methodology article ────────────────────────────────────────
function ArticleMethodology() {
  return (
    <article>
      <div id="m-overview" style={{ scrollMarginTop: 16 }}>
        <P>
          Complete mathematical derivations for the five interlocking components of the system.
          Every formula has a direct correspondence to executable code — theoretical claims are
          falsifiable and reproducible. The pipeline is:
        </P>
        <KTexBlock src="q \;\xrightarrow{\;\mathcal{N}\;}\; \sigma \;\xrightarrow{\;\mathcal{R}\;}\; a^* \;\xrightarrow{\;\text{agent}\;}\; r_0 \;\xrightarrow{\;\text{reflect}\;}\; r^* \;\xrightarrow{\;\text{learn}\;}\; w'" />
        <P>
          where <M>q</M> is the raw query, <M>σ</M> the normalised signal, <M>a*</M> the selected agent,
          <M>r₀</M> the raw response, <M>r*</M> the (optionally refined) response, and <M>w'</M> the
          updated weight vector. The only probabilistic elements are the LLM agent calls and the
          optional LLM fallback in routing.
        </P>
      </div>

      {/* §1 Query Normalisation */}
      <SectionNum id="m-norm" n="1." color="#0F766E">Query Normalisation</SectionNum>
      <P>
        The normalisation operator <M>𝒩</M> maps a raw query to a four-dimensional signal capturing
        domain, confidence, answer shape, and verbosity — a strictly richer space than the action verb alone.
      </P>

      <SubSection id="m-norm-conf" n="1.1">Domain Confidence Scoring</SubSection>
      <Definition n="1" title="Domain Confidence">
        Let <M>H_d(q)</M> be the number of keywords from domain <M>d</M>'s registry that match query <M>q</M>
        (word-boundary guard for tokens ≤ 4 chars, plain substring for longer tokens):
        <KTexBlock n="1" src="c_d(q) \;=\; \min\!\bigl(1.0,\;\; H_d(q) \times 0.35\bigr)" />
        One keyword hit → <M>c = 0.35</M> (above routing threshold 0.30). Three hits saturate at <M>c = 1.0</M>.
      </Definition>
      <Remark>
        Query: <em>"Explain the difference between TCP and UDP."</em>{" "}
        Both <code style={{ fontFamily: fMono, fontSize: 12 }}>tcp</code> and <code style={{ fontFamily: fMono, fontSize: 12 }}>udp</code> match
        (word-boundary guard, |tcp|=3). <M>H_net = 2</M>, so <M>c = 0.70 &gt; 0.30</M> → routes to{" "}
        <code style={{ fontFamily: fMono, fontSize: 12 }}>it_networking</code>. Under action-first routing,
        "explain" fires first and routes to <code style={{ fontFamily: fMono, fontSize: 12 }}>knowledge_learning</code> — domain is discarded.
      </Remark>

      <SubSection id="m-norm-shape" n="1.2">Answer Shape Classification</SubSection>
      <Definition n="2" title="Answer Shape Function">
        Priority-ordered predicate function (<M>q_l</M> = lowercased query, <M>n</M> = word count):
        <KTexBlock src="\mathrm{shape}(q) = \begin{cases} \textit{factual} & n \leq 10 \land \phi_f(q_l) \\ \textit{code} & \phi_b(q_l) \land \phi_a(q_l) \\ \textit{debug} & \phi_d(q_l) \\ \textit{procedural} & \phi_p(q_l) \\ \textit{comparison} & \phi_c(q_l) \\ \textit{explanation} & \text{otherwise} \end{cases}" />
        The two-condition guard on <em>code</em> — build verb <M>φ_b</M> AND artifact noun <M>φ_a</M> — prevents
        "Create a plan for my startup" from routing to the code agent.
      </Definition>
      <Remark>
        "Write a FastAPI endpoint that accepts a JSON body." → <M>φ_b</M>: "write" ✓ · <M>φ_a</M>: "endpoint" ✓ → <strong>code</strong>.{" "}
        "Create a roadmap for deploying our app." → <M>φ_b</M>: "create" ✓ · <M>φ_a</M>: no artifact noun ✗ → falls through to <strong>explanation</strong>.
      </Remark>

      <SubSection id="m-norm-verb" n="1.3">Verbosity & Normalisation Operator</SubSection>
      <Definition n="3" title="Verbosity Function">
        <KTexBlock n="2" src="\mathrm{verbosity}(q) = \begin{cases} \textit{terse} & n \leq 6 \\ \textit{detailed} & n \geq 25 \\ \textit{normal} & \text{otherwise} \end{cases}" />
        Threshold ≤ 6 (not ≤ 8): tightened after 8-token explanation queries were falsely routed to terse.
      </Definition>
      <Definition n="4" title="Normalisation Operator">
        <KTexBlock n="3" src="\mathcal{N}(q) = \bigl(d^*(q),\; c_{d^*}(q),\; \mathrm{shape}(q),\; \mathrm{verbosity}(q)\bigr)" />
        Pure function — no side effects, no LLM calls, <KTex src="O(|K|) \approx O(200)" /> keywords,
        under 1 ms wall-clock.
      </Definition>
      <Remark>
        Query: "What port does HTTPS use?" (<M>n = 6</M>) →
        domain <em>networking</em> (<code style={{ fontFamily: fMono, fontSize: 12 }}>https</code> matches, <M>c = 0.35</M>) ·
        shape <em>factual</em> (<M>n ≤ 10</M> + "what port" pattern) ·
        verbosity <em>terse</em> (<M>n = 6</M>) →
        signal <KTex src="\sigma = (\textit{networking},\; 0.35,\; \textit{factual},\; \textit{terse})" />.
      </Remark>

      {/* §2 Routing Decision */}
      <SectionNum id="m-route" n="2." color="#9A6C00">Routing Decision</SectionNum>
      <Definition n="5" title="Priority Routing Function">
        Given signal <KTex src="\sigma = (d, c, s, v)" /> and detected action <M>x</M>, first match wins:
        <KTexBlock n="4" src="\mathcal{R}(\sigma, x) = \begin{cases} a_{\text{terse}} & x = \textit{lookup} \\ a_{\text{terse}} & s = \textit{factual} \\ a_{\text{terse}} & v = \textit{terse} \land s = \textit{explanation} \land d = \textit{general} \\ \text{DOMAIN\_TO\_AGENT}(d) & c > 0.30 \\ \mathcal{R}_{\text{LLM}}(q) & \text{otherwise} \end{cases}" />
      </Definition>
      <DataTable
        headers={["Rule", "When fires", "Why"]}
        rows={[
          ["1 — Lookup hard-override",  "action = 'lookup' or 'one-liner'",     "Confidence forced to 1.0, no reflection"],
          ["2 — Factual shape",         "shape = factual",                       "Fix for terse invisibility — factual queries are first-class"],
          ["3 — Short generic explain", "n ≤ 6, no domain, explanation shape",   "Conjunction d=general keeps 'Explain VPNs' out"],
          ["4 — Domain routing",        "c > 0.30 (one keyword hit sufficient)", "Fix for explain-bleed — domain is primary signal"],
          ["5 — LLM fallback",          "all above miss",                        "Confidence penalised 0.75× to reflect higher uncertainty"],
        ]}
        caption="Table 1. Priority routing rules evaluated top-to-bottom, first match wins."
      />

      <SubSection id="m-route-props" n="2.1">Failure Propositions</SubSection>
      <P>Under legacy action-first routing <KTex src="\mathcal{R}'(q) = \mathrm{verb\_map}(\mathrm{detect\_verb}(q))" />, two failures are structurally unavoidable:</P>
      <Proposition n="1">
        <strong>Explain-bleed is irreducible under <KTex src="\mathcal{R}'" />.</strong>{" "}
        For any two queries <KTex src="q_1, q_2" /> with <KTex src="\mathrm{detect\_verb}(q_1) = \mathrm{detect\_verb}(q_2) = \textit{explain}" />,
        we have <KTex src="\mathcal{R}'(q_1) = \mathcal{R}'(q_2)" /> regardless of domain content.
        Adding keywords to <KTex src="K_d" /> cannot change this because the verb check occurs before domain scoring.
      </Proposition>
      <Proposition n="2">
        <strong>Terse invisibility is irreducible under <KTex src="\mathcal{R}'" />.</strong>{" "}
        For any query with <KTex src="|q|_w \leq 6" />,{" "}
        <KTex src="\mathcal{R}'(q) \neq a_{\text{terse}}" /> unless <M>q</M> contains a lookup verb.
        Query length is not a dimension of <KTex src="\mathcal{R}'" />.
      </Proposition>
      <Note color="#7E3F8F">
        Both propositions follow from the same root cause: <KTex src="\mathcal{R}'" /> is a function of one variable
        (the verb), so any information not in the verb is lost. <KTex src="\mathcal{R} \circ \mathcal{N}" /> is a
        function of four variables — the same information cannot be lost.
      </Note>

      <SubSection id="m-route-regret" n="2.2">Routing Regret</SubSection>
      <Definition n="6" title="Routing Regret">
        For chosen agent <M>a*</M> and competitor set <KTex src="C = \{a \in \mathcal{A} : a \neq a^*,\; a \neq a_{\text{know}}\}" />:
        <KTexBlock n="5" src="r(a^*, C) = \max\!\Bigl(0,\;\; \max_{a \in C} w(a) - w(a^*)\Bigr)" />
        Zero when no competitor outweighs the chosen agent. Regret &gt; 0.3 indicates a plausible alternative existed.
        Knowledge-learning excluded from <M>C</M> — it fires on generic verbs and is not a meaningful competitor.
      </Definition>
      <Remark>
        System routes to <code style={{ fontFamily: fMono, fontSize: 12 }}>python_dev</code> (<M>w = 0.74</M>) but{" "}
        <code style={{ fontFamily: fMono, fontSize: 12 }}>it_networking</code> has <M>w = 0.82</M>. Regret <M>r = 0.82 − 0.74 = 0.08</M>.
        Learning signal (§3): <M>L = p − 0.5r = 0.80 − 0.04 = 0.76</M>. The weight update is slightly lower than
        raw performance, reflecting mild opportunity cost.
      </Remark>

      {/* §3 Learning Kernel */}
      <SectionNum id="m-learn" n="3." color="#1E5A8A">Adaptive Learning Kernel</SectionNum>
      <P>
        All weight changes flow through a single function <code style={{ fontFamily: fMono, fontSize: 12 }}>apply_learning_update</code> —
        no other code path modifies agent weights. Six steps, applied in order:
      </P>
      <DataTable
        headers={["Step", "Formula", "Purpose"]}
        rows={[
          ["A — Calibration",  "ε = c̄ − p̄  (EMA, ≥5 samples)",              "Track over/under-confidence per agent"],
          ["B — Learning signal", "L = p − 0.5r",                              "Penalise opportunity cost of routing"],
          ["C — Instability",  "I = 0.4r + 0.4|ε| + 0.2σ²_w",               "Composite uncertainty signal [0,1]"],
          ["D — Adaptive rate","α(I) = 0.05·max(0.1, 1−I)  if I<0.60",       "Slow learning under instability, freeze at I≥0.80"],
          ["E — Weight update","Δ = clip(α(L−w), ±0.02),  w' = clip(w+Δ, 0.1, 3.0)", "Double-clipped for stability"],
          ["F — Decay",        "w_a' ← w_a ± 0.001  for all a≠a*",           "Unselected agents drift toward w=1.0"],
        ]}
        caption="Table 2. Six steps of the adaptive learning kernel, applied per decision."
      />
      <Boxed>
        <div style={{ textAlign: "center", fontSize: 13, color: T.muted, fontFamily: fUI, marginBottom: 12 }}>Complete learning update (boxed summary)</div>
        <KTexBlock src="I = 0.4r + 0.4|\varepsilon| + 0.2\sigma^2_w, \quad L = p - 0.5r" />
        <KTexBlock src="w' = \mathrm{clip}\!\bigl(w + \mathrm{clip}\!\bigl(\alpha(I)(L-w),\,-0.02,\,+0.02\bigr),\;0.1,\;3.0\bigr)" />
      </Boxed>
      <Remark>
        <KTex src="w = 0.95,\; L = 0.76,\; I = 0.062" /> →
        <KTex src="\alpha = 0.05 \times (1 - 0.062) = 0.0469" /> →
        <KTex src="\Delta_{\text{raw}} = 0.0469 \times (0.76 - 0.95) = -0.0089" /> →
        <KTex src="\Delta = -0.0089" /> (within ±0.02) →
        <KTex src="w' = \mathrm{clip}(0.95 - 0.0089,\; 0.1,\; 3.0) = 0.9411" />.
        A good response with mild regret pulls the weight slightly down.
      </Remark>
      <Note color="#1E5A8A">
        The double clipping serves different purposes. The ±0.02 clip on Δ prevents any single event from
        causing a large jump. The [0.1, 3.0] clip on w provides hard safety rails — no agent can be
        permanently disabled or receive unbounded priority. The system is Lyapunov-stable in the weight space.
      </Note>

      {/* §4 Memory Retrieval */}
      <SectionNum id="m-mem" n="4." color="#0F766E">Memory Retrieval</SectionNum>
      <Definition n="7" title="Retrieval Score">
        Every memory <M>m</M> and query <M>q</M> are embedded by nomic-embed-text into <KTex src="\mathbb{R}^{768}" />,
        L2-normalised (cosine → dot product). The composite score:
        <KTexBlock n="6" src="s(q, m) = \underbrace{(\mathbf{e}_q \cdot \mathbf{e}_m)}_{\text{cosine}} \cdot \underbrace{q_m}_{\text{quality}} \cdot \underbrace{\tau_{\text{type}(m)}}_{\text{type weight}} \cdot \underbrace{f(\Delta t_m)}_{\text{freshness}}" />
      </Definition>
      <DataTable
        headers={["Type", "τ", "Rationale"]}
        rows={[
          ["reflection", "1.4", "Grounded quality signal — most actionable"],
          ["failure",    "1.3", "Negative examples prevent repeat mistakes"],
          ["code",       "1.2", "Executable examples are directly reusable"],
          ["procedural", "1.2", "Step-by-step patterns generalise across queries"],
          ["lesson",     "1.1", "Structured explanation — moderate reuse"],
          ["episodic",   "1.0", "Conversation history (baseline)"],
          ["seed",       "0.8", "Auto-generated eval memories — yield to real ones"],
        ]}
        caption="Table 3. Type weights τ in the retrieval score."
      />
      <P>Freshness decay with half-life 30 days:</P>
      <KTexBlock n="7" src="f(\Delta t) = \max\!\bigl(0.05,\;\; e^{-\Delta t \cdot \ln 2 / 30}\bigr)" />
      <Remark>
        Reflection memory, 1 day old, quality 0.90, cosine 0.72:
        <KTex src="s = 0.72 \times 0.90 \times 1.4 \times e^{-0.023} \approx 0.884" />.{" "}
        Seed memory, 60 days old, quality 0.80, same cosine:
        <KTex src="s = 0.72 \times 0.80 \times 0.8 \times 0.25 \approx 0.115" />.
        The reflection memory outscores the seed by <strong>7.7×</strong> at identical semantic similarity,
        due to type weight and freshness.
      </Remark>
      <P>
        Quality feedback propagates back via retrieval audit: each retrieved memory gains <KTex src="\delta_f = +0.03" /> (👍)
        or <KTex src="\delta_f = -0.05" /> (👎). The asymmetry <KTex src="|\delta_-| > |\delta_+|" /> ensures
        consistently mis-retrieved memories descend below the prune threshold naturally.
        Prune criterion: <KTex src="q_m < 0.55 \;\land\; \mathrm{use\_count}(m) = 0" />.
      </P>

      {/* §5 Reflection Triage */}
      <SectionNum id="m-reflect" n="5." color="#15803D">Reflection Triage</SectionNum>
      <Definition n="8" title="Reflection Level">
        <KTexBlock n="8" src="\mathrm{level}(x, a, c, \xi) = \begin{cases} \mathrm{none} & x \in \{\textit{explain, compare, plan, lookup}\} \\ \mathrm{full} & x = \textit{debug} \land a \in \mathcal{A}_{\text{code}} \\ \mathrm{full} & \xi = \textit{compound} \land a \in \mathcal{A}_{\text{code}} \\ \mathrm{full} & c < 0.55 \land a \in \mathcal{A}_{\text{code}} \\ \mathrm{light} & x = \textit{build} \land c \geq 0.55 \land a \in \mathcal{A}_{\text{code}} \\ \mathrm{none} & \text{otherwise} \end{cases}" />
        where <KTex src="\mathcal{A}_{\text{code}} = \{a_{\text{py}}, a_{\text{blz}}\}" />.
      </Definition>
      <P>
        Two runtime escalations: (1) <strong>Confidence gate</strong> — if <KTex src="c < 0.40" />,
        promote to full regardless of triage. (2) <strong>Instability gate</strong> — if <KTex src="I > 0.60" />,
        promote none → light.
      </P>
      <P>
        Contradiction escalation: if the response negates a high-similarity past memory
        (<KTex src="\cos \geq 0.78" />, overlap ≥ 20%, and 22 negation patterns present), escalate to full.
        Zero LLM calls — purely heuristic, fires only when all three conditions hold simultaneously.
      </P>
      <Note color="#15803D">
        Before Phase 19 (triage), reflection fired on 58% of decisions (166/283), adding ~25–30 s per event.
        After triage, full-reflection rate dropped to ~15–20% with light reflection covering an additional ~10–15%.
      </Note>

      {/* §6 Coherence Functional */}
      <SectionNum id="m-cohere" n="6." color="#7E3F8F">Coherence Functional</SectionNum>
      <P>
        A routing accuracy metric is snapshot-in-time. The coherence functional <KTex src="C(t)" /> provides
        a continuous, composite measure of system self-consistency over the rolling 20-decision window <KTex src="W_t" />:
      </P>
      <KTexBlock n="9" src="C_{\text{routing}}(t) = 1 - \frac{\sum_{i \in W_t} \mathbf{1}[\text{conflict}_i]}{|W_t|}" />
      <KTexBlock n="10" src="C_{\text{calib}}(t) = 1 - \frac{1}{|\mathcal{A}|} \sum_{a \in \mathcal{A}} |\varepsilon_{\text{cal}}(a, t)|" />
      <KTexBlock n="11" src="C_{\text{quality}}(t) = \frac{1}{|W_t|} \sum_{i \in W_t} \hat{p}_i \quad (\hat{p}_i = 0.75 \;\text{no conflict},\; 0.55 \;\text{conflict})" />
      <Boxed>
        <KTexBlock src="C(t) = \tfrac{1}{3}\bigl[C_{\text{routing}}(t) + C_{\text{calib}}(t) + C_{\text{quality}}(t)\bigr]" />
        <div style={{ textAlign: "center", fontSize: 12, color: T.muted, fontFamily: fUI }}>C(t) ∈ [0,1] · coherent when C(t) &gt; 0.75</div>
      </Boxed>
      <Remark>
        20-decision window: conflict_rate = 0.20 → <KTex src="C_{\text{routing}} = 0.80" />,
        mean |ε| = 0.12 → <KTex src="C_{\text{calib}} = 0.88" />,
        mean p̂ = 0.71 → <KTex src="C_{\text{quality}} = 0.71" />.
        Result: <KTex src="C(t) = (0.80 + 0.88 + 0.71)/3 = 0.797" /> — system is coherent (green badge).
      </Remark>

      {/* §7 Dual-Trajectory Evaluation */}
      <SectionNum id="m-dual" n="7." color="#C48808">Dual-Trajectory Evaluation</SectionNum>
      <P>
        For code and debug tasks handled by <code style={{ fontFamily: fMono, fontSize: 12 }}>python_dev</code> or{" "}
        <code style={{ fontFamily: fMono, fontSize: 12 }}>dotnet_dev</code>, two candidates are generated and a
        critic picks the better one. Zero overhead for non-code queries.
      </P>
      <Definition n="9" title="Code Task Gate">
        <KTexBlock src="\mathrm{is\_code}(q) = \mathbf{1}\bigl[\mathrm{shape}(\mathcal{N}(q)) \in \{\textit{code},\;\textit{debug}\}\bigr]" />
        If 0, the agent is invoked once and dual-trajectory is bypassed entirely.
      </Definition>
      <P>When <KTex src="\mathrm{is\_code}(q) = 1" />:</P>
      <DataTable
        headers={["Candidate", "Inputs", "Notes"]}
        rows={[
          ["A — Full agent",  "Memory context + tools + system prompt",     "Standard path — reads episodic/procedural memory"],
          ["B — CoT LLM",    "System prompt + chain-of-thought suffix",      "No memory, no tools — step-by-step reasoning before code"],
          ["Critic",         "q, A, B → {A, B} + one-line reason",           "Short LLM call — much cheaper than full reflection"],
        ]}
        caption="Table 4. Dual-trajectory generation and critic selection."
      />
      <Note color="#C48808">
        When B wins, memory still saves candidate A — it's a real agent attempt with valid training signal.
        Total overhead for a code task: one extra LLM call (B) + one short critic call, both smaller than a
        full reflection cycle. This is a width-1 instance of the GRAM framework.
      </Note>

      {/* Summary Table */}
      <SectionNum id="m-summary" n="" color="#9A7A60">Formula Reference</SectionNum>
      <DataTable
        headers={["Component", "Formula"]}
        rows={[
          ["Domain confidence",   "c_d(q) = min(1, H_d(q) × 0.35)"],
          ["Routing threshold",   "c > 0.30 → signal route (one keyword hit sufficient)"],
          ["Learning signal",     "L = p − 0.5r"],
          ["Instability",         "I = 0.4r + 0.4|ε_cal| + 0.2σ²_w"],
          ["Adaptive rate",       "α(I) = 0.05·max(0.1, 1−I)  if I<0.60, else 0.025 or 0"],
          ["Weight update",       "Δ = clip(α(L−w), ±0.02);  w' = clip(w+Δ, 0.1, 3.0)"],
          ["Calibration bias",    "ε = c̄ − p̄  (EMA over ≥5 samples)"],
          ["Retrieval score",     "s(q,m) = (e_q·e_m) · q_m · τ_type · exp(−Δt·ln2/30)"],
          ["Freshness floor",     "f(Δt) = max(0.05, exp(−Δt·ln2/30))"],
          ["Quality feedback",    "q_m ← clip(q_m + δ_f, 0, 1);  δ_f = +0.03 or −0.05"],
          ["Coherence functional","C(t) = ⅓[C_routing + C_calib + C_quality];  coherent if C > 0.75"],
        ]}
        caption="Table 5. All 11 core formulas across the five pipeline components."
      />
    </article>
  );
}

// ── Article registry ───────────────────────────────────────────
const ARTICLES = [
  { id: "querysignal",  title: "QuerySignal",   subtitle: "Deterministic intent routing for local agentic systems", tag: "Routing",      color: "#0F766E", icon: "◉", Content: ArticleQuerySignal,  toc: QS_TOC   },
  { id: "methodology",  title: "Methodology",   subtitle: "Mathematical derivations, worked examples, and formal proofs",    tag: "Ch. 2",        color: "#7E3F8F", icon: "∂", Content: ArticleMethodology, toc: METH_TOC },
  { id: "coherence",    title: "Coherence",     subtitle: "Measuring system stability over time",                   tag: "Intelligence", color: "#9A6C00", icon: "Ψ", Content: ArticleCoherence,    toc: null     },
  { id: "memory",       title: "Memory",        subtitle: "FAISS, LRU cache, dedup, and quality lifecycle",         tag: "Memory",       color: "#1E5A8A", icon: "⊞", Content: ArticleMemory,       toc: null     },
  { id: "reflection",   title: "Reflection",    subtitle: "Triage, self-critique, and rewrite loops",               tag: "Learning",     color: "#15803D", icon: "⊕", Content: ArticleReflection,   toc: null     },
];

// ── Main component ─────────────────────────────────────────────
export default function ResearchTab({ activeDoc }) {
  const article = ARTICLES.find(a => a.id === activeDoc) || ARTICLES[0];
  const [activeSection, setActiveSection] = useState("s1");
  const articleRef = useRef(null);

  const handleScroll = useCallback(() => {
    if (!articleRef.current || !article.toc) return;
    const containerRect = articleRef.current.getBoundingClientRect();
    const threshold = containerRect.top + 160;
    let current = article.toc[0].id;
    for (const { id } of article.toc) {
      const el = document.getElementById(id);
      if (el && el.getBoundingClientRect().top <= threshold) current = id;
    }
    setActiveSection(current);
  }, [article.toc]);

  // The page may scroll in an ancestor container (shared content column),
  // so listen in capture phase to catch scrolls anywhere.
  useEffect(() => {
    document.addEventListener("scroll", handleScroll, true);
    return () => document.removeEventListener("scroll", handleScroll, true);
  }, [handleScroll]);

  const { Content } = article;

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Scrollable article column */}
      <div ref={articleRef} onScroll={handleScroll} style={{ flex: 1, overflowY: "auto", background: T.bg }}>
        {/* Article header strip */}
        <div style={{ borderBottom: `1px solid ${T.border}`, background: T.surface }}>
          <div style={{ maxWidth: ARTICLE_MAX, margin: "0 auto", padding: "28px 32px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <span style={{ fontSize: 9, fontWeight: 700, padding: "3px 9px", borderRadius: 3, background: `${article.color}16`, color: article.color, border: `1px solid ${article.color}38`, letterSpacing: "0.08em", textTransform: "uppercase", fontFamily: fUI }}>{article.tag}</span>
              <span style={{ fontSize: 11.5, color: T.muted, fontFamily: fUI }}>Agentic AI · Jun 2026</span>
            </div>
            <h1 style={{ fontSize: 33, fontWeight: 600, color: T.text, letterSpacing: "0.01em", marginBottom: 10, lineHeight: 1.18, fontFamily: "'Cormorant Garamond', Georgia, serif" }}>{article.title}</h1>
            <p style={{ fontSize: 15.5, color: T.muted, margin: 0, fontFamily: fUI, lineHeight: 1.5 }}>{article.subtitle}</p>
          </div>
        </div>
        {/* Article body — centered */}
        <div style={{ maxWidth: ARTICLE_MAX, margin: "0 auto", padding: "40px 32px 88px" }}>
          <Content />
        </div>
      </div>

      {/* TOC sidebar — only for articles with toc data */}
      {article.toc && (
        <div style={{ width: 210, borderLeft: `1px solid ${T.border}`, flexShrink: 0, overflowY: "auto", background: T.surface }}>
          <TOC items={article.toc} activeId={activeSection} />
        </div>
      )}
    </div>
  );
}
