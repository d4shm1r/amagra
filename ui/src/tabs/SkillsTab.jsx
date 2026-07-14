import { useState, useEffect } from "react";
import { T, FONT_MONO } from "@/styles/theme";
import { PageHeader } from "@/components/ui";

import { API } from "@/lib/api";

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

  const load = () => {
    setLoading(true);
    fetch(`${API}/cos/skills`)
      .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
      .then(d => { setSkills(d.skills || []); setError(null); })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <div>
      <style>{`
        .skl-refresh{
          position:relative; overflow:hidden; padding:7px 20px; border-radius:40px;
          font-family:inherit; font-size:11.5px; font-weight:600; letter-spacing:-0.01em;
          color:#5C4030; border:2px solid transparent; cursor:pointer;
          background:linear-gradient(#FCFAF7,#FCFAF7) padding-box, linear-gradient(145deg,#FFE880,#DEB838,#C48808) border-box;
          box-shadow:4px 4px 10px rgba(72,52,28,0.11),-2px -2px 7px rgba(255,255,255,0.80),inset 0 1px 1px rgba(255,255,255,0.94),inset 0 -1px 2px rgba(138,99,36,0.06);
          transition:transform 200ms cubic-bezier(0.22,1,0.36,1), box-shadow 200ms ease-out, color 140ms ease;
        }
        .skl-refresh::before{content:'';position:absolute;top:0;left:0;right:0;bottom:50%;background:linear-gradient(180deg,rgba(255,255,255,0.46) 0%,rgba(255,255,255,0) 100%);border-radius:40px 40px 0 0;pointer-events:none;z-index:1;}
        .skl-refresh:hover{color:#6C4C00;transform:translateY(-1px);box-shadow:6px 6px 16px rgba(62,44,20,0.17),-2px -2px 8px rgba(255,255,255,0.94),inset 0 1px 1px rgba(255,255,255,0.94),inset 0 -1px 2px rgba(138,99,36,0.10),0 0 24px rgba(196,136,8,0.13);}
      `}</style>

      {/* Header */}
      <PageHeader
        center
        title="Skills"
        subtitle={skills.length > 0 ? `${skills.length} skill nodes · phrase-weighted routing` : "Loading skill graph…"}
      >
        <button className="skl-refresh" onClick={load}>↻ Refresh</button>
      </PageHeader>

      {error && (
        <div style={{ color: T.error, background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 5, padding: "8px 14px", marginBottom: 16, fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Grid */}
      {!loading && skills.length === 0 && !error && (
        <div style={{ color: T.muted, fontSize: 13, textAlign: "center", padding: "40px 0" }}>
          No skills yet.
        </div>
      )}

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: 16,
      }}>
        {skills.map(skill => (
          <SkillCard key={skill.name} skill={skill} />
        ))}
      </div>
    </div>
  );
}
