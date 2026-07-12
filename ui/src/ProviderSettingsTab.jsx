import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "./ObsShared";

import { API } from "./api";

const T = {
  bg:      "#F4F0E8",
  surface: "#FAF7F2",
  surface2:"#F4F0E8",
  surface3:"#EDE6DA",
  border:  "#E0D6C4",
  accent:  "#C48808",
  text:    "#2E2010",
  mutedLt: "#5C4030",
  muted:   "#9A7A60",
  success: "#15803D",
  warn:    "#9A6C00",
  error:   "#B42318",
};

// Three families the user picks between. The backend maps each to env vars the
// providers already read. Embeddings stay local on purpose (FAISS namespace).
const FAMILIES = [
  {
    id: "ollama",
    label: "Local (Ollama)",
    blurb: "Fully private, works offline. A model on your machine or a remote Ollama box.",
    fields: ["model", "base_url"],
    defaults: { model: "phi4-mini:latest", base_url: "http://localhost:11434" },
  },
  {
    id: "openai",
    label: "OpenAI-compatible",
    blurb: "OpenAI, Groq, OpenRouter, Together, or LM Studio — anything that speaks the OpenAI API.",
    fields: ["model", "base_url", "api_key"],
    defaults: { model: "gpt-4o-mini", base_url: "https://api.openai.com/v1" },
  },
  {
    id: "anthropic",
    label: "Anthropic (Claude)",
    blurb: "Claude models via the Anthropic API.",
    fields: ["model", "api_key"],
    defaults: { model: "claude-sonnet-4-6" },
  },
];

const familyOf = (provider) =>
  FAMILIES.find((f) => f.id === provider) ||
  (["groq", "openrouter", "together", "lmstudio"].includes(provider) ? FAMILIES[1] : FAMILIES[0]);

const lbl = { provider: "Provider", model: "Model", base_url: "Base URL", api_key: "API key" };

function StatusPill({ status }) {
  if (!status) return null;
  const ok = status.status === "ok";
  const c = ok ? T.success : T.error;
  return (
    <span style={{ color: c, fontWeight: 700, fontSize: 13 }}>
      {ok ? "● reachable" : "● error"}
      {status.model_available === false && ok ? " (model not found)" : ""}
    </span>
  );
}

export default function ProviderSettingsTab() {
  const [current, setCurrent]   = useState(null);
  const [provider, setProvider] = useState("ollama");
  const [form, setForm]         = useState({ model: "", base_url: "", api_key: "" });
  const [keyDirty, setKeyDirty] = useState(false); // only send api_key if the user typed one
  const [test, setTest]         = useState(null);
  const [busy, setBusy]         = useState("");     // "test" | "save" | ""
  const [saved, setSaved]       = useState(false);
  const [error, setError]       = useState("");

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/settings/llm`);
      const data = await r.json();
      const c = data.current;
      setCurrent(c);
      setProvider(c.provider);
      setForm({ model: c.model || "", base_url: c.base_url || "", api_key: "" });
      setKeyDirty(false);
    } catch (e) {
      setError("Could not reach the backend. Is the API running on :8000?");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const fam = familyOf(provider);

  const pickProvider = (id) => {
    setProvider(id);
    const f = familyOf(id);
    // seed sensible defaults when switching family, keep edits when staying
    setForm((prev) => ({
      model: f.defaults.model || prev.model || "",
      base_url: f.defaults.base_url || "",
      api_key: "",
    }));
    setKeyDirty(false);
    setTest(null);
    setSaved(false);
  };

  const body = () => {
    const out = { provider, model: form.model || undefined };
    if (fam.fields.includes("base_url")) out.base_url = form.base_url || undefined;
    if (fam.fields.includes("api_key") && keyDirty && form.api_key) out.api_key = form.api_key;
    return out;
  };

  const runTest = async () => {
    setBusy("test"); setError(""); setTest(null);
    try {
      const r = await fetch(`${API}/settings/llm/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body()),
      });
      setTest(await r.json());
    } catch (e) {
      setError("Test request failed.");
    } finally { setBusy(""); }
  };

  const save = async () => {
    setBusy("save"); setError(""); setSaved(false);
    try {
      const r = await fetch(`${API}/settings/llm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body()),
      });
      if (!r.ok) { setError(`Save failed (${r.status}).`); return; }
      const data = await r.json();
      setCurrent(data.current);
      setTest(data.health);
      setSaved(true);
      setKeyDirty(false);
      setForm((p) => ({ ...p, api_key: "" }));
    } catch (e) {
      setError("Save request failed.");
    } finally { setBusy(""); }
  };

  const inputStyle = {
    width: "100%", padding: "9px 11px", borderRadius: 8,
    border: `1px solid ${T.border}`, background: T.surface, color: T.text,
    fontSize: 14, fontFamily: "inherit", boxSizing: "border-box",
  };

  return (
    <div style={{ color: T.text }}>
      <PageHeader
        center
        title="Model"
      />

      {current && (
        <div style={{
          background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10,
          padding: "12px 16px", marginBottom: 22, fontSize: 13.5,
        }}>
          <span style={{ color: T.muted }}>Active now: </span>
          <strong style={{ color: T.accent }}>{current.provider}</strong>
          <span style={{ color: T.muted }}> · </span>
          <code style={{ color: T.text }}>{current.model}</code>
          {current.has_api_key && <span style={{ color: T.muted }}> · key set</span>}
        </div>
      )}

      {/* Provider family picker */}
      <div style={{ display: "grid", gap: 10, marginBottom: 22 }}>
        {FAMILIES.map((f) => {
          const active = f.id === provider || (f.id === "openai" && fam.id === "openai");
          return (
            <button
              key={f.id}
              onClick={() => pickProvider(f.id)}
              style={{
                textAlign: "left", cursor: "pointer",
                background: active ? `${T.accent}10` : T.surface,
                border: `1.5px solid ${active ? T.accent : T.border}`,
                borderRadius: 10, padding: "12px 16px", color: T.text, fontFamily: "inherit",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 14.5, marginBottom: 2 }}>
                {f.label}{active ? "  ✓" : ""}
              </div>
              <div style={{ fontSize: 13, color: T.mutedLt, lineHeight: 1.45 }}>{f.blurb}</div>
            </button>
          );
        })}
      </div>

      {/* Fields */}
      <div style={{ display: "grid", gap: 14, marginBottom: 22 }}>
        {fam.fields.map((field) => (
          <label key={field} style={{ display: "block" }}>
            <span style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: T.mutedLt, marginBottom: 5 }}>
              {lbl[field]}{field === "api_key" && current?.has_api_key ? "  (leave blank to keep saved key)" : ""}
            </span>
            <input
              type={field === "api_key" ? "password" : "text"}
              value={field === "api_key" ? form.api_key : form[field] || ""}
              placeholder={field === "api_key" && current?.has_api_key ? "••••••••" : (fam.defaults[field] || "")}
              onChange={(e) => {
                if (field === "api_key") setKeyDirty(true);
                setForm((p) => ({ ...p, [field]: e.target.value }));
                setSaved(false);
              }}
              style={inputStyle}
            />
          </label>
        ))}
      </div>

      {/* Landing-page pill buttons — the shared .btn-ghost (App.jsx) */}
      <div style={{ display: "flex", gap: 14, alignItems: "center", justifyContent: "center" }}>
        <button className="btn-ghost" onClick={runTest} disabled={!!busy}
          style={{ padding: "13px 30px", fontSize: 14, opacity: busy ? 0.6 : 1 }}>
          {busy === "test" ? "Testing…" : "Test connection"}
        </button>
        <button className="btn-ghost" onClick={save} disabled={!!busy}
          style={{ padding: "13px 30px", fontSize: 14, opacity: busy ? 0.6 : 1 }}>
          {busy === "save" ? "Saving…" : "Save & apply"}
        </button>
      </div>

      {(test || (saved && !test)) && (
        <div style={{ marginTop: 12, textAlign: "center" }}>
          <StatusPill status={test} />
          {saved && !test && <span style={{ color: T.success, fontWeight: 700, fontSize: 13 }}>● saved</span>}
        </div>
      )}

      {test?.error && (
        <pre style={{
          marginTop: 14, background: `${T.error}0E`, border: `1px solid ${T.error}40`,
          color: T.error, padding: "10px 12px", borderRadius: 8, fontSize: 12.5,
          whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>{test.error}</pre>
      )}
      {error && (
        <div style={{ marginTop: 14, color: T.error, fontSize: 13 }}>{error}</div>
      )}

      <p style={{ marginTop: 26, fontSize: 12.5, color: T.muted, lineHeight: 1.5, borderTop: `1px solid ${T.border}`, paddingTop: 16 }}>
        Embeddings stay local ({current?.embed_model || "nomic-embed-text"}) regardless of this
        setting — the memory index is built for that model, so retrieval keeps working offline.
        If a hosted provider is misconfigured, Amagra falls back to local Ollama rather than failing.
      </p>
    </div>
  );
}
