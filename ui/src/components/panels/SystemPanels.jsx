// ── SystemPanels ──────────────────────────────────────────────────────────────
// Live panels rehomed from the retired Progress tab (v1.7.1 menu declutter).
//   • MemoryAdminPanel — export / consolidate / auto-resolve / prune actions and
//     the "at-risk" list. Lives inside the Memory surface (MemoryBrowserTab
//     already renders the stats, so this adds only the actions it was missing).
//   • FeedbackLoopPanel — thumbs rollup by agent. A Diagnostics section.
// Each is self-contained (owns its own fetches) so it can drop into any tab.
import { useState, useEffect, useCallback } from "react";
import { API } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import {
  Section, Well, Row, Stack, Spacer, Button, Notice, Disclosure,
  StatStrip, BarRow, Micro, Small, Caption, Inline, EmptyState, useConfirm,
} from "@/components/ui";

// ── Memory admin: export / consolidate / auto-resolve / prune + at-risk ───────
// `stats` is the /memory/stats object the host tab already fetched; `onChanged`
// lets the host refresh its own view after a destructive action.
export function MemoryAdminPanel({ stats, onChanged }) {
  const [atRisk,            setAtRisk]            = useState([]);
  const [atRiskOpen,        setAtRiskOpen]        = useState(false);
  const [pruning,           setPruning]           = useState(false);
  const [pruneResult,       setPruneResult]       = useState(null);
  const [consolidating,     setConsolidating]     = useState(false);
  const [consolidateResult, setConsolidateResult] = useState(null);
  const [resolving,         setResolving]         = useState(false);
  const [resolveResult,     setResolveResult]     = useState(null);
  const confirm = useConfirm();

  const loadAtRisk = useCallback(() => {
    fetch(`${API}/memory/at-risk?n=20`).then(r => r.json())
      .then(d => setAtRisk(d.at_risk || [])).catch(() => {});
  }, []);
  useEffect(() => { loadAtRisk(); }, [loadAtRisk]);

  const prunable = stats?.prune_candidates ?? 0;

  const runPrune = async () => {
    setPruning(true); setPruneResult(null);
    try {
      const d = await fetch(`${API}/memory/prune`, { method: "POST" }).then(r => r.json());
      setPruneResult(d); loadAtRisk(); onChanged?.();
    } catch { setPruneResult({ error: "Request failed" }); }
    setPruning(false);
  };

  const runConsolidate = async () => {
    setConsolidating(true); setConsolidateResult(null);
    try {
      const d = await fetch(`${API}/memory/consolidate`, { method: "POST" }).then(r => r.json());
      setConsolidateResult(d); loadAtRisk(); onChanged?.();
    } catch { setConsolidateResult({ error: "Request failed" }); }
    setConsolidating(false);
  };

  // Rehomed from the retired CogOS tab, which was the only place this action
  // existed — stranded on a diagnostics screen, next to a read-only list of
  // contradictions, while every other memory action lived here.
  //
  // It asks first. CogOS fired it on a single click: it deletes one side of
  // each contradicting pair, which is not something to discover after the fact,
  // and the threshold is doing real work (0.90 cosine) that the reader should
  // see before agreeing to it.
  const runAutoResolve = async () => {
    const ok = await confirm({
      title: "Auto-resolve contradictions?",
      body: "Near-identical contradicting pairs (cosine > 0.90) are merged, keeping the "
          + "higher-quality memory and deleting the other. This cannot be undone.",
      confirmLabel: "Resolve",
      danger: true,
    });
    if (!ok) return;

    setResolving(true); setResolveResult(null);
    try {
      const d = await fetch(`${API}/memory/auto-resolve?threshold=0.90`, { method: "POST" })
        .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); });
      setResolveResult(d); loadAtRisk(); onChanged?.();
    } catch (e) { setResolveResult({ error: e.message || "Request failed" }); }
    setResolving(false);
  };

  return (
    <Section title="Memory health">
      <Stack gap="sm">
        <Row gap="xs" wrap>
          {[["csv", "memories.csv"], ["json", "memories.json"], ["md", "memories.md"]].map(([fmt, fname]) => (
            <a key={fmt} href={`${API}/memory/export.${fmt}`} download={fname}
               className="btn-ghost">
              {fmt.toUpperCase()}
            </a>
          ))}
          <Button variant="ghost" size="sm" onClick={runConsolidate} disabled={consolidating}>
            {consolidating ? "Running…" : "Consolidate"}
          </Button>
          <Button variant="ghost" size="sm" onClick={runAutoResolve} disabled={resolving}>
            {resolving ? "Resolving…" : "Auto-resolve"}
          </Button>
          {/* Prune is the destructive one and reads as it: danger styling, and
              disabled outright when there is nothing to prune. */}
          <Button variant="danger" size="sm" onClick={runPrune} disabled={pruning || prunable === 0}>
            {pruning ? "Pruning…" : `Prune${prunable > 0 ? ` (${prunable})` : ""}`}
          </Button>
        </Row>

        {/* Result banners. These used to be three hand-mixed tint recipes —
            a pale red, a pale green — re-deriving by eye what Notice already
            computes from a tone, and drifting from it in the process. */}
        {consolidateResult && (
          <Notice tone={consolidateResult.error ? "error" : "success"}>
            {consolidateResult.error
              ? `Error: ${consolidateResult.error}`
              : `Removed ${consolidateResult.removed} near-duplicates · ${consolidateResult.remaining} memories remaining`}
          </Notice>
        )}
        {resolveResult && (
          <Notice tone={resolveResult.error ? "error" : "success"}>
            {resolveResult.error
              ? `Error: ${resolveResult.error}`
              : `Resolved ${resolveResult.resolved} contradicting pair${resolveResult.resolved === 1 ? "" : "s"} · ${resolveResult.remaining} memories remaining${resolveResult.dry_run ? " (dry run — nothing changed)" : ""}`}
          </Notice>
        )}
        {pruneResult && (
          <Notice tone={pruneResult.error ? "error" : "success"}>
            {pruneResult.error
              ? `Error: ${pruneResult.error}`
              : `Deleted ${pruneResult.deleted} entries · ${pruneResult.remaining} remaining`}
          </Notice>
        )}

        <Disclosure
          title="At risk"
          subtitle={`${atRisk.length} memories scoring 0.55–0.70 and recalled at most once`}
          open={atRiskOpen}
          onToggle={() => setAtRiskOpen(o => !o)}
        />
        {atRiskOpen && (
          atRisk.length === 0
            ? <EmptyState msg="No at-risk memories right now." />
            : <Stack gap="xs">
                {atRisk.map(m => {
                  const q = m.quality || 0;
                  return (
                    <Well key={m.id} tone={q < 0.60 ? "error" : "warn"}>
                      <Row gap="sm">
                        <Inline mono weight={700} tone={q < 0.60 ? "error" : "warn"}>
                          {q.toFixed(3)}
                        </Inline>
                        <Micro>{m.agent?.replace(/_/g, " ")}</Micro>
                        <Micro>{m.type}</Micro>
                        <Small tone="default">{m.preview}</Small>
                        <Spacer />
                        <Micro>×{m.use_count}</Micro>
                      </Row>
                    </Well>
                  );
                })}
              </Stack>
        )}
      </Stack>
    </Section>
  );
}

// ── Feedback loop: thumbs rollup by agent ────────────────────────────────────
function buildFeedbackStats(entries) {
  const byAgent = {};
  for (const e of entries) {
    if (!byAgent[e.agent]) byAgent[e.agent] = { up: 0, down: 0 };
    if (e.rating === 1)  byAgent[e.agent].up++;
    if (e.rating === -1) byAgent[e.agent].down++;
  }
  return byAgent;
}

export function FeedbackLoopPanel() {
  const { data } = usePoll("/feedback?limit=500", { interval: 60_000 });
  const feedback = Array.isArray(data) ? data : [];

  const total     = feedback.length;
  const totalUp   = feedback.filter(f => f.rating === 1).length;
  const totalDown = feedback.filter(f => f.rating === -1).length;
  const agentRows = Object.entries(buildFeedbackStats(feedback))
    .sort((a, b) => (b[1].up + b[1].down) - (a[1].up + a[1].down));

  if (total === 0) {
    return (
      <Section title="Feedback loop">
        <EmptyState msg="No ratings yet — rate any answer in Chat and the rollup starts here." />
      </Section>
    );
  }

  const pct = (n) => Math.round((n / total) * 100);

  return (
    <Section title="Feedback loop" hint="the human signal on answer quality">
      <Stack gap="md">
        <StatStrip items={[
          { label: "Total ratings", value: total, tone: "gold" },
          { label: "Positive", value: totalUp,   sub: `${pct(totalUp)}%`,   tone: "success" },
          { label: "Negative", value: totalDown, sub: `${pct(totalDown)}%`, tone: "error" },
        ]} />

        {/* Per agent, share positive. The bar is the share and the number is the
            count, so a 100% built on two ratings cannot masquerade as a strong
            result — the emoji-labelled 👍/👎 columns this replaces made the two
            impossible to tell apart at a glance. */}
        <Stack gap="none">
          {agentRows.map(([agent, d]) => {
            const n     = d.up + d.down;
            const share = n > 0 ? d.up / n : 0;
            return (
              <BarRow
                key={agent}
                label={agent.replace(/_/g, " ")}
                labelWidth={140}
                fraction={share}
                tone={share >= 0.7 ? "success" : share >= 0.4 ? "warn" : "error"}
                value={`${Math.round(share * 100)}% · ${n}`}
              />
            );
          })}
        </Stack>
        <Caption>Bar shows share positive; the number is that share and the rating count.</Caption>
      </Stack>
    </Section>
  );
}
