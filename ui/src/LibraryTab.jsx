import { useEffect, useRef, useState, useCallback } from "react";
import { T, LUX, FONT_DISPLAY } from "./theme";
import { PageHeader } from "./ObsShared";

const API = "http://localhost:8000";

// Library — the persistent knowledge layer. Documents are presented as
// objects in a collection, never as chunks or embeddings. Status language
// is "Reading… / Read", and the only verbs are Add, Move, Remove.

const DEFAULT_COLLECTIONS = ["Strategy", "Research", "Product", "Personal", "Archive"];

const TYPE_META = {
  pdf:  { label: "PDF",      tint: "#B42318" },
  md:   { label: "Markdown", tint: "#9A6C00" },
  txt:  { label: "Text",     tint: "#5C4030" },
  csv:  { label: "Data",     tint: "#15803D" },
  json: { label: "Data",     tint: "#15803D" },
  yaml: { label: "Config",   tint: "#0F766E" },
  yml:  { label: "Config",   tint: "#0F766E" },
  html: { label: "Web",      tint: "#C2410C" },
  css:  { label: "Web",      tint: "#C2410C" },
};
const CODE_EXT = new Set(["py", "js", "ts", "jsx", "tsx", "sh", "sql", "toml", "cfg", "conf", "rst"]);

function typeOf(filename) {
  const ext = (filename.split(".").pop() || "").toLowerCase();
  if (TYPE_META[ext]) return { ext, ...TYPE_META[ext] };
  if (CODE_EXT.has(ext)) return { ext, label: "Code", tint: "#1E5A8A" };
  return { ext, label: "Document", tint: "#5C4030" };
}

function prettyTitle(filename) {
  return filename.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim() || filename;
}

function prettyDate(iso) {
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

function readLength(chars) {
  if (!chars) return null;
  const min = Math.max(1, Math.round(chars / 1200));
  return min >= 60 ? `${Math.round(min / 60)}h read` : `${min} min read`;
}

// ── Document card ─────────────────────────────────────────────
function DocCard({ doc, collections, onMove, onRemove }) {
  const [menu, setMenu] = useState(false);
  const ref = useRef(null);
  const t = typeOf(doc.filename);

  useEffect(() => {
    if (!menu) return;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setMenu(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menu]);

  const reading = doc.status === "reading";

  return (
    <div className="lib-card" style={{
      position: "relative",
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 14, padding: "18px 18px 14px",
      display: "flex", flexDirection: "column", gap: 12,
      transition: "box-shadow .2s ease, transform .2s ease, border-color .2s ease",
      boxShadow: LUX.shadowSm,
    }}>
      {/* Emblem */}
      <div style={{
        width: 46, height: 58, borderRadius: 8, flexShrink: 0,
        background: `linear-gradient(160deg, #FCFAF7, ${T.surface2})`,
        border: `1px solid ${T.border}`,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.7), 0 1px 2px rgba(72,52,28,0.08)",
        display: "flex", alignItems: "center", justifyContent: "center",
        position: "relative",
      }}>
        <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.05em", color: t.tint }}>
          {t.ext.toUpperCase().slice(0, 4)}
        </span>
        <span style={{
          position: "absolute", top: 0, right: 0, width: 12, height: 12,
          background: T.surface2, borderLeft: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}`,
          borderRadius: "0 8px 0 6px",
        }} />
      </div>

      {/* Title + meta */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div title={doc.filename} style={{
          fontSize: 14, fontWeight: 600, color: T.text, lineHeight: 1.35,
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          overflow: "hidden", textTransform: "capitalize",
        }}>
          {prettyTitle(doc.filename)}
        </div>
        <div style={{ fontSize: 11, color: T.muted, marginTop: 5 }}>
          {t.label}
          {doc.added ? ` · ${prettyDate(doc.added)}` : ""}
          {readLength(doc.chars) ? ` · ${readLength(doc.chars)}` : ""}
        </div>
      </div>

      {/* Status + menu */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {reading ? (
          <span style={{ fontSize: 11, color: T.accent2, fontWeight: 600, animation: "livePulse 1.4s ease-in-out infinite" }}>
            Reading…
          </span>
        ) : doc.status === "error" ? (
          <span style={{ fontSize: 11, color: T.error, fontWeight: 600 }}>Couldn't read</span>
        ) : (
          <span style={{ fontSize: 11, color: T.success, fontWeight: 600 }}>✓ Read</span>
        )}
        <div ref={ref} style={{ marginLeft: "auto", position: "relative" }}>
          <button onClick={() => setMenu(m => !m)} className="nav-btn" style={{
            border: "none", background: "transparent", cursor: "pointer",
            color: T.muted, fontSize: 15, lineHeight: 1, padding: "2px 7px",
            borderRadius: 6, fontFamily: "inherit",
          }}>⋯</button>
          {menu && (
            <div style={{
              position: "absolute", bottom: "calc(100% + 6px)", right: 0,
              background: "#FCFAF7", border: `1px solid ${T.border}`,
              borderRadius: 10, boxShadow: LUX.shadowMd, padding: 6,
              zIndex: 100, minWidth: 168,
            }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: T.muted, letterSpacing: "0.1em", textTransform: "uppercase", padding: "3px 10px 5px" }}>
                Move to
              </div>
              {collections.filter(c => c !== doc.collection).map(c => (
                <button key={c} onClick={() => { setMenu(false); onMove(doc, c); }} className="nav-btn" style={{
                  display: "block", width: "100%", textAlign: "left",
                  padding: "5px 10px", border: "none", borderRadius: 6,
                  background: "transparent", color: T.mutedLt, cursor: "pointer",
                  fontSize: 12, fontFamily: "inherit",
                }}>{c}</button>
              ))}
              <button onClick={() => {
                const c = window.prompt("New collection name:");
                if (c?.trim()) { setMenu(false); onMove(doc, c.trim()); }
              }} className="nav-btn" style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "5px 10px", border: "none", borderRadius: 6,
                background: "transparent", color: T.muted, cursor: "pointer",
                fontSize: 12, fontFamily: "inherit", fontStyle: "italic",
              }}>New collection…</button>
              <div style={{ height: 1, background: T.border, margin: "5px 4px" }} />
              <button onClick={() => { setMenu(false); onRemove(doc); }} className="nav-btn" style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "5px 10px", border: "none", borderRadius: 6,
                background: "transparent", color: T.error, cursor: "pointer",
                fontSize: 12, fontFamily: "inherit",
              }}>Remove from Library</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Library surface ───────────────────────────────────────────
export default function LibraryTab() {
  const [docs,       setDocs]       = useState(null);   // null = loading
  const [active,     setActive]     = useState("All");
  const [query,      setQuery]      = useState("");
  const [dragOver,   setDragOver]   = useState(false);
  const [notice,     setNotice]     = useState(null);
  const fileRef  = useRef(null);
  const noticeTimer = useRef(null);

  const flash = (msg) => {
    setNotice(msg);
    clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(null), 3000);
  };

  const load = useCallback(() => {
    fetch(`${API}/documents`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setDocs((d?.documents || []).map(x => ({ ...x, status: "read" }))))
      .catch(() => setDocs([]));
  }, []);

  useEffect(() => { load(); }, [load]);

  const uploadFiles = useCallback(async (files) => {
    const target = active === "All" ? "Unsorted" : active;
    for (const file of files) {
      setDocs(prev => [
        { filename: file.name, collection: target, status: "reading", chars: file.size, added: new Date().toISOString() },
        ...(prev || []).filter(d => d.filename !== file.name),
      ]);
      const fd = new FormData();
      fd.append("file", file);
      fd.append("collection", target);
      try {
        const r = await fetch(`${API}/documents/upload`, { method: "POST", body: fd });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          setDocs(prev => (prev || []).map(d => d.filename === file.name ? { ...d, status: "error" } : d));
          flash(err.detail || `Couldn't read ${file.name}`);
          continue;
        }
        const data = await r.json();
        setDocs(prev => (prev || []).map(d => d.filename === data.filename
          ? { ...d, status: "read", chars: data.chars, chunks: data.chunks_stored } : d));
      } catch {
        setDocs(prev => (prev || []).map(d => d.filename === file.name ? { ...d, status: "error" } : d));
        flash("Backend offline — couldn't add the document.");
      }
    }
  }, [active]);

  const moveDoc = async (doc, collection) => {
    setDocs(prev => prev.map(d => d.filename === doc.filename ? { ...d, collection } : d));
    try {
      await fetch(`${API}/documents/${encodeURIComponent(doc.filename)}/collection`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collection }),
      });
    } catch { flash("Couldn't move the document — backend offline."); load(); }
  };

  const removeDoc = async (doc) => {
    if (!window.confirm(`Remove "${prettyTitle(doc.filename)}" from your Library?`)) return;
    setDocs(prev => prev.filter(d => d.filename !== doc.filename));
    try {
      await fetch(`${API}/documents/${encodeURIComponent(doc.filename)}`, { method: "DELETE" });
    } catch { flash("Couldn't remove the document — backend offline."); load(); }
  };

  // Collections present in data, plus defaults for the Move menu
  const present = [...new Set((docs || []).map(d => d.collection || "Unsorted"))];
  const chipList = ["All", ...present.sort((a, b) =>
    (a === "Unsorted") - (b === "Unsorted") || a.localeCompare(b))];
  const moveTargets = [...new Set([...DEFAULT_COLLECTIONS, ...present])].filter(c => c !== "Unsorted");

  const q = query.trim().toLowerCase();
  const visible = (docs || []).filter(d =>
    (active === "All" || (d.collection || "Unsorted") === active) &&
    (!q || d.filename.toLowerCase().includes(q) || (d.collection || "").toLowerCase().includes(q))
  );

  return (
    <div
      style={{ position: "relative" }}
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setDragOver(false); }}
      onDrop={e => { e.preventDefault(); setDragOver(false); uploadFiles([...e.dataTransfer.files]); }}
    >
      <style>{`
        .lib-card:hover { box-shadow: ${LUX.shadowMd}; transform: translateY(-2px); border-color: rgba(196,136,8,0.30); }
      `}</style>

      {/* ── Header ── */}
      <PageHeader title="Library" subtitle="Your saved documents and references — searchable and collection-tagged.">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search your library…"
          style={{
            width: 230,
            background: T.surface, border: `1px solid ${T.border}`,
            borderRadius: 20, padding: "7px 16px",
            fontSize: 12.5, color: T.text, fontFamily: "inherit", outline: "none",
          }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="btn-gold"
          style={{ padding: "9px 22px", fontSize: 13, whiteSpace: "nowrap" }}
        >＋ Add documents</button>
        <input ref={fileRef} type="file" multiple
          accept=".txt,.md,.py,.js,.ts,.jsx,.tsx,.json,.yaml,.yml,.html,.css,.sh,.sql,.csv,.pdf,.toml,.cfg,.conf,.rst"
          onChange={e => { uploadFiles([...e.target.files]); e.target.value = ""; }}
          style={{ display: "none" }} />
      </PageHeader>

      {/* ── Collection chips ── */}
      {(docs?.length > 0) && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 20 }}>
          {chipList.map(c => {
            const count = c === "All" ? docs.length : docs.filter(d => (d.collection || "Unsorted") === c).length;
            const on = active === c;
            return (
              <button key={c} onClick={() => setActive(c)} className="nav-btn" style={{
                padding: "5px 14px", borderRadius: 16, cursor: "pointer",
                border: `1px solid ${on ? T.mutedLt : T.border}`,
                background: on ? T.surface : "transparent",
                color: on ? T.text : T.muted,
                fontSize: 12, fontWeight: on ? 700 : 500, fontFamily: "inherit",
              }}>
                {c} <span style={{ opacity: 0.55, fontWeight: 400 }}>{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Notice ── */}
      {notice && (
        <div style={{
          marginBottom: 14, padding: "8px 14px", borderRadius: 8,
          background: "#F9E7E1", border: `1px solid ${T.error}33`,
          fontSize: 12, color: T.error,
        }}>{notice}</div>
      )}

      {/* ── Content ── */}
      {docs === null ? (
        <div style={{ padding: "60px 0", textAlign: "center", color: T.muted, fontSize: 13, fontStyle: "italic" }}>
          Opening your library…
        </div>
      ) : docs.length === 0 ? (
        <div style={{ padding: "70px 0 60px", textAlign: "center" }}>
          <div style={{ fontFamily: FONT_DISPLAY, fontSize: 24, color: T.text, marginBottom: 8 }}>
            Your library is empty.
          </div>
          <div style={{ fontSize: 13.5, color: T.muted, maxWidth: 420, margin: "0 auto 24px", lineHeight: 1.6 }}>
            Add documents and Amagra will read them, remember them,
            and draw on them in every conversation.
          </div>
          <button onClick={() => fileRef.current?.click()} className="btn-gold"
            style={{ padding: "13px 32px", fontSize: 14 }}>
            ＋ Add your first document
          </button>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 14 }}>
            or drop files anywhere on this page
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(218px, 1fr))", gap: 14 }}>
          {visible.map(doc => (
            <DocCard key={doc.filename} doc={doc}
              collections={moveTargets}
              onMove={moveDoc} onRemove={removeDoc} />
          ))}
          {visible.length === 0 && (
            <div style={{ gridColumn: "1 / -1", padding: "40px 0", textAlign: "center", color: T.muted, fontSize: 12.5, fontStyle: "italic" }}>
              Nothing here{q ? " matches your search" : " yet"}.
            </div>
          )}
        </div>
      )}

      {/* ── Drag overlay ── */}
      {dragOver && (
        <div style={{
          position: "absolute", inset: -12, borderRadius: 18,
          border: `2px dashed ${T.accent}`, background: "rgba(196,136,8,0.05)",
          display: "flex", alignItems: "center", justifyContent: "center",
          pointerEvents: "none", zIndex: 50,
        }}>
          <span style={{ fontFamily: FONT_DISPLAY, fontSize: 20, color: T.accent2 }}>
            Drop to add to your Library
          </span>
        </div>
      )}
    </div>
  );
}
