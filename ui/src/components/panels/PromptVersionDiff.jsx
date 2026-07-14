// PromptVersionDiff.jsx — side-by-side version compare for a prompt (#71).
//
// The last open piece of #71: Monaco's DiffEditor over the versions that #69
// persists under prompts/<slug>/versions/. Pick any two committed versions (or a
// version vs. the live working head) and see exactly what changed. Read-only.

import { useState, useEffect } from "react";
import { DiffEditor } from "@monaco-editor/react";
import { MONACO_THEME } from "@/lib/monacoSetup";
import { listVersions, readVersion } from "@/lib/promptStore";

const HEAD = "head";   // sentinel for "current working copy"

export default function PromptVersionDiff({ T, slug, headContent, onClose }) {
  const [versions, setVersions] = useState(null);   // null = loading
  const [left, setLeft]   = useState(null);
  const [right, setRight] = useState(null);
  const [leftText,  setLeftText]  = useState("");
  const [rightText, setRightText] = useState("");

  // Load the version list once, and pick a sensible default pair.
  useEffect(() => {
    let live = true;
    listVersions(slug).then((vs) => {
      if (!live) return;
      setVersions(vs);
      if (vs.length >= 2)      { setLeft(vs[vs.length - 2]); setRight(vs[vs.length - 1]); }
      else if (vs.length === 1){ setLeft(vs[0]);             setRight(HEAD); }
      else                     { setLeft(HEAD);              setRight(HEAD); }
    });
    return () => { live = false; };
  }, [slug]);

  // Resolve the chosen sides to text (head is in memory; versions come from disk).
  useEffect(() => {
    let live = true;
    const resolve = async (sel, set) => {
      if (sel == null) return;
      if (sel === HEAD) { set(headContent ?? ""); return; }
      const txt = await readVersion(slug, sel);
      if (live) set(txt ?? "");
    };
    resolve(left, setLeftText);
    resolve(right, setRightText);
    return () => { live = false; };
  }, [slug, left, right, headContent]);

  const opts = versions ?? [];
  const labelFor = (v) => (v === HEAD ? "working draft" : `v${v}`);

  const selStyle = {
    background: T.surface, color: T.text, border: `1px solid ${T.border}`,
    borderRadius: 4, padding: "3px 8px", fontSize: 12, fontFamily: "inherit",
  };

  return (
    <div
      onClick={onClose}
      style={{ position: "absolute", inset: 0, background: "#2E201066", display: "flex",
               alignItems: "center", justifyContent: "center", zIndex: 50 }}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: "82%", height: "78%", background: T.surface, border: `1px solid ${T.border}`,
                 borderRadius: 8, boxShadow: "0 12px 40px #2E201033", display: "flex",
                 flexDirection: "column", overflow: "hidden" }}>

        {/* header */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px",
                      borderBottom: `1px solid ${T.border}`, background: T.surface2, flexShrink: 0 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>Compare versions</span>
          <span style={{ fontSize: 11, color: T.muted }}>{slug}</span>
          <div style={{ flex: 1 }} />
          {versions != null && opts.length > 0 && (
            <>
              <select value={left ?? ""} onChange={(e) => setLeft(coerce(e.target.value))} style={selStyle}>
                {opts.map((v) => <option key={`l${v}`} value={v}>{labelFor(v)}</option>)}
                <option value={HEAD}>{labelFor(HEAD)}</option>
              </select>
              <span style={{ color: T.muted, fontSize: 12 }}>→</span>
              <select value={right ?? ""} onChange={(e) => setRight(coerce(e.target.value))} style={selStyle}>
                {opts.map((v) => <option key={`r${v}`} value={v}>{labelFor(v)}</option>)}
                <option value={HEAD}>{labelFor(HEAD)}</option>
              </select>
            </>
          )}
          <button onClick={onClose}
            style={{ background: "transparent", border: "none", color: T.muted, fontSize: 18,
                     cursor: "pointer", lineHeight: 1, padding: "0 4px" }}>×</button>
        </div>

        {/* body */}
        <div style={{ flex: 1, minHeight: 0 }}>
          {versions == null ? (
            <Center T={T}>Loading versions…</Center>
          ) : opts.length === 0 ? (
            <Center T={T}>No saved versions yet — press <b style={{ margin: "0 4px" }}>Ctrl+S</b> in the editor to commit one.</Center>
          ) : (
            <DiffEditor
              language="markdown"
              theme={MONACO_THEME}
              original={leftText}
              modified={rightText}
              options={{
                readOnly: true, renderSideBySide: true, minimap: { enabled: false },
                wordWrap: "on", scrollBeyondLastLine: false, fontSize: 13,
                overviewRulerLanes: 0, renderOverviewRuler: false,
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function coerce(v) { return v === HEAD ? HEAD : Number(v); }

function Center({ T, children }) {
  return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
                  color: T.muted, fontSize: 13 }}>{children}</div>
  );
}
