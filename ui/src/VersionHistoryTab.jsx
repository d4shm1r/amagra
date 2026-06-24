import { useState, useMemo } from "react";
import { BUILD_PHASES, VERSION_EPOCHS, ROADMAP } from "./constants";
import { T } from "./theme";
import { PageHeader } from "./ObsShared";

const STATUS_STYLE = {
  done:    { label: "Complete",    color: "#15803D" },
  planned: { label: "Planned",     color: "#9A7A60" },
  ready:   { label: "Ready",       color: "#0F766E" },
  partial: { label: "In Progress", color: "#C2410C" },
  next:    { label: "In Progress", color: "#C2410C" },
};

const PRIO_COLOR = { high: T.error, medium: T.warn, low: T.muted };

// ── Helpers ────────────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: "0.07em",
      padding: "2px 7px", borderRadius: 3,
      background: `${color}1A`, color,
      border: `1px solid ${color}44`, flexShrink: 0,
    }}>{label}</span>
  );
}

function SectionHead({ label, color, count }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
      <span style={{ fontSize: 11, fontWeight: 800, color, letterSpacing: "0.08em", textTransform: "uppercase" }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 1, background: `${color}33` }} />
      {count != null && <span style={{ fontSize: 10, color: T.muted }}>{count} phase{count !== 1 ? "s" : ""}</span>}
    </div>
  );
}

// ── Phase card ─────────────────────────────────────────────────
function PhaseCard({ phase, roadmap = false, highlight = false }) {
  const [open, setOpen] = useState(highlight);
  const ss      = STATUS_STYLE[phase.status] || STATUS_STYLE.planned;
  const steps   = phase.steps || phase.items || [];
  const isNow   = phase.status === "next";

  return (
    <div
      onClick={() => setOpen(o => !o)}
      style={{
        display: "flex", flexDirection: "column",
        background: highlight ? `${phase.color}07` : T.bg,
        border: `1px solid ${open || highlight
          ? phase.color + (highlight ? "88" : "55")
          : phase.color + "22"}`,
        borderRadius: 6,
        padding: "11px 14px",
        cursor: "pointer",
        transition: "border-color .15s",
        marginBottom: 6,
        boxShadow: highlight ? `0 0 12px ${phase.color}22` : "none",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        {/* Dot */}
        <div style={{
          width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
          background: phase.color,
          boxShadow: (open || highlight) ? `0 0 6px ${phase.color}88` : "none",
        }} />

        {/* Version */}
        <span style={{
          fontSize: 9, fontWeight: 700, fontFamily: "monospace",
          color: phase.color, background: `${phase.color}18`,
          border: `1px solid ${phase.color}40`,
          padding: "1px 6px", borderRadius: 3, flexShrink: 0, letterSpacing: "0.04em",
        }}>{phase.version}</span>

        {/* NOW badge */}
        {isNow && (
          <span style={{
            fontSize: 8, fontWeight: 800, letterSpacing: "0.1em",
            padding: "2px 6px", borderRadius: 3, flexShrink: 0,
            background: `${phase.color}22`, color: phase.color,
            border: `1px solid ${phase.color}55`,
          }}>NOW</span>
        )}

        {/* Title */}
        <span style={{ fontSize: 12, fontWeight: 600, color: T.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {phase.label ? `${phase.label} — ` : ""}{phase.title}
        </span>

        {/* Priority */}
        {roadmap && phase.priority && (
          <Badge label={phase.priority} color={PRIO_COLOR[phase.priority]} />
        )}

        {/* Status */}
        <Badge label={ss.label} color={ss.color} />

        {/* Steps count (collapsed only) */}
        {!open && steps.length > 0 && (
          <span style={{ fontSize: 10, color: T.muted, flexShrink: 0, fontFamily: "monospace" }}>
            {steps.length}
          </span>
        )}

        {/* Date */}
        {phase.date && (
          <span style={{ fontSize: 10, color: T.muted, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
            {phase.date}
          </span>
        )}

        {/* Chevron */}
        <span style={{ fontSize: 10, color: phase.color, opacity: .5, flexShrink: 0, transition: "transform .15s", display: "inline-block", transform: open ? "rotate(180deg)" : "none" }}>▼</span>
      </div>

      {/* Summary (collapsed) */}
      {!open && phase.summary && (
        <div style={{ fontSize: 11, color: T.muted, marginTop: 5, marginLeft: 17, lineHeight: 1.55, paddingLeft: 2 }}>
          {phase.summary}
        </div>
      )}

      {/* Expanded body */}
      {open && (
        <div style={{ marginTop: 10, marginLeft: 17, display: "flex", flexDirection: "column", gap: 5 }}>
          {phase.summary && (
            <div style={{ fontSize: 11, color: T.mutedLt, lineHeight: 1.6, marginBottom: 6 }}>
              {phase.summary}
            </div>
          )}
          {steps.map((step, i) => {
            const done = phase.status === "done" || step.includes("✅");
            const text = step.replace(/\s*✅$/, "").replace(" ✅", "");
            return (
              <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ color: done ? T.success : phase.color, fontSize: 10, flexShrink: 0, marginTop: 1, fontFamily: "monospace" }}>
                  {done ? "✓" : "□"}
                </span>
                <span style={{
                  fontSize: 11, color: done ? T.text : T.muted, lineHeight: 1.55,
                }}>{text}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Timeline minimap ───────────────────────────────────────────
function EpochNav({ epochs, phaseMap, onJump }) {
  return (
    <div style={{
      display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 18,
    }}>
      {epochs.filter(e => e.phases.length > 0).map(epoch => (
        <button
          key={epoch.version}
          onClick={() => onJump(epoch.version)}
          style={{
            padding: "3px 9px", borderRadius: 4, fontSize: 10, fontWeight: 700,
            fontFamily: "monospace", cursor: "pointer",
            background: `${epoch.color}18`,
            color: epoch.color,
            border: `1px solid ${epoch.color}44`,
            letterSpacing: "0.04em",
          }}
        >{epoch.version}</button>
      ))}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────
export default function VersionHistoryTab() {
  const [showRoadmap, setShowRoadmap] = useState(false);
  const [search,      setSearch]      = useState("");

  const latest     = BUILD_PHASES[BUILD_PHASES.length - 1];
  const totalSteps = BUILD_PHASES.reduce((s, p) => s + (p.steps?.length || 0), 0);
  const startDate  = BUILD_PHASES[0].date;
  const endDate    = latest.date;
  const phaseMap   = useMemo(() => Object.fromEntries(BUILD_PHASES.map(p => [p.id, p])), []);

  const semverDesc = (a, b) => {
    const parts = v => (v || "").replace(/^v/, "").split(".").map(n => parseInt(n, 10) || 0);
    const [a0,a1,a2] = parts(a.version), [b0,b1,b2] = parts(b.version);
    return (b0 - a0) || (b1 - a1) || (b2 - a2);
  };

  // Search filter
  const matchPhase = (phase) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      phase.title?.toLowerCase().includes(q) ||
      phase.summary?.toLowerCase().includes(q) ||
      phase.version?.toLowerCase().includes(q) ||
      (phase.steps || phase.items || []).some(s => s.toLowerCase().includes(q))
    );
  };

  const handleJump = (version) => {
    const el = document.getElementById(`epoch-${version}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Roadmap split
  const upcoming   = ROADMAP.filter(p => p.status !== "done");
  const technical  = upcoming.filter(p => !p.type);
  const commercial = upcoming.filter(p => p.type === "commercial");

  return (
    <div style={{ animation: "fadeIn .2s" }}>

      <PageHeader title="Releases" subtitle="Every shipped phase and version epoch — the full build history." />

      {/* ── Stats bar ── */}
      <div className="lux-card" style={{
        display: "flex", gap: 0,
        overflow: "hidden", marginBottom: 20,
      }}>
        {[
          { label: "Phases",       value: BUILD_PHASES.length, color: T.accent },
          { label: "Version",      value: latest.version,      color: "#0F766E" },
          { label: "Steps",        value: totalSteps,          color: T.warn },
          { label: "Epochs",       value: VERSION_EPOCHS.filter(e => e.phases.length > 0).length, color: "#7E3F8F" },
          { label: "Started",      value: startDate,           color: T.muted },
          { label: "Latest",       value: endDate,             color: T.muted },
        ].map((s, i, arr) => (
          <div key={s.label} style={{
            flex: 1, padding: "12px 14px", textAlign: "center",
            borderRight: i < arr.length - 1 ? `1px solid ${T.border}` : "none",
          }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: s.color, fontFamily: "monospace", lineHeight: 1.1 }}>
              {s.value}
            </div>
            <div style={{ fontSize: 10, color: T.muted, marginTop: 3, letterSpacing: "0.05em" }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* ── Toggle ── */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
        <button
          onClick={() => { setShowRoadmap(false); setSearch(""); }}
          style={{
            padding: "5px 14px", borderRadius: 6, fontSize: 11, fontWeight: 600,
            fontFamily: "inherit", cursor: "pointer",
            background: !showRoadmap ? `${T.accent}22` : "transparent",
            color: !showRoadmap ? T.accent : T.muted,
            border: `1px solid ${!showRoadmap ? T.accent + "55" : T.border}`,
          }}
        >Completed Releases</button>
        <button
          onClick={() => { setShowRoadmap(true); setSearch(""); }}
          style={{
            padding: "5px 14px", borderRadius: 6, fontSize: 11, fontWeight: 600,
            fontFamily: "inherit", cursor: "pointer",
            background: showRoadmap ? "#9A6C0022" : "transparent",
            color: showRoadmap ? T.warn : T.muted,
            border: `1px solid ${showRoadmap ? "#9A6C0055" : T.border}`,
          }}
        >Roadmap — Upcoming</button>

        {/* Search */}
        <div style={{
          flex: 1, maxWidth: 280, display: "flex", alignItems: "center", gap: 6,
          background: T.surface2, border: `1px solid ${T.border}`,
          borderRadius: 6, padding: "4px 10px",
        }}>
          <span style={{ fontSize: 12, color: T.muted, flexShrink: 0 }}>⌕</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search phases, steps…"
            style={{
              flex: 1, background: "transparent", border: "none",
              color: T.text, fontSize: 11, outline: "none", fontFamily: "inherit",
            }}
          />
          {search && (
            <button onClick={() => setSearch("")} style={{ background: "none", border: "none", color: T.muted, cursor: "pointer", fontSize: 12, padding: 0 }}>✕</button>
          )}
        </div>
      </div>

      {!showRoadmap ? (
        /* ── Completed releases ── */
        <div>
          {/* Epoch quick-jump (only when not searching) */}
          {!search && (
            <EpochNav
              epochs={VERSION_EPOCHS}
              phaseMap={phaseMap}
              onJump={handleJump}
            />
          )}

          {VERSION_EPOCHS.map((epoch) => {
            const phases = epoch.phases
              .map(id => phaseMap[id])
              .filter(Boolean)
              .filter(matchPhase)
              .slice()
              .sort(semverDesc);

            if (phases.length === 0) return null;

            // Date range from phases
            const dates  = epoch.phases.map(id => phaseMap[id]?.date).filter(Boolean);
            const first  = dates[0];
            const last   = dates[dates.length - 1];
            const range  = first && last && first !== last ? `${first} — ${last}` : first || "";

            const stepCount = phases.reduce((s, p) => s + (p.steps?.length || 0), 0);

            return (
              <div key={epoch.version} id={`epoch-${epoch.version}`} style={{ marginBottom: 28, scrollMarginTop: 12 }}>
                {/* Epoch header */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, paddingBottom: 6, borderBottom: `1px solid ${epoch.color}22` }}>
                  <span style={{ fontSize: 14, fontWeight: 800, color: epoch.color, fontFamily: "monospace", letterSpacing: "-0.01em" }}>
                    {epoch.version}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>
                    {epoch.label}
                  </span>
                  <div style={{ flex: 1 }} />
                  {range && <span style={{ fontSize: 10, color: T.muted }}>{range}</span>}
                  <span style={{ fontSize: 10, color: T.muted, fontFamily: "monospace" }}>
                    {phases.length}p · {stepCount}s
                  </span>
                </div>

                {/* Phase cards */}
                <div style={{ paddingLeft: 10, borderLeft: `2px solid ${epoch.color}28` }}>
                  {phases.map(phase => (
                    <PhaseCard key={phase.id} phase={phase} />
                  ))}
                </div>
              </div>
            );
          })}

          {/* No results */}
          {search && VERSION_EPOCHS.every(e =>
            e.phases.map(id => phaseMap[id]).filter(Boolean).filter(matchPhase).length === 0
          ) && (
            <div style={{ padding: "40px 0", textAlign: "center" }}>
              <div style={{ fontSize: 13, color: T.muted }}>No phases match "{search}"</div>
              <button onClick={() => setSearch("")} style={{ marginTop: 10, background: "transparent", border: `1px solid ${T.border}`, color: T.muted, padding: "4px 12px", borderRadius: 6, fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
                Clear search
              </button>
            </div>
          )}
        </div>
      ) : (
        /* ── Roadmap — uncompleted phases only ── */
        <div>
          <div style={{ marginBottom: 18, fontSize: 11, color: T.muted, lineHeight: 1.6 }}>
            Uncompleted phases only. Continues from Phase{" "}
            <span style={{ color: T.text, fontFamily: "monospace" }}>{BUILD_PHASES[BUILD_PHASES.length - 1].id}</span>{" — "}
            nearest target{" "}
            <span style={{ color: T.warn, fontFamily: "monospace" }}>{upcoming[0]?.version ?? "—"}</span>.
          </div>

          {/* Technical track */}
          {technical.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <SectionHead label="Technical Track" color="#0F766E" count={technical.length} />
              <div style={{ paddingLeft: 10, borderLeft: "2px solid #0F766E28" }}>
                {technical.filter(matchPhase).map(phase => (
                  <PhaseCard key={phase.id} phase={phase} roadmap highlight={phase.status === "next"} />
                ))}
              </div>
            </div>
          )}

          {/* Commercial track */}
          {commercial.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <SectionHead label="Revenue Track" color={T.warn} count={commercial.length} />
              <div style={{ paddingLeft: 10, borderLeft: `2px solid ${T.warn}28` }}>
                {commercial.filter(matchPhase).map(phase => (
                  <PhaseCard key={phase.id} phase={phase} roadmap />
                ))}
              </div>
            </div>
          )}

          {/* No results */}
          {search && [...technical, ...commercial].filter(matchPhase).length === 0 && (
            <div style={{ padding: "40px 0", textAlign: "center" }}>
              <div style={{ fontSize: 13, color: T.muted }}>No phases match "{search}"</div>
              <button onClick={() => setSearch("")} style={{ marginTop: 10, background: "transparent", border: `1px solid ${T.border}`, color: T.muted, padding: "4px 12px", borderRadius: 6, fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
                Clear search
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
