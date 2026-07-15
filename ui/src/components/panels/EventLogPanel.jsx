import { useState, useEffect, useRef } from "react";
import {
  ObsPanel, EventRow, RefreshButton, EmptyState, eventMeta, PageHeader, Pill,
  Row, Stack, Spacer, Pad, Scroll, Notice, Small, Inline, SegmentedControl, Button,
} from "@/components/ui";
import { SearchInput, Toggle } from "@/components/forms";

import { API } from "@/lib/api";

const EVENT_CATEGORIES = [
  { id: "all",     label: "All" },
  { id: "plan",    label: "Plan",    match: t => t.startsWith("plan.") || t.startsWith("step.") },
  { id: "risk",    label: "Risk",    match: t => t.startsWith("risk.") || t.startsWith("reflection.") },
  { id: "query",   label: "Query",   match: t => t.startsWith("query.") || t.startsWith("agent.") || t.startsWith("response.") },
  { id: "memory",  label: "Memory",  match: t => t.startsWith("memory.") || t.startsWith("contradiction.") },
  { id: "learn",   label: "Learn",   match: t => t.startsWith("routing.") || t.startsWith("session.") },
];

// ── Count pills ───────────────────────────────────────────────
function CountPills({ counts }) {
  if (!counts || !Object.keys(counts).length) return null;
  const total = Object.values(counts).reduce((s, n) => s + n, 0);
  return (
    <Row wrap gap="xs">
      <Pill tone="gold" strong>{total} total</Pill>
      {Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([type, n]) => {
          const meta = eventMeta(type);
          return (
            <Pill key={type} tone="muted">
              <Inline tone={meta.tone}>{meta.icon}</Inline>{" "}
              {type.replace(/\./g, " ")}{" "}
              <Inline tone="subtle">{n}</Inline>
            </Pill>
          );
        })}
    </Row>
  );
}

// ── Main component ────────────────────────────────────────────
export default function EventLogPanel({ embedded = false } = {}) {
  const [data,       setData]       = useState({ events: [], counts: {} });
  const [filter,     setFilter]     = useState("all");
  const [search,     setSearch]     = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const listRef = useRef(null);

  const load = () => {
    setLoading(true);
    fetch(`${API}/cos/events?n=200`)
      .then(r => r.json())
      .then(d => { setData(d || { events: [], counts: {} }); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); const id = setInterval(load, 10_000); return () => clearInterval(id); }, []);

  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [data, autoScroll]);

  const events = data.events || [];
  const counts = data.counts || {};

  const cat = EVENT_CATEGORIES.find(c => c.id === filter);
  const filtered = events.filter(e => {
    const type = e.event_type || "";
    if (filter !== "all" && cat?.match && !cat.match(type)) return false;
    if (search) {
      const q = search.toLowerCase();
      const payload = JSON.stringify(e.payload || "").toLowerCase();
      if (!type.toLowerCase().includes(q) && !payload.includes(q)) return false;
    }
    return true;
  });

  const content = (
    <Stack gap="md">
      {error && <Notice tone="error">Backend unavailable: {error}</Notice>}

      <CountPills counts={counts} />

      {/* Filter bar */}
      <Row gap="sm" wrap>
        <SegmentedControl
          options={EVENT_CATEGORIES.map(c => ({ val: c.id, label: c.label }))}
          value={filter}
          onChange={setFilter}
        />
        <SearchInput value={search} onChange={setSearch} placeholder="Search events…" width={170} />
        {(search || filter !== "all") && (
          <Button variant="quiet" size="sm" onClick={() => { setSearch(""); setFilter("all"); }}>
            ✕ Clear
          </Button>
        )}
        <Spacer />
        <Small tone="muted">{filtered.length} / {events.length}</Small>
      </Row>

      {/* Event list */}
      <ObsPanel>
        {loading && !events.length ? (
          <EmptyState msg="Loading events…" />
        ) : filtered.length ? (
          <Scroll ref={listRef} max="calc(100vh - 320px)">
            {filtered.map((e, i) => <EventRow key={i} event={e} />)}
          </Scroll>
        ) : (
          <EmptyState msg={
            events.length === 0
              ? "No events yet — run a query to populate the event log."
              : "No events match this filter."
          } />
        )}
      </ObsPanel>
    </Stack>
  );

  // Embedded in a dashboard cell (which carries the title and owns no padding).
  if (embedded) return <Pad>{content}</Pad>;

  return (
    <>
      <PageHeader
        sticky={false}
        title="Events"
        subtitle="Typed event stream from the cognitive runtime · auto-refresh 10s"
      >
        <Row gap="xs">
          <Toggle checked={autoScroll} onChange={setAutoScroll} label="Auto-scroll" />
          <Small tone="muted">Auto-scroll</Small>
        </Row>
        <RefreshButton onClick={load} />
      </PageHeader>
      {content}
    </>
  );
}
