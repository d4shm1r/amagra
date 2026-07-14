# ui/src — how this code is organised

One rule, and everything else follows from it:

> **Colors, shapes and style objects may only be written in `styles/` and
> `components/ui|forms/`. Everything else composes them.**

A tab says *what* it shows. The kit decides *how it looks*. That is why a tab
file has no hex codes, no `style={{…}}`, no `<style>` blocks, and does not even
import the design tokens — it only imports components.

`npm run lint:ui` enforces this. `npm run lint:ui:debt` lists what's left.

## The layout

```
src/
  main.jsx              entry — mounts <App> inside the error boundary
  App.jsx               shell: routing, keyboard map, app-wide state

  tabs/                 every ROUTED view, one file each, + index.js registry
  components/
    ui/                 THE design system — the only import surface for views
    forms/              every input (text, search, select, toggle, slider)
    layout/             app chrome (AppLauncher, Onboarding)
    panels/             sub-views composed INSIDE tabs (not routed)
    library/            feature components for one tab (pattern for the rest)
  config/               navConfig.js (nav graph), constants.js (agents, builds)
  lib/                  api.js, promptStore.js, monacoSetup.js — no rendering
  styles/               theme.js (JS tokens) + index.css (global CSS)
```

**Tab vs panel.** If `App.jsx` routes to it, it is a tab: `tabs/XxxTab.jsx`,
default-exported, registered in `tabs/index.js`. If it renders *inside* another
view, it is a panel: `components/panels/`. There is no third category.

## Which knob do I turn?

A change to how the app *looks* should be one edit, in one file, and land on
every tab at once. If it isn't, that's a bug in the architecture, not a task for
your afternoon. The knobs:

| To change | Edit | File |
|---|---|---|
| **Width of a tab's body** | `LAYOUT.content` | `styles/theme.js` |
| Width of prose (chat thread, articles) | `LAYOUT.reading` | `styles/theme.js` |
| Page margins | `LAYOUT.gutter` / `gutterY` | `styles/theme.js` |
| Any color | `T`, `SEM`, `GOLD` | `styles/theme.js` (+ `public/tokens.css`) |
| What a tone *means* | `TONES` | `components/ui/tone.js` |
| Font sizes / vertical rhythm | `TYPE` | `styles/theme.js` |
| Spacing scale, corner radii | `SPACE`, `RADIUS` | `styles/theme.js` |
| Animation speed / easing | `DUR`, `EASE` | `styles/theme.js` |
| How a card / button / pill looks | that component | `components/ui/` |

`LAYOUT.content` takes anything `max-width` takes, so `1020`, `"85%"` and
`"72rem"` all work.

**A view never centers itself.** The shell wraps every tab in `<Column>`, which
is the only thing that reads `LAYOUT.content`. This is not a style preference —
the app lost this fight once already (a past phase stripped `maxWidth + margin:
0 auto` from 16 tab roots to make App the sole layout authority, and by the time
the kit landed, four files had grown it back and were silently overriding the
page width). `lint:ui` now fails on `margin: 0 auto` in a view.

## Imports

Every cross-directory import uses the `@/` root (aliased to `src/` in
`vite.config.js`), so a file can move without a wave of `../../` churn and an
import line says which layer it reaches into:

```js
import { Page, Section, Stack, Button } from "@/components/ui";
import { SearchInput }                  from "@/components/forms";
import { API }                          from "@/lib/api";
import { AGENTS }                       from "@/config/constants";
```

## Writing a tab

```jsx
import { Page, PageHeader, Section, Stack, Button, Pill } from "@/components/ui";

export default function ThingTab() {
  const { things, refresh } = useThings();          // logic is fine
  return (
    <Page>
      <PageHeader center title="Things" subtitle="…">
        <Button variant="ghost" onClick={refresh}>Refresh</Button>
      </PageHeader>
      <Stack gap="lg">
        <Section title="Recent">
          {things.map(t => <Pill key={t.id} tone={t.ok ? "success" : "error"}>{t.name}</Pill>)}
        </Section>
      </Stack>
    </Page>
  );
}
```

Note `tone={…}`. A view names a **meaning** — `"success"`, `"error"`, `"accent"`
— and `components/ui/tone.js` resolves it to a color. Repaint the palette in one
file and the whole app follows.

## When the kit doesn't have what you need

**Add it to the kit.** Not to your tab. The next view then gets it for free, and
the app keeps one vocabulary instead of thirty dialects. That is the entire
point of the rule, and the lint script exists to stop the shortcut.

The one exception is a color that is genuinely **data**: an agent's identity
color from the `AGENTS` table, a node type from an API payload. Forwarding one of
those into `tone={…}` is fine — `toneColor()` passes raw colors through. Writing
the literal yourself is not.

## Converting a legacy view

Most tabs predate the kit and still style themselves. To convert one:

1. `npm run lint:ui:debt` — see what it's guilty of.
2. Replace its styling with kit primitives; add any missing primitive to
   `components/ui` (a real gap, not a one-off).
3. Move any colors in its data to tone names.
4. Delete it from the `DEBT` list in `scripts/lint-ui.mjs`.

`tabs/GuideTab.jsx`, `tabs/LibraryTab.jsx` and `tabs/LogTab.jsx` are the worked
examples. The `DEBT` list only ever shrinks.
