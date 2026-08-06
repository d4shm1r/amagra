// ToolsTab — the front door to the agent tool loop (tools/tool_loop.py).
//
// POST /tools/run and GET /tools/list have existed since the tool loop was
// built, but nothing in the UI ever called them — the only trace of the
// capability was two lines in the changelog. This tab is that front door: it
// lists what's actually available right now (the backend only lists tools
// whose own config gate is satisfied — e.g. web_search only appears once a
// search provider is configured), takes a prompt, and shows the finished
// action → observe → repeat trace. Each call the loop makes also emits
// `tool.call` on the runtime event bus AS it happens, so the terminal dock at
// the bottom of the app is where you watch it work live; this tab shows the
// prompt, the controls, and the trace once it's done.
import { useEffect, useState } from "react";
import { API } from "@/lib/api";
import {
  Page, PageHeader, Column, Stack, Row, Section, Button, Pill,
  Micro, Caption, Body, EmptyState, Notice, Loading, Divider,
} from "@/components/ui";
import { TextArea, Field, Slider } from "@/components/forms";

export default function ToolsTab() {
  const [tools,    setTools]    = useState(null);
  const [toolsErr, setToolsErr] = useState(null);

  const [prompt,   setPrompt]   = useState("");
  const [maxIters, setMaxIters] = useState(3);
  const [running,  setRunning]  = useState(false);
  const [result,   setResult]   = useState(null);
  const [runErr,   setRunErr]   = useState(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/tools/list`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { if (alive) setTools(d.tools || []); })
      .catch(e => { if (alive) setToolsErr(e.message); });
    return () => { alive = false; };
  }, []);

  async function run() {
    if (!prompt.trim() || running) return;
    setRunning(true); setRunErr(null); setResult(null);
    try {
      const r = await fetch(`${API}/tools/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, max_iters: maxIters }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${r.status}`);
      }
      setResult(await r.json());
    } catch (e) {
      setRunErr(e.message || "The run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <Page>
      <PageHeader
        title="Tools"
        subtitle="Give the model a prompt and let it work through read_file, search_files, and whatever else is configured below — one action, one observation, up to the round limit. Every call streams live into the terminal dock at the bottom of the app as it happens."
      />
      <Column>
        <Stack gap="lg">
          <Section
            title="Available right now"
            hint={tools ? `${tools.length} tool${tools.length === 1 ? "" : "s"} usable` : undefined}
          >
            {toolsErr ? (
              <Notice tone="error">Couldn't reach the engine — {toolsErr}</Notice>
            ) : tools == null ? (
              <Loading />
            ) : tools.length === 0 ? (
              <EmptyState msg="No tools usable right now — check that the local engine is running." />
            ) : (
              <Stack gap="sm">
                {tools.map(t => (
                  <Row key={t.name} gap="md" align="flex-start" wrap>
                    <Pill tone="accent">{t.name}</Pill>
                    <Caption>{t.description}</Caption>
                  </Row>
                ))}
              </Stack>
            )}
          </Section>

          <Section title="Run">
            <Stack gap="md">
              <TextArea
                value={prompt}
                onChange={setPrompt}
                rows={4}
                placeholder='What should it figure out? e.g. "What does routes/tools.py do, and which file defines the tool catalog?"'
              />
              <Field label="Max tool rounds" hint="How many calls before it must give a final answer">
                <Row gap="sm">
                  <Slider value={maxIters} onChange={setMaxIters} min={1} max={5} width={140} label="Max tool rounds" />
                  <Micro mono>{maxIters}</Micro>
                </Row>
              </Field>
              <Row gap="md">
                <Button variant="gold" onClick={run} disabled={running || !prompt.trim()}>
                  {running ? "Working…" : "Run"}
                </Button>
                {running && <Caption>Watch the terminal dock below for each call as it happens.</Caption>}
              </Row>
            </Stack>
          </Section>

          {runErr && <Notice tone="error">{runErr}</Notice>}

          {result && (
            <Section
              title="Result"
              hint={`${result.iterations} round${result.iterations === 1 ? "" : "s"} · stopped: ${result.stopped}`}
            >
              <Stack gap="md">
                <Body>{result.answer || "(no answer text)"}</Body>
                {result.calls?.length > 0 && (
                  <>
                    <Divider />
                    <Stack gap="sm">
                      {result.calls.map((c, i) => (
                        <Row key={i} gap="sm" align="flex-start" wrap>
                          <Pill tone={c.ok ? "success" : "error"} strong>{c.ok ? "✓" : "✗"}</Pill>
                          <Caption mono>{c.tool}</Caption>
                          <Micro tone="muted" mono>{JSON.stringify(c.args)}</Micro>
                        </Row>
                      ))}
                    </Stack>
                  </>
                )}
              </Stack>
            </Section>
          )}
        </Stack>
      </Column>
    </Page>
  );
}
