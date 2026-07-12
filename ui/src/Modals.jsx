import { useState, useEffect, useRef } from "react";
import { API } from "./api";
import { AGENTS, BUILD_PHASES, VERSION } from "./constants";
import { T, LUX, TYPE, EASE, DUR, RADIUS, FONT_DISPLAY, FONT_MONO } from "./theme";
import { PageHeader } from "./ObsShared";
import InspectOverviewTab from "./InspectOverviewTab";

// ── Shared calm primitives (Settings + About) ─────────────────
const GOLD    = T.accent;      // #C48808 — fills, thumbs, hairlines
const GOLD_TX = T.accentText;  // #8A5A00 — legible gold for text

// Gold-and-white slider + row dividers. The unfilled track is warm cream
// (T.border), never black; the thumb is a white-ringed gold disc.
const CALM_CSS = `
.gold-range{-webkit-appearance:none;appearance:none;height:7px;border-radius:999px;outline:none;cursor:pointer;
  background:linear-gradient(90deg, ${GOLD} 0 var(--pct,50%), ${GOLD}26 var(--pct,50%) 100%);
  box-shadow:inset 0 0 0 1px ${GOLD}33;}
.gold-range::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:18px;height:18px;border-radius:50%;
  background:${GOLD};border:2.5px solid #fff;box-shadow:0 0 0 1.5px ${GOLD}, ${LUX.shadowMd};cursor:pointer;transition:transform ${DUR.fast} ${EASE.out};}
.gold-range::-webkit-slider-thumb:hover{transform:scale(1.12);}
.gold-range::-moz-range-thumb{width:18px;height:18px;border:2.5px solid #fff;border-radius:50%;background:${GOLD};box-shadow:0 0 0 1.5px ${GOLD}, ${LUX.shadowMd};cursor:pointer;}
.gold-range::-moz-range-track{background:transparent;height:7px;border-radius:999px;}
.set-row + .set-row{border-top:1px solid ${T.border}66;}
.set-card{transition:box-shadow ${DUR.base} ${EASE.out};}
.set-card:hover{box-shadow:${LUX.shadowSm};}
`;

function SectionCard({ sym, title, children }) {
  return (
    <div className="set-card" style={{
      background: LUX.tileFace, border: `1px solid ${LUX.tileBorder}`,
      borderRadius: RADIUS.lg, padding: "16px 20px", marginBottom: 16,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6,
                    paddingBottom: 12, borderBottom: `1px solid ${GOLD}20` }}>
        {sym && <span style={{
          fontFamily: FONT_DISPLAY, fontSize: 15, lineHeight: 1, color: GOLD,
          width: 26, height: 26, flexShrink: 0, display: "inline-flex",
          alignItems: "center", justifyContent: "center",
          background: `${GOLD}12`, border: `1px solid ${GOLD}30`, borderRadius: "50%",
        }}>{sym}</span>}
        <span style={{ ...TYPE.eyebrow, fontSize: 10, color: GOLD_TX }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

function Row({ label, hint, children }) {
  return (
    <div className="set-row" style={{ display: "flex", alignItems: "center", gap: 16, padding: "12px 0" }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ ...TYPE.small, color: T.text }}>{label}</div>
        {hint && <div style={{ ...TYPE.caption, fontSize: 11, color: T.muted, marginTop: 2 }}>{hint}</div>}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  );
}

function GoldSlider({ value, min, max, step }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <input type="range" className="gold-range" min={min} max={max} step={step}
      value={value.value} onChange={value.onChange}
      style={{ width: 170, "--pct": `${pct}%` }} />
  );
}

function Toggle({ checked, onChange }) {
  return (
    <button role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      style={{
        width: 44, height: 25, borderRadius: 999, padding: 0, position: "relative", cursor: "pointer",
        background: checked ? GOLD : "#D6C6A6",
        border: `1px solid ${checked ? GOLD : "#C3B088"}`,
        boxShadow: `inset 0 1px 2px ${checked ? "rgba(120,86,20,0.25)" : "rgba(120,86,20,0.14)"}`,
        transition: `background ${DUR.base} ${EASE.out}, border-color ${DUR.base} ${EASE.out}`,
      }}>
      <span style={{
        position: "absolute", top: 2, left: checked ? 21 : 2, width: 19, height: 19, borderRadius: "50%",
        background: "#fff", border: "1px solid rgba(120,86,20,0.30)",
        boxShadow: "0 1px 4px rgba(72,52,28,0.32)",
        transition: `left ${DUR.base} ${EASE.out}`,
      }} />
    </button>
  );
}

function SegGroup({ options, value, onChange }) {
  return (
    <div style={{ display: "inline-flex", gap: 2, padding: 2, background: T.surface2,
                  border: `1px solid ${T.border}`, borderRadius: RADIUS.md }}>
      {options.map(o => {
        const on = value === o.val;
        return (
          <button key={o.val} onClick={() => onChange(o.val)} style={{
            padding: "5px 13px", fontSize: 11, fontFamily: "inherit", fontWeight: on ? 700 : 500,
            background: on ? `${GOLD}22` : "transparent", color: on ? GOLD_TX : T.muted,
            border: "none", borderRadius: RADIUS.sm, cursor: "pointer",
            transition: `background ${DUR.fast} ${EASE.out}, color ${DUR.fast} ${EASE.out}`,
          }}>{o.label}</button>
        );
      })}
    </div>
  );
}

// ── Settings ──────────────────────────────────────────────────
export function SettingsModal({ settings, onUpdate }) {
  const [saved,    setSaved]    = useState(false);
  const saveTimer = useRef(null);

  const flash = () => {
    setSaved(true);
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => setSaved(false), 1600);
  };
  const set = (key, val) => { onUpdate(key, val); flash(); };
  const resetDefaults = () => {
    Object.entries({
      defaultAgent: "auto", reflectMode: "", temperature: 0.7, maxMemories: 5,
      enterToSend: true, showTimestamps: true, reduceMotion: false,
    }).forEach(([k, v]) => onUpdate(k, v));
    flash();
  };

  return (
    <div style={{ animation: `fadeIn ${DUR.base} ${EASE.out}` }}>
      <style>{CALM_CSS}</style>

      <PageHeader
        center
        title="Settings"
        subtitle="Tune how Amagra reasons, remembers, and behaves. Every change saves instantly to this device."
      >
        <span style={{
          fontSize: 10.5, fontWeight: 700, letterSpacing: "0.04em",
          color: saved ? T.success : "transparent",
          transition: `color ${DUR.base} ${EASE.out}`,
        }}>✓ Saved</span>
      </PageHeader>

      <SectionCard title="Agent & Inference">
        <Row label="Default agent" hint="Pre-selects the agent for every new conversation">
          <select value={settings.defaultAgent} onChange={e => set("defaultAgent", e.target.value)}
            style={{
              background: T.surface2, border: `1px solid ${T.border}`, color: T.text,
              borderRadius: RADIUS.md, padding: "6px 10px", fontSize: 11.5, fontFamily: "inherit",
              cursor: "pointer", minWidth: 180,
            }}>
            <option value="auto">Auto (Coordinator routes)</option>
            {AGENTS.filter(a => a.id !== "coordinator").map(a => (
              <option key={a.id} value={a.id}>{a.label}</option>
            ))}
          </select>
        </Row>

        <Row label="Default reflect mode" hint="Depth of self-critique applied after each response">
          <SegGroup value={settings.reflectMode} onChange={v => set("reflectMode", v)}
            options={[
              { val: "",      label: "Auto"  },
              { val: "none",  label: "Fast"  },
              { val: "light", label: "Check" },
              { val: "full",  label: "Deep"  },
            ]}
          />
        </Row>

        <Row label={`Temperature — ${settings.temperature.toFixed(1)}`}
             hint="Higher = more creative · lower = more deterministic">
          <GoldSlider min={0.1} max={1.0} step={0.1}
            value={{ value: settings.temperature, onChange: e => set("temperature", parseFloat(e.target.value)) }} />
        </Row>
      </SectionCard>

      <SectionCard title="Memory">
        <Row label={`Max memories per query — ${settings.maxMemories}`}
             hint="How many relevant memories are retrieved and injected into each request">
          <GoldSlider min={1} max={15} step={1}
            value={{ value: settings.maxMemories, onChange: e => set("maxMemories", parseInt(e.target.value)) }} />
        </Row>
      </SectionCard>

      <SectionCard title="Interface">
        <Row label="Send on Enter" hint="On: Enter sends, Shift+Enter for a new line. Off: Ctrl+Enter sends.">
          <Toggle checked={settings.enterToSend} onChange={v => set("enterToSend", v)} />
        </Row>
        <Row label="Message timestamps" hint="Show the time beside each chat message">
          <Toggle checked={settings.showTimestamps} onChange={v => set("showTimestamps", v)} />
        </Row>
        <Row label="Reduce motion" hint="Collapse animations and transitions across the app">
          <Toggle checked={settings.reduceMotion} onChange={v => set("reduceMotion", v)} />
        </Row>
      </SectionCard>

      {/* Footer — persistence note + reset */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 4 }}>
        <div style={{ ...TYPE.caption, fontSize: 11, color: T.muted, flex: 1 }}>
          Settings persist in <code style={{ color: GOLD_TX, fontFamily: FONT_MONO }}>localStorage</code>.
          Reflect mode and default agent apply on your next message.
        </div>
        <button className="btn-ghost" onClick={resetDefaults}
          style={{ flexShrink: 0, padding: "9px 22px", fontSize: 12 }}>
          Reset to defaults
        </button>
      </div>
    </div>
  );
}

// ── Keyboard shortcuts ────────────────────────────────────────
// Each group is an "infographic" card. Symbols are decorative gold glyphs,
// not emoji. Every binding below is wired (App.jsx global handler + ChatTab
// panel handler) — nothing aspirational.
const SHORTCUT_GROUPS = [
  { sym: "◇", title: "Primary Navigation", rows: [
    ["Introduction",      "Ctrl+1"],
    ["Workspace",         "Ctrl+2"],
    ["Runs",              "Ctrl+3"],
    ["Cognition",         "Ctrl+4"],
    ["Memory",            "Ctrl+5"],
    ["Research",          "Ctrl+6"],
    ["Setup",             "Ctrl+7"],
    ["Command menu",      "Ctrl+K"],
  ]},
  { sym: "⟡", title: "Debug & Decisions", rows: [
    ["Decisions",         "Ctrl+Shift+D"],
    ["Learning Timeline", "Ctrl+Shift+L"],
    ["Policy Gate",       "Ctrl+Shift+Y"],
    ["Decisions / Replay","Ctrl+Shift+R"],
  ]},
  { sym: "⊹", title: "Observe & Explore", rows: [
    ["Cognitive OS",      "Ctrl+Shift+X"],
    ["Memory Browser",    "Ctrl+Shift+M"],
    ["Knowledge Graph",   "Ctrl+Shift+K"],
    ["Data Analysis",     "Ctrl+Shift+A"],
    ["Consensus",         "Ctrl+Shift+V"],
  ]},
  { sym: "⚙", title: "Tools & Surfaces", rows: [
    ["Prompt Editor",     "Ctrl+Shift+E"],
    ["Task Queue",        "Ctrl+Shift+Q"],
    ["Goals",             "Ctrl+Shift+G"],
    ["Releases",          "Ctrl+Shift+H"],
    ["Skills",            "Ctrl+Shift+S"],
    ["Providers",         "Ctrl+Shift+P"],
  ]},
  { sym: "▢", title: "Interface", rows: [
    ["Toggle menu",       "Ctrl+B"],
    ["Open Settings",     "Ctrl+,"],
    ["Keyboard Shortcuts","Ctrl+/"],
    ["Close / dismiss",   "Escape"],
  ]},
  { sym: "∴", title: "Chat", rows: [
    ["New chat",          "Ctrl+Shift+N"],
    ["Send message",      "Enter"],
    ["New line",          "Shift+Enter"],
    ["Threads panel",     "Ctrl+Shift+T"],
    ["Context panel",     "Ctrl+Shift+C"],
    ["Advanced panel",    "Ctrl+Shift+O"],
  ]},
];

const SHORTCUT_COUNT = SHORTCUT_GROUPS.reduce((n, g) => n + g.rows.length, 0);

// A key chord like "Ctrl+Shift+D" → discrete gold key caps joined by a hair "+".
function KeyChord({ combo }) {
  const keys = combo.split("+");
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 3, flexShrink: 0 }}>
      {keys.map((k, i) => (
        <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
          {i > 0 && <span style={{ fontSize: 9, color: T.muted }}>+</span>}
          <kbd style={{
            fontFamily: FONT_MONO, fontSize: 10, fontWeight: 700, lineHeight: 1,
            color: T.accentText, background: `${T.accent}12`,
            border: `1px solid ${T.accent}38`, borderRadius: RADIUS.sm - 3,
            padding: "3px 6px", whiteSpace: "nowrap", boxShadow: LUX.shadowSm,
          }}>{k}</kbd>
        </span>
      ))}
    </span>
  );
}

export function ShortcutsModal() {
  return (
    <div style={{ animation: `fadeIn ${DUR.base} ${EASE.out}` }}>
      <style>{`
        .kbd-group { transition: box-shadow ${DUR.base} ${EASE.out}, transform ${DUR.base} ${EASE.out}; }
        .kbd-group:hover { box-shadow: ${LUX.shadowSm}; transform: translateY(-1px); }
      `}</style>

      <PageHeader
        center
        title="Shortcuts"
        subtitle={`Every keyboard binding in Amagra — ${SHORTCUT_COUNT} shortcuts across ${SHORTCUT_GROUPS.length} groups. Chords work anywhere outside a text field; ⌘ substitutes for Ctrl on macOS.`}
      />

      {/* Cards stacked inline — one full-width card per row for more room */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}>
        {SHORTCUT_GROUPS.map((group) => (
          <div key={group.title} className="kbd-group" style={{
            width: "100%",
            background: LUX.tileFace, border: `1px solid ${LUX.tileBorder}`,
            borderRadius: RADIUS.lg, padding: "18px 22px",
          }}>
            {/* Group header */}
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 12,
                          paddingBottom: 10, borderBottom: `1px solid ${T.accent}20` }}>
              <span style={{ ...TYPE.eyebrow, fontSize: 10, color: T.accentText }}>
                {group.title}
              </span>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 10, color: T.muted, fontFamily: FONT_MONO }}>
                {group.rows.length}
              </span>
            </div>

            {/* Rows — two per line, split by a gold divider */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
            }}>
              {group.rows.map(([action, key], i) => {
                const rightCol = i % 2 === 1;
                return (
                  <div key={action} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    gap: 12, padding: "8px 0",
                    paddingLeft: rightCol ? 26 : 0,
                    paddingRight: rightCol ? 0 : 26,
                    borderLeft: rightCol ? `1px solid ${T.accent}22` : "none",
                  }}>
                    <span style={{ ...TYPE.small, color: T.mutedLt, minWidth: 0, overflow: "hidden",
                                   textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{action}</span>
                    <KeyChord combo={key} />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── About (identity, build & live engine state) ───────────────
// A first-class surface (System › About). Now also home to the System
// information that used to live under Settings — the live engine readout.
export function AboutView({ coherence, apiStatus, onNav }) {
  const [status,   setStatus]   = useState(null);
  const [memStats, setMemStats] = useState(null);
  const [decStats, setDecStats] = useState(null);
  const [working,  setWorking]  = useState(null);

  useEffect(() => {
    fetch(`${API}/status`)
      .then(r => r.ok ? r.json() : null).then(setStatus).catch(() => {});
    fetch(`${API}/memory/stats`)
      .then(r => r.ok ? r.json() : null).then(setMemStats).catch(() => {});
    fetch(`${API}/decisions?limit=1`)
      .then(r => r.ok ? r.json() : null).then(d => d && setDecStats(d.stats || null)).catch(() => {});
    fetch(`${API}/agents/status`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d?.agents && setWorking(d.agents.filter(a => a.status === "running").length)).catch(() => {});
  }, []);

  const online = apiStatus === "online";
  const latest = BUILD_PHASES[BUILD_PHASES.length - 1];

  const InfoRow = ({ label, children }) => (
    <div className="set-row" style={{ display: "flex", justifyContent: "space-between",
                                      alignItems: "center", gap: 12, padding: "10px 0" }}>
      <span style={{ ...TYPE.small, color: T.muted }}>{label}</span>
      <span style={{ ...TYPE.small, color: T.text, textAlign: "right", minWidth: 0,
                     overflow: "hidden", textOverflow: "ellipsis" }}>{children}</span>
    </div>
  );
  const Mono = ({ children, color }) => (
    <span style={{ fontFamily: FONT_MONO, fontSize: 11.5, color: color || GOLD_TX }}>{children}</span>
  );

  return (
    <div style={{ animation: `fadeIn ${DUR.base} ${EASE.out}` }}>
      <style>{CALM_CSS}</style>

      <PageHeader center title="About" subtitle="What Amagra is — and the live state of the engine on this machine." />

      {/* Identity hero */}
      <div className="set-card" style={{
        background: LUX.tileFace, border: `1px solid ${LUX.tileBorder}`,
        borderRadius: RADIUS.lg, padding: "20px 22px", marginBottom: 16,
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 28, fontWeight: 600, fontFamily: FONT_DISPLAY,
                       letterSpacing: "0.08em", ...LUX.goldText, display: "inline-block" }}>AMAGRA</h2>
          <span style={{
            fontSize: 11, fontWeight: 700, color: GOLD_TX,
            background: `${GOLD}16`, border: `1px solid ${GOLD}40`,
            borderRadius: RADIUS.sm, padding: "2px 9px", fontFamily: FONT_MONO,
          }}>v{VERSION}</span>
          <span style={{ ...TYPE.caption, color: T.muted }}>
            Phase {latest.id} — {latest.title}
          </span>
        </div>
        <p style={{ margin: "12px 0 0", ...TYPE.small, color: T.mutedLt, maxWidth: 620 }}>
          The AI you can trust with long-term work — it remembers what you've done, explains every
          decision, and runs entirely on your hardware.
        </p>
        <div style={{ marginTop: 16, display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "8px 24px" }}>
          {[["Architecture","Signal-first routing"],["Memory","FAISS + LRU cache"],
            ["Agents","Specialist + Coordinator"],["Eval","Dual-trajectory critic"],
            ["UI","React + Vite"],["API","FastAPI / Python"]].map(([k,v]) => (
            <div key={k} style={{ ...TYPE.caption, fontSize: 11.5 }}>
              <span style={{ color: T.muted }}>{k}: </span>
              <span style={{ color: T.text }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Live snapshot — recent decisions + recent work, inline (no wrapper card) */}
      <div style={{ marginBottom: 16 }}>
        <InspectOverviewTab embedded onNav={onNav} />
      </div>

      {/* Live system information (moved from Settings) — also home to the live numbers */}
      <SectionCard sym="⚙" title="System">
        <InfoRow label="API"><Mono>{API || "same-origin"}</Mono></InfoRow>
        <InfoRow label="Status">
          <span style={{ ...TYPE.small, color: online ? T.success : T.error, fontWeight: 600 }}>
            {online ? "● Online" : "○ Offline"}
          </span>
        </InfoRow>
        <InfoRow label="Model">{status?.model ?? "phi4-mini"}</InfoRow>
        <InfoRow label="GPU">{status?.gpu ?? "RTX 2050"}</InfoRow>
        <InfoRow label="Backend">{memStats?.backend?.type ?? "FAISSBackend"}</InfoRow>
        <InfoRow label="Working now"><Mono>{working ?? "—"}</Mono></InfoRow>
        <InfoRow label="Decisions"><Mono>{decStats?.total ?? "—"}</Mono></InfoRow>
        <InfoRow label="Reflect rate"><Mono>{decStats ? `${Math.round((decStats.reflect_rate || 0) * 100)}%` : "—"}</Mono></InfoRow>
        <InfoRow label="Conflicts"><Mono>{decStats?.conflicts ?? "—"}</Mono></InfoRow>
        <InfoRow label="Tasks pending"><Mono>{status?.tasks?.pending ?? "—"}</Mono></InfoRow>
        <InfoRow label="Tasks done"><Mono>{status?.tasks?.done ?? "—"}</Mono></InfoRow>
        <InfoRow label="Tasks failed"><Mono>{status?.tasks?.failed ?? "—"}</Mono></InfoRow>
        <InfoRow label="Memories total"><Mono>{memStats?.total ?? "—"}</Mono></InfoRow>
        <InfoRow label="Prune ready"><Mono>{memStats?.prune_candidates ?? "—"}</Mono></InfoRow>
        <InfoRow label="Never recalled"><Mono>{memStats?.never_used ?? "—"}</Mono></InfoRow>
        {coherence && <>
          <InfoRow label="Coherence C(t)"><Mono>{coherence.C?.toFixed(4)}</Mono></InfoRow>
          <InfoRow label="Routing"><Mono>{coherence.c_routing?.toFixed(3)}</Mono></InfoRow>
          <InfoRow label="Calibration"><Mono>{coherence.c_calib?.toFixed(3)}</Mono></InfoRow>
          <InfoRow label="Memories active"><Mono>{coherence.mem_n}</Mono></InfoRow>
        </>}
      </SectionCard>
    </div>
  );
}
