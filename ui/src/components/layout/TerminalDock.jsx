// ── TerminalDock ──────────────────────────────────────────────────────────────
// A permanent, always-connected tail of the runtime event bus — the terminal-
// style window the app was missing. Unlike the Session Log tab (a passive,
// per-browser-session array that dies on refresh), this holds one long-lived
// SSE connection to GET /cos/events/stream open for as long as the app is
// running, independent of which tab is active or whether the dock is expanded.
// That's the point: it behaves like a background health-checker, not a report
// that finishes when a task does — it reconnects on its own after the backend
// closes the stream (see routes/cos.py `max_seconds`) and keeps counting
// unseen activity while collapsed.
//
// EventSource can't carry this app's fetch conventions (and can't POST), so
// this follows the same fetch + ReadableStream pattern already used for
// /ask/stream in ChatTab.jsx, not the EventSource API.
import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/lib/api";
import {
  Stack, Scroll, Pad, Bar, Spacer, Icon, Dot, Pill, Micro, EventRow, EmptyState,
} from "@/components/ui";

const STORE_KEY  = "terminal_dock_open_v1";
const MAX_LINES  = 500;
const RECONNECT_MS = 2000;

function loadOpen() {
  try { return localStorage.getItem(STORE_KEY) === "1"; }
  catch { return false; }
}

let _lineId = 0;

// Shapes a raw bus frame into what EventRow renders, pre-summarizing the two
// synthetic frame types (health.tick's nested /health body, stream.closed)
// into a flat payload so EventRow's generic "k: v · k: v" formatter has
// something short to say instead of dumping the whole health document.
function lineFrom(ev, { replay = false } = {}) {
  if (ev.type === "health.tick") {
    const h = ev.payload || {};
    return {
      id: ++_lineId, replay, count: 1,
      type: "health.tick", timestamp: ev.ts,
      payload: {
        ollama: h.ollama ?? "unknown",
        memory: h.memory?.backend ? `${h.memory.backend}(${h.memory.total ?? "?"})` : "unknown",
        uci: typeof h.uci === "number" ? h.uci.toFixed(1) : (h.uci ?? "—"),
      },
    };
  }
  if (ev.type === "stream.closed") {
    return {
      id: ++_lineId, replay, count: 1,
      type: "stream.closed", timestamp: ev.ts,
      payload: { note: "closed by server — reconnecting" },
    };
  }
  return {
    id: ++_lineId, replay, count: 1,
    type: ev.type || "event", timestamp: ev.ts, payload: ev.payload || {},
  };
}

export default function TerminalDock() {
  const [open,      setOpen]      = useState(loadOpen);
  const [connected, setConnected] = useState(false);
  const [lines,     setLines]     = useState([]);
  const [unseen,    setUnseen]    = useState(0);

  const openRef        = useRef(open);
  const bodyRef         = useRef(null);
  const stickToBottom   = useRef(true);
  const aliveRef        = useRef(true);
  const abortRef        = useRef(null);
  const reconnectTimer  = useRef(null);

  useEffect(() => { openRef.current = open; }, [open]);

  const pushLines = useCallback((incoming) => {
    if (!incoming.length) return;
    let addedCount = 0;
    setLines(prev => {
      const next = [...prev];
      for (const line of incoming) {
        // Several panels read /cos/uci on their own poll cadence and each read
        // re-emits uci.computed even when nothing changed underneath, so an
        // idle app still floods this feed with identical repeats. Collapse a
        // run of the same live (type, payload) into one row with a ×N count
        // instead of pretending each poll was a new fact. Backlog rows are
        // real, distinctly-timed history — never merged.
        const last = next[next.length - 1];
        const samePayload = last && JSON.stringify(last.payload) === JSON.stringify(line.payload);
        if (last && !last.replay && !line.replay && last.type === line.type && samePayload) {
          next[next.length - 1] = { ...last, timestamp: line.timestamp, count: last.count + 1 };
        } else {
          next.push(line);
          addedCount++;
        }
      }
      return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
    });
    if (!openRef.current && addedCount) setUnseen(u => u + addedCount);
  }, []);

  useEffect(() => {
    aliveRef.current = true;

    async function connect() {
      if (!aliveRef.current) return;
      abortRef.current = new AbortController();
      try {
        const r = await fetch(`${API}/cos/events/stream`, { signal: abortRef.current.signal });
        if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);
        setConnected(true);

        const reader  = r.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop();

          for (const part of parts) {
            const line = part.split("\n").find(l => l.startsWith("data: "));
            if (!line) continue;
            let ev;
            try { ev = JSON.parse(line.slice(6)); } catch { continue; }

            if (ev.type === "stream.connected") continue;
            if (ev.type === "stream.backlog") {
              pushLines((ev.events || []).map(e => lineFrom(e, { replay: true })));
              continue;
            }
            pushLines([lineFrom(ev)]);
          }
        }
      } catch {
        // network drop, server restart, or intentional abort on unmount
      } finally {
        setConnected(false);
        if (aliveRef.current) {
          reconnectTimer.current = setTimeout(connect, RECONNECT_MS);
        }
      }
    }

    connect();
    return () => {
      aliveRef.current = false;
      abortRef.current?.abort();
      clearTimeout(reconnectTimer.current);
    };
  }, [pushLines]);

  // Auto-scroll only when the reader was already at the bottom — matches the
  // "don't yank the view while I'm reading scrollback" convention.
  useEffect(() => {
    if (open && stickToBottom.current && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines, open]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) setUnseen(0);
    try { localStorage.setItem(STORE_KEY, next ? "1" : "0"); } catch { /* private mode */ }
  }

  function handleScroll() {
    const el = bodyRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  }

  const lastLine = lines[lines.length - 1];

  return (
    <Stack gap="none">
      {open && (
        <Scroll ref={bodyRef} max="240px" onScroll={handleScroll}>
          <Pad size="lg">
            {lines.length === 0 ? (
              <EmptyState msg="Listening on the event bus — nothing yet." />
            ) : (
              <Stack gap="none">
                {lines.map(l => (
                  <EventRow key={l.id} event={l} replay={l.replay} count={l.count} compact />
                ))}
              </Stack>
            )}
          </Pad>
        </Scroll>
      )}

      <Bar surface onClick={toggle} title={open ? "Collapse terminal" : "Expand terminal — live runtime event feed"}>
        <Icon name="log" size={14} />
        <Dot tone={connected ? "success" : "warn"} live={connected} label={connected ? "Live" : "Reconnecting"} />
        <Micro weight={600} tone={connected ? "default" : "warn"}>{connected ? "Live" : "Reconnecting…"}</Micro>
        {!open && lastLine && (
          <Micro tone="muted" clamp={1}>
            {lastLine.type} — {Object.entries(lastLine.payload || {}).slice(0, 3)
              .map(([k, v]) => `${k}: ${v}`).join(" · ")}{lastLine.count > 1 ? ` ×${lastLine.count}` : ""}
          </Micro>
        )}
        <Spacer />
        {!open && unseen > 0 && <Pill tone="accent" strong>{unseen}</Pill>}
        <Micro tone="muted">{open ? "▾" : "▴"}</Micro>
      </Bar>
    </Stack>
  );
}
