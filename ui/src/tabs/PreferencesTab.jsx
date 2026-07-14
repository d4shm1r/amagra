import { useState, useRef } from "react";
import { AGENTS } from "@/config/constants";
import { Page, PageHeader, Section, Stack, Row, Spacer, Inline, Caption, Code, Button, SegmentedControl } from "@/components/ui";
import { Field, Select, Toggle, Slider } from "@/components/forms";

const DEFAULTS = {
  defaultAgent: "auto", reflectMode: "", temperature: 0.7, maxMemories: 5,
  enterToSend: true, showTimestamps: true, reduceMotion: false,
};

const REFLECT_MODES = [
  { val: "",      label: "Auto"  },
  { val: "none",  label: "Fast"  },
  { val: "light", label: "Check" },
  { val: "full",  label: "Deep"  },
];

const AGENT_OPTIONS = [
  { value: "auto", label: "Auto (Coordinator routes)" },
  ...AGENTS.filter(a => a.id !== "coordinator").map(a => ({ value: a.id, label: a.label })),
];

export default function PreferencesTab({ settings, onUpdate }) {
  const [saved, setSaved] = useState(false);
  const timer = useRef(null);

  const flash = () => {
    setSaved(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setSaved(false), 1600);
  };
  const set = (key, val) => { onUpdate(key, val); flash(); };
  const resetDefaults = () => {
    Object.entries(DEFAULTS).forEach(([k, v]) => onUpdate(k, v));
    flash();
  };

  return (
    <Page>
      <PageHeader
        center
        title="Settings"
        subtitle="Tune how Amagra reasons, remembers, and behaves. Every change saves instantly to this device."
      >
        {saved && <Inline role="micro" tone="success" weight={700}>✓ Saved</Inline>}
      </PageHeader>

      <Stack gap="lg">
        <Section title="Agent & Inference">
          <Field label="Default agent" hint="Pre-selects the agent for every new conversation">
            <Select
              value={settings.defaultAgent}
              onChange={v => set("defaultAgent", v)}
              options={AGENT_OPTIONS}
            />
          </Field>

          <Field label="Default reflect mode" hint="Depth of self-critique applied after each response">
            <SegmentedControl
              value={settings.reflectMode}
              onChange={v => set("reflectMode", v)}
              options={REFLECT_MODES}
            />
          </Field>

          <Field
            label={`Temperature — ${settings.temperature.toFixed(1)}`}
            hint="Higher = more creative · lower = more deterministic"
          >
            <Slider
              label="Temperature"
              min={0.1} max={1.0} step={0.1}
              value={settings.temperature}
              onChange={v => set("temperature", v)}
            />
          </Field>
        </Section>

        <Section title="Memory">
          <Field
            label={`Max memories per query — ${settings.maxMemories}`}
            hint="How many relevant memories are retrieved and injected into each request"
          >
            <Slider
              label="Max memories per query"
              min={1} max={15} step={1}
              value={settings.maxMemories}
              onChange={v => set("maxMemories", v)}
            />
          </Field>
        </Section>

        <Section title="Interface">
          <Field label="Send on Enter" hint="On: Enter sends, Shift+Enter for a new line. Off: Ctrl+Enter sends.">
            <Toggle label="Send on Enter" checked={settings.enterToSend} onChange={v => set("enterToSend", v)} />
          </Field>
          <Field label="Message timestamps" hint="Show the time beside each chat message">
            <Toggle label="Message timestamps" checked={settings.showTimestamps} onChange={v => set("showTimestamps", v)} />
          </Field>
          <Field label="Reduce motion" hint="Collapse animations and transitions across the app">
            <Toggle label="Reduce motion" checked={settings.reduceMotion} onChange={v => set("reduceMotion", v)} />
          </Field>
        </Section>

        <Row gap="md">
          <Caption>
            Settings persist in <Code tone="gold">localStorage</Code>. Reflect mode and default
            agent apply on your next message.
          </Caption>
          <Spacer />
          <Button variant="ghost" onClick={resetDefaults}>Reset to defaults</Button>
        </Row>
      </Stack>
    </Page>
  );
}
