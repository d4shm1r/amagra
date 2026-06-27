import { useState, useEffect, useMemo } from "react";
import { T, FONT_MONO } from "./theme";
import { PageHeader, RefreshBtn } from "./ObsShared";

import { API } from "./api";

const COMPLEXITY_COLOR = {
  simple:   T.success,
  moderate: "#9A6C00",
  complex:  "#7E3F8F",
};

const AGENT_COLORS = {
  python_dev:         "#0E7490",
  ai_ml:              "#7E3F8F",
  it_networking:      "#15803D",
  dotnet_dev:         "#0F766E",
  knowledge_learning: "#9A6C00",
  terse:              "#1E5A8A",
  data_analyst:       "#C77B3B",
  writer:             "#A07408",
  web_dev:            "#0E7490",
  devops:             "#0F766E",
};

function agentColor(agent) {
  return AGENT_COLORS[agent] || T.muted;
}

function AgentBadge({ agent }) {
  const color = agentColor(agent);
  return (
    <span style={{
      background: `${color}18`, border: `1px solid ${color}44`,
      color, borderRadius: 99, padding: "2px 9px",
      fontSize: 10, fontFamily: FONT_MONO, fontWeight: 700, whiteSpace: "nowrap",
    }}>
      {agent.replace(/_/g, " ")}
    </span>
  );
}

function CategoryBadge({ cat }) {
  return (
    <span style={{
      background: `${T.accent}14`, border: `1px solid ${T.accent}33`,
      color: T.accent, borderRadius: 99, padding: "2px 9px",
      fontSize: 10, fontFamily: FONT_MONO, whiteSpace: "nowrap",
    }}>
      {cat}
    </span>
  );
}

function SkillCard({ skill }) {
  const complexity = skill.complexity || "simple";
  const cc = COMPLEXITY_COLOR[complexity] || T.muted;

  return (
    <div className="lux-card lux-card-i" style={{
      padding: "16px 18px",
      display: "flex", flexDirection: "column", gap: 9,
    }}>
      <div style={{ display: "flex", gap: 6, alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: T.text, lineHeight: 1.3 }}>
          {skill.name}
        </div>
        <span style={{
          fontSize: 9, fontWeight: 700, fontFamily: FONT_MONO,
          color: cc, background: `${cc}18`,
          border: `1px solid ${cc}44`,
          borderRadius: 3, padding: "2px 6px", flexShrink: 0, marginTop: 1,
        }}>
          {complexity}
        </span>
      </div>

      <div style={{ fontSize: 11, color: T.muted, lineHeight: 1.5 }}>
        {skill.description || "—"}
      </div>

      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "center" }}>
        <AgentBadge agent={skill.agent} />
        <CategoryBadge cat={skill.category} />
        <span style={{
          marginLeft: "auto", fontSize: 9, color: T.muted,
          fontFamily: FONT_MONO, flexShrink: 0,
        }}>
          {skill.keywords} kw
        </span>
      </div>
    </div>
  );
}

export default function SkillsTab() {
  const [skills,  setSkills]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [query,   setQuery]   = useState("");
  const [agentF,  setAgentF]  = useState("all");
  const [catF,    setCatF]    = useState("all");

  const load = () => {
    setLoading(true);
    fetch(`${API}/cos/skills`)
      .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
      .then(d => { setSkills(d.skills || []); setError(null); })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const agents     = useMemo(() => ["all", ...new Set(skills.map(s => s.agent))],     [skills]);
  const categories = useMemo(() => ["all", ...new Set(skills.map(s => s.category))],  [skills]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return skills.filter(s => {
      if (agentF !== "all" && s.agent    !== agentF) return false;
      if (catF   !== "all" && s.category !== catF)   return false;
      if (!q) return true;
      return (
        s.name.toLowerCase().includes(q)        ||
        s.description?.toLowerCase().includes(q) ||
        s.agent.toLowerCase().includes(q)        ||
        s.category.toLowerCase().includes(q)
      );
    });
  }, [skills, query, agentF, catF]);

  const FilterBtn = ({ val, current, set, colorFn }) => {
    const active = current === val;
    const color  = val === "all" ? T.accent : (colorFn ? colorFn(val) : T.accent);
    return (
      <button onClick={() => set(val)} style={{
        padding: "4px 13px", borderRadius: 99, fontSize: 11,
        fontFamily: "inherit", cursor: "pointer", border: "none",
        background: active ? `${color}22` : T.surface2,
        color: active ? color : T.muted,
        fontWeight: active ? 700 : 400,
        whiteSpace: "nowrap",
        transition: "background .1s, color .1s",
      }}>
        {val === "all" ? "All" : val.replace(/_/g, " ")}
      </button>
    );
  };

  return (
    <div>
      {/* Header */}
      <PageHeader
        title="Skills"
        subtitle={skills.length > 0 ? `${skills.length} skill nodes · phrase-weighted routing` : "Loading skill graph…"}
      >
        <RefreshBtn onClick={load} />
      </PageHeader>

      {error && (
        <div style={{ color: T.error, background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 5, padding: "8px 14px", marginBottom: 16, fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Search + filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search skills…"
          style={{
            background: T.surface, border: `1px solid ${T.border}`,
            borderRadius: 99, color: T.text, padding: "7px 16px",
            fontSize: 12, fontFamily: "inherit", outline: "none",
            width: 240, flex: "0 0 auto",
            transition: "border-color .15s",
          }}
          onFocus={e  => { e.target.style.borderColor = `${T.accent}88`; }}
          onBlur={e   => { e.target.style.borderColor = T.border; }}
        />
        {query && (
          <button onClick={() => setQuery("")} style={{
            background: "transparent", border: "none", color: T.error,
            cursor: "pointer", fontSize: 13, padding: "2px 4px",
          }}>✕</button>
        )}
      </div>

      {/* Agent filter row */}
      <div style={{ display: "flex", gap: 5, marginBottom: 8, flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: 9, color: T.muted, fontWeight: 700, letterSpacing: "0.1em",
                       textTransform: "uppercase", flexShrink: 0, marginRight: 4 }}>Agent</span>
        {agents.map(a => (
          <FilterBtn key={a} val={a} current={agentF} set={setAgentF} colorFn={agentColor} />
        ))}
      </div>

      {/* Category filter row */}
      <div style={{ display: "flex", gap: 5, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: 9, color: T.muted, fontWeight: 700, letterSpacing: "0.1em",
                       textTransform: "uppercase", flexShrink: 0, marginRight: 4 }}>Category</span>
        {categories.map(c => (
          <FilterBtn key={c} val={c} current={catF} set={setCatF} />
        ))}
      </div>

      {/* Count row */}
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 12 }}>
        {loading ? "Loading…" : `${filtered.length} / ${skills.length} skills`}
        {(agentF !== "all" || catF !== "all" || query) && (
          <button onClick={() => { setAgentF("all"); setCatF("all"); setQuery(""); }}
            style={{ marginLeft: 8, background: "transparent", border: "none",
                     color: T.accent, cursor: "pointer", fontSize: 11, fontFamily: "inherit" }}>
            Clear filters
          </button>
        )}
      </div>

      {/* Grid */}
      {!loading && filtered.length === 0 && (
        <div style={{ color: T.muted, fontSize: 13, textAlign: "center", padding: "40px 0" }}>
          No skills match "{query}"
        </div>
      )}

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: 12,
      }}>
        {filtered.map(skill => (
          <SkillCard key={skill.name} skill={skill} />
        ))}
      </div>
    </div>
  );
}
