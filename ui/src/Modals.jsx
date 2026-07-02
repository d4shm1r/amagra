import { useState, useEffect, useRef } from "react";
import { API } from "./api";
import { AGENTS } from "./constants";
import { T } from "./theme";

// ── Settings modal ────────────────────────────────────────────
export function SettingsModal({ settings, onUpdate, coherence, apiStatus, mode, onSetMode }) {
  const [status,   setStatus]   = useState(null);
  const [memStats, setMemStats] = useState(null);
  const [saved,    setSaved]    = useState(false);
  const saveTimer = useRef(null);

  useEffect(() => {
    fetch(`${API}/status`)
      .then(r => r.ok ? r.json() : null).then(setStatus).catch(() => {});
    fetch(`${API}/memory/stats`)
      .then(r => r.ok ? r.json() : null).then(setMemStats).catch(() => {});
  }, []);

  function set(key, val) {
    onUpdate(key, val);
    setSaved(true);
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => setSaved(false), 1800);
  }

  const SectionHead = ({ title }) => (
    <div style={{ fontSize: 9, fontWeight: 700, color: T.muted, letterSpacing: "0.1em",
                  textTransform: "uppercase", margin: "20px 0 10px", paddingBottom: 5,
                  borderBottom: `1px solid ${T.border}` }}>
      {title}
    </div>
  );

  const Field = ({ label, hint, children }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, color: T.text }}>{label}</div>
        {hint && <div style={{ fontSize: 10, color: T.muted, marginTop: 1 }}>{hint}</div>}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  );

  const ButtonGroup = ({ options, value, onChange }) => (
    <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.border}` }}>
      {options.map(({ val, label }) => (
        <button key={val} onClick={() => onChange(val)}
          style={{
            padding: "4px 10px", fontSize: 11, fontFamily: "inherit", fontWeight: value === val ? 700 : 400,
            background: value === val ? `${T.accent}33` : "transparent",
            color: value === val ? T.accent : T.muted,
            border: "none", borderLeft: val !== options[0].val ? `1px solid ${T.border}` : "none",
            cursor: "pointer", transition: "background 0.1s, color 0.1s",
          }}>{label}</button>
      ))}
    </div>
  );

  const online = apiStatus === "online";

  return (
    <div style={{ minWidth: 400, maxHeight: "70vh", overflowY: "auto", paddingRight: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: T.text, flex: 1 }}>Settings</h2>
        {saved && <span style={{ fontSize: 10, color: T.success, fontWeight: 600 }}>✓ Saved</span>}
      </div>

      <SectionHead title="Interface" />

      <Field label="Mode" hint="Simple keeps the essentials; Advanced reveals every tool and diagnostic">
        <ButtonGroup
          value={mode}
          onChange={onSetMode}
          options={[
            { val: "simple",   label: "Simple"   },
            { val: "advanced", label: "Advanced" },
          ]}
        />
      </Field>

      <SectionHead title="Agent & Inference" />

      <Field label="Default agent" hint="Pre-selects the agent for every new conversation">
        <select value={settings.defaultAgent} onChange={e => set("defaultAgent", e.target.value)}
          style={{
            background: T.surface2, border: `1px solid ${T.border}`, color: T.text,
            borderRadius: 8, padding: "4px 8px", fontSize: 11, fontFamily: "inherit", cursor: "pointer",
            minWidth: 160,
          }}>
          <option value="auto">Auto (Coordinator routes)</option>
          {AGENTS.filter(a => a.id !== "coordinator").map(a => (
            <option key={a.id} value={a.id}>{a.label}</option>
          ))}
        </select>
      </Field>

      <Field label="Default reflect mode" hint="Depth of self-critique applied after each response">
        <ButtonGroup
          value={settings.reflectMode}
          onChange={v => set("reflectMode", v)}
          options={[
            { val: "",      label: "Auto"  },
            { val: "none",  label: "Fast"  },
            { val: "light", label: "Check" },
            { val: "full",  label: "Deep"  },
          ]}
        />
      </Field>

      <Field
        label={`Temperature — ${settings.temperature.toFixed(1)}`}
        hint="Higher = more creative, lower = more deterministic"
      >
        <input type="range" min="0.1" max="1.0" step="0.1"
          value={settings.temperature}
          onChange={e => set("temperature", parseFloat(e.target.value))}
          style={{ width: 130, accentColor: T.accent, cursor: "pointer" }}
        />
      </Field>

      <SectionHead title="Memory" />

      <Field
        label={`Max memories per query — ${settings.maxMemories}`}
        hint="How many relevant memories are retrieved and injected into each request"
      >
        <input type="range" min="1" max="15" step="1"
          value={settings.maxMemories}
          onChange={e => set("maxMemories", parseInt(e.target.value))}
          style={{ width: 130, accentColor: T.accent, cursor: "pointer" }}
        />
      </Field>

      {memStats && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 4, marginBottom: 12 }}>
          {[
            ["Total",         memStats.total            ?? "—"],
            ["Prune ready",   memStats.prune_candidates ?? "—"],
            ["Never recalled",memStats.never_used       ?? "—"],
          ].map(([k, v]) => (
            <div key={k} style={{ background: T.surface2, borderRadius: 8, padding: "8px 10px", textAlign: "center" }}>
              <div style={{ fontSize: 16, fontWeight: 800, color: T.text, fontVariantNumeric: "tabular-nums" }}>{v}</div>
              <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>{k}</div>
            </div>
          ))}
        </div>
      )}

      <SectionHead title="System" />

      {[
        ["API",     `${API}`,                                     true ],
        ["Status",  online ? "● Online" : "○ Offline",           false],
        ["Model",   status?.model  ?? "phi4-mini",               false],
        ["GPU",     status?.gpu    ?? "RTX 2050",                false],
        ["Backend", memStats?.backend?.type ?? "FAISSBackend",   false],
        ...(coherence ? [
          ["C(t)",  coherence.C?.toFixed(4)                    , true],
          ["Routing",  coherence.c_routing?.toFixed(3)         , true],
        ] : []),
      ].map(([k, v, mono]) => (
        <div key={k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                              padding: "5px 0", borderBottom: `1px solid ${T.border}22`, fontSize: 11 }}>
          <span style={{ color: T.muted }}>{k}</span>
          <span style={{ color: T.text, fontFamily: mono ? "monospace" : "inherit", fontSize: mono ? 10 : 11 }}>{v}</span>
        </div>
      ))}

      <div style={{ marginTop: 14, padding: "8px 10px", background: T.surface2,
                    borderRadius: 8, fontSize: 10, color: T.muted }}>
        Settings persist in <code style={{ color: T.accent2 }}>localStorage</code>.
        Reflect mode and default agent apply on next message.
      </div>
    </div>
  );
}

// ── Keyboard shortcuts modal ──────────────────────────────────
const SHORTCUT_GROUPS = [
  { title: "Primary Navigation", rows: [
    ["Introduction",      "Ctrl+1"],
    ["Workspace",         "Ctrl+2"],
    ["Runs",              "Ctrl+3"],
    ["Cognition",         "Ctrl+4"],
    ["Memory",            "Ctrl+5"],
    ["Research",          "Ctrl+6"],
    ["Setup",             "Ctrl+7"],
    ["Search menu",       "Ctrl+K"],
  ]},
  { title: "Debug", rows: [
    ["Decisions",         "Ctrl+Shift+D"],
    ["Learning Timeline", "Ctrl+Shift+L"],
    ["Policy Gate",       "Ctrl+Shift+Y"],
    ["Decisions / Replay","Ctrl+Shift+R"],
  ]},
  { title: "Observe & Explore", rows: [
    ["Cognitive OS",      "Ctrl+Shift+X"],
    ["Memory Browser",    "Ctrl+Shift+M"],
    ["Knowledge Graph",   "Ctrl+Shift+K"],
    ["Data Analysis",     "Ctrl+Shift+A"],
  ]},
  { title: "Tools", rows: [
    ["Prompt Editor",     "Ctrl+Shift+E"],
    ["Task Queue",        "Ctrl+Shift+Q"],
    ["Goals",             "Ctrl+Shift+G"],
    ["Progress",          "Ctrl+Shift+P"],
    ["Version History",   "Ctrl+Shift+H"],
  ]},
  { title: "Interface", rows: [
    ["Toggle menu",       "Ctrl+B"],
    ["Open Settings",     "Ctrl+,"],
    ["Keyboard Shortcuts","Ctrl+/"],
    ["Close modal",       "Escape"],
  ]},
  { title: "Chat", rows: [
    ["Send message",      "Enter"],
    ["New line",          "Shift+Enter"],
    ["Threads panel",     "Ctrl+Shift+T"],
    ["Context panel",     "Ctrl+Shift+C"],
    ["Advanced panel",    "Ctrl+Shift+O"],
  ]},
];

const SIMPLE_SHORTCUT_GROUPS = [
  { title: "Primary Navigation", rows: [
    ["Introduction",      "Ctrl+1"],
    ["Chat",              "Ctrl+2"],
    ["Prompt IDE",        "Ctrl+3"],
    ["Consensus",         "Ctrl+4"],
    ["Library",           "Ctrl+5"],
    ["Model",             "Ctrl+6"],
    ["Guide",             "Ctrl+7"],
    ["Search menu",       "Ctrl+K"],
  ]},
  { title: "Interface", rows: [
    ["Toggle menu",       "Ctrl+B"],
    ["Open Settings",     "Ctrl+,"],
    ["Keyboard Shortcuts","Ctrl+/"],
    ["Close modal",       "Escape"],
  ]},
  { title: "Chat", rows: [
    ["Send message",      "Enter"],
    ["New line",          "Shift+Enter"],
    ["Threads panel",     "Ctrl+Shift+T"],
    ["Context panel",     "Ctrl+Shift+C"],
    ["Advanced panel",    "Ctrl+Shift+O"],
  ]},
];

export function ShortcutsModal({ mode = "advanced" }) {
  const groups = mode === "simple" ? SIMPLE_SHORTCUT_GROUPS : SHORTCUT_GROUPS;
  // Pair groups into 2 columns: [0,1], [2,3], [4]
  const pairs = [];
  for (let i = 0; i < groups.length; i += 2)
    pairs.push([groups[i], groups[i + 1]]);

  const KeyBadge = ({ k }) => (
    <span style={{
      display: "inline-block", fontFamily: "monospace", fontSize: 9, fontWeight: 700,
      background: T.surface2, color: T.accent2,
      border: `1px solid ${T.border}`,
      borderRadius: 3, padding: "2px 6px", whiteSpace: "nowrap",
    }}>{k}</span>
  );

  const GroupCol = ({ group }) => group ? (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 8, fontWeight: 700, color: T.muted, letterSpacing: "0.12em",
                    textTransform: "uppercase", marginBottom: 6 }}>
        {group.title}
      </div>
      {group.rows.map(([action, key]) => (
        <div key={action} style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "4px 0", gap: 8, borderBottom: `1px solid ${T.border}22`,
        }}>
          <span style={{ fontSize: 11, color: T.mutedLt, minWidth: 0, overflow: "hidden",
                         textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{action}</span>
          <KeyBadge k={key} />
        </div>
      ))}
    </div>
  ) : <div style={{ flex: 1 }} />;

  return (
    <div style={{ minWidth: 560, maxWidth: 640 }}>
      <h2 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700, color: T.text }}>
        Keyboard Shortcuts
      </h2>
      <div style={{ maxHeight: 440, overflowY: "auto", paddingRight: 4, display: "flex",
                    flexDirection: "column", gap: 18 }}>
        {pairs.map((pair, i) => (
          <div key={i} style={{ display: "flex", gap: 28 }}>
            <GroupCol group={pair[0]} />
            <div style={{ width: 1, background: T.border, flexShrink: 0 }} />
            <GroupCol group={pair[1]} />
          </div>
        ))}
      </div>
    </div>
  );
}
