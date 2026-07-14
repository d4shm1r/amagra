import { Page, PageHeader, Section, Stack, Grid, Row, Spacer, Small, Micro, KeyChord } from "@/components/ui";

// Every binding below is wired (App.jsx global handler + ChatTab panel handler)
// — nothing aspirational.
const GROUPS = [
  { title: "Primary Navigation", rows: [
    ["Introduction",       "Ctrl+1"],
    ["Workspace",          "Ctrl+2"],
    ["Runs",               "Ctrl+3"],
    ["Cognition",          "Ctrl+4"],
    ["Memory",             "Ctrl+5"],
    ["Research",           "Ctrl+6"],
    ["Setup",              "Ctrl+7"],
    ["Command menu",       "Ctrl+K"],
  ]},
  { title: "Debug & Decisions", rows: [
    ["Decisions",          "Ctrl+Shift+D"],
    ["Learning Timeline",  "Ctrl+Shift+L"],
    ["Policy Gate",        "Ctrl+Shift+Y"],
    ["Decisions / Replay", "Ctrl+Shift+R"],
  ]},
  { title: "Observe & Explore", rows: [
    ["Cognitive OS",       "Ctrl+Shift+X"],
    ["Memory Browser",     "Ctrl+Shift+M"],
    ["Knowledge Graph",    "Ctrl+Shift+K"],
    ["Data Analysis",      "Ctrl+Shift+A"],
    ["Consensus",          "Ctrl+Shift+V"],
  ]},
  { title: "Tools & Surfaces", rows: [
    ["Prompt Editor",      "Ctrl+Shift+E"],
    ["Task Queue",         "Ctrl+Shift+Q"],
    ["Goals",              "Ctrl+Shift+G"],
    ["Releases",           "Ctrl+Shift+H"],
    ["Skills",             "Ctrl+Shift+S"],
    ["Providers",          "Ctrl+Shift+P"],
  ]},
  { title: "Interface", rows: [
    ["Toggle menu",        "Ctrl+B"],
    ["Open Settings",      "Ctrl+,"],
    ["Keyboard Shortcuts", "Ctrl+/"],
    ["Close / dismiss",    "Escape"],
  ]},
  { title: "Chat", rows: [
    ["New chat",           "Ctrl+Shift+N"],
    ["Send message",       "Enter"],
    ["New line",           "Shift+Enter"],
    ["Threads panel",      "Ctrl+Shift+T"],
    ["Context panel",      "Ctrl+Shift+C"],
    ["Advanced panel",     "Ctrl+Shift+O"],
  ]},
];

const TOTAL = GROUPS.reduce((n, g) => n + g.rows.length, 0);

export default function ShortcutsTab() {
  return (
    <Page>
      <PageHeader
        center
        title="Shortcuts"
        subtitle={`Every keyboard binding in Amagra — ${TOTAL} shortcuts across ${GROUPS.length} groups. Chords work anywhere outside a text field; ⌘ substitutes for Ctrl on macOS.`}
      />

      <Stack gap="lg">
        {GROUPS.map(group => (
          <Section
            key={group.title}
            title={group.title}
            action={<Micro mono>{group.rows.length}</Micro>}
          >
            <Grid cols={2} divided>
              {group.rows.map(([action, combo]) => (
                <Row key={action} gap="md">
                  <Small tone="muted" clamp={1}>{action}</Small>
                  <Spacer />
                  <KeyChord combo={combo} />
                </Row>
              ))}
            </Grid>
          </Section>
        ))}
      </Stack>
    </Page>
  );
}
