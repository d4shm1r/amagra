import { useEffect, useState } from "react";
import { API } from "@/lib/api";
import { VERSION } from "@/config/constants";
import { BUILD_PHASES } from "@/config/history";
import {
  Page, PageHeader, Section, Card, Grid, Row, Stack,
  Wordmark, Pill, Caption, Lead, DataRow, Inline,
} from "@/components/ui";
import InspectOverviewPanel from "@/components/panels/InspectOverviewPanel";
import IdentityPanel from "@/components/panels/IdentityPanel";

const FACTS = [
  ["Architecture", "Signal-first routing"],
  ["Memory",       "FAISS + LRU cache"],
  ["Agents",       "Specialist + Coordinator"],
  ["Eval",         "Dual-trajectory critic"],
  ["UI",           "React + Vite"],
  ["API",          "FastAPI / Python"],
];

export default function AboutTab({ coherence, apiStatus, onNav }) {
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
      .then(d => d?.agents && setWorking(d.agents.filter(a => a.status === "running").length))
      .catch(() => {});
  }, []);

  const online = apiStatus === "online";
  const latest = BUILD_PHASES[BUILD_PHASES.length - 1];

  return (
    <Page>
      <PageHeader
        center
        title="About"
        subtitle="What Amagra is — and the live state of the engine on this machine."
      />

      <Stack gap="lg">
        {/* Identity */}
        <Card pad="md">
          <Row gap="md" align="baseline" wrap>
            <Wordmark />
            <Pill tone="gold" strong>v{VERSION}</Pill>
            <Caption>Phase {latest.id} — {latest.title}</Caption>
          </Row>
          <Lead tone="muted">
            The AI you can trust with long-term work — it remembers what you've done, explains every
            decision, and runs entirely on your hardware.
          </Lead>
          <Grid min={200} gap="sm">
            {FACTS.map(([k, v]) => (
              <Caption key={k}>
                {k}: <Inline role="caption" tone="default">{v}</Inline>
              </Caption>
            ))}
          </Grid>
        </Card>

        {/* Live snapshot — recent decisions + recent work */}
        <InspectOverviewPanel embedded onNav={onNav} />

        {/* Who this instance is — intrinsic state you set, learned state it earned */}
        <IdentityPanel />

        {/* Live engine readout */}
        <Section title="System" icon="⚙">
          <DataRow label="API" mono tone="gold" value={API || "same-origin"} />
          <DataRow label="Status" tone={online ? "success" : "error"}>
            <Inline role="small" tone={online ? "success" : "error"} weight={600}>
              {online ? "● Online" : "○ Offline"}
            </Inline>
          </DataRow>
          <DataRow label="Model"       value={status?.model ?? "phi4-mini"} />
          <DataRow label="GPU"         value={status?.gpu ?? "RTX 2050"} />
          <DataRow label="Backend"     value={memStats?.backend?.type ?? "FAISSBackend"} />
          <DataRow label="Working now" mono tone="gold" value={working} />
          <DataRow label="Decisions"   mono tone="gold" value={decStats?.total} />
          <DataRow label="Reflect rate" mono tone="gold"
                   value={decStats ? `${Math.round((decStats.reflect_rate || 0) * 100)}%` : null} />
          <DataRow label="Conflicts"      mono tone="gold" value={decStats?.conflicts} />
          <DataRow label="Tasks pending"  mono tone="gold" value={status?.tasks?.pending} />
          <DataRow label="Tasks done"     mono tone="gold" value={status?.tasks?.done} />
          <DataRow label="Tasks failed"   mono tone="gold" value={status?.tasks?.failed} />
          <DataRow label="Memories total" mono tone="gold" value={memStats?.total} />
          <DataRow label="Prune ready"    mono tone="gold" value={memStats?.prune_candidates} />
          <DataRow label="Never recalled" mono tone="gold" value={memStats?.never_used} />
          {coherence && <>
            <DataRow label="Coherence C(t)"   mono tone="gold" value={coherence.C?.toFixed(4)} />
            <DataRow label="Routing"          mono tone="gold" value={coherence.c_routing?.toFixed(3)} />
            <DataRow label="Calibration"      mono tone="gold" value={coherence.c_calib?.toFixed(3)} />
            <DataRow label="Memories active"  mono tone="gold" value={coherence.mem_n} />
          </>}
        </Section>
      </Stack>
    </Page>
  );
}
