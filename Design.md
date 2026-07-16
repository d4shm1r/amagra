# Amagra — Design Language

> **What this is.** The *why* behind how Amagra looks, and the rules that make it
> reproducible. Its siblings:
>
> | Doc | Answers |
> |---|---|
> | [`docs/design/DESIGN_PRINCIPLES.md`](docs/design/DESIGN_PRINCIPLES.md) | how it must **feel** (the experience filter) |
> | **`Design.md`** (this) | how it must **look**, and why |
> | [`ui/src/README.md`](ui/src/README.md) | how to **build** it (file map, lint, knobs, migration) |
>
> Implementation detail deliberately lives in the README, not here, so this
> document stays true as the codebase moves.

### How to read a rule

Derived by reading `ui/` (v1.7.0). Every normative statement is tagged, because a
design system that can't tell you what's real is just a wish list:

- **[Enforced]** — something fails if you break it: `npm run lint:ui`, a registry
  check, or `npm test`, each run by the **UI** job in CI. Not "we agreed to"; a
  machine says no, on the pull request, before it lands.

  > Worth knowing how thin this was. Until the UI job existed, CI ran `ruff` and
  > `pytest` and nothing else — the whole design system was enforceable in
  > principle and enforced by nobody but whoever remembered to run it. Every
  > "[Enforced]" in this document was, for a while, a claim about a command
  > rather than about the repository.
- **[Observed]** — the code does this consistently today; the kit is built around it.
- **[Proposed]** — *not true yet.* A gap worth closing, recorded honestly rather
  than described as fact.

---

## 1. Philosophy

Amagra is meant to feel like a **finely made instrument**, not like software.

The interface is a workshop for thinking, and a workshop is judged by what it
lets you forget. Calm is preferred over excitement, clarity over decoration,
restraint over abundance. Empty space is a material, not a leftover — it is the
thing that makes the one important element on a screen findable without a label
shouting at you.

Luxury here means **quiet**, never expensive-looking. Gold leaf on every surface
is not luxury; it is anxiety. Gold on *one* surface, where it means something, is.
Every visual decision should do one of two jobs: reduce cognitive effort, or
reinforce trust. A decision that does neither is decoration, and decoration is the
first thing to cut.

The test the app is designed against: **it should be able to sit unchanged for a
decade without looking dated.** That rules out whatever is currently fashionable
in favor of the boring, durable things — paper, ink, a warm light source, type
that respects reading. When you meet a situation this document doesn't cover, ask
which choice a careful instrument-maker would still be happy with in ten years.

**The corollary that does the real work:** because a screen's calm is a budget,
every new element spends it. The question is never "can this be added?" — it's
"what is this replacing?"

---

## 2. The material: "Gilded Calm"

A warm-cream **paper** canvas, a five-step **gold** brand ramp, warm-umber ink.
Three rules define the surface, and everything in §3–§6 is a consequence:

### Warm, never black **[Observed]**
Every shadow is warm umber (`rgba(72,52,28,…)`); no neutral grey or black appears
anywhere in the palette. Black on cream reads as a *hole* in the paper — the eye
knows real shadow is colored by the light around it. The canvas is layered creams
rather than white for the same reason: white is a screen, cream is a material.

### Depth, not outline **[Observed]**
An object is separated from the field by **light**, not by a drawn box. Cards get
a soft warm lift shadow plus an *inset* paper highlight; the edge is a whisper of
gold hairline. A grey 1px border everywhere is the cheapest possible separation and
it makes a page look like a spreadsheet.

> This rule has scar tissue. Cards used to carry an *outer* white glow
> (`-3px -3px 11px white`): it fringed every border with a pale halo and smudged
> through the sticky header's fade as content scrolled under it. The highlight
> moved **inside** the card. Depth reads the same; nothing bleeds past the border.

### Gold is meaning, not decoration **[Observed]**
Gold marks exactly four things: brand, focus, active state, and the single primary
action. It is rationed on purpose — see the gold budget (§4.2). If gold appears
anywhere it doesn't carry one of those meanings, it has stopped being a signal and
become noise, and every *real* signal on the page got quieter.

A faint SVG **paper grain** (2%, multiply) sits over the whole app *and* the
marketing landing page — one material, so the product and its promise are made of
the same stuff.

---

## 3. Hierarchy

### 3.1 Hierarchy is carried by treatment, not size **[Observed]**

This is the least obvious and most important thing about the app's typography.
A section title (`eyebrow`, 10.5px) is **smaller than body text** (14px) — and
still outranks it. It wins on uppercase, 0.14em tracking, weight 800, and gold.

Size is a blunt instrument: a hierarchy built only on size needs each level to be
~1.3× the last, and five levels in you have a 36px "small heading" and a page that
shouts. Treatment (case, tracking, weight, color, family) gives you rank *without*
spending vertical space. That's what lets a dense diagnostic panel stay calm.

The ladder, high to low:

| Rank | Role | Treatment | Rule |
|---|---|---|---|
| 1 | Page hero | `display` 36 serif, gold gradient | **one per tab**, `userSelect: none` — "the hero is identity, not content" |
| 2 | Section title | `eyebrow` 10.5 caps, 0.14em, gold | every titled panel; small but unmistakable |
| 3 | Sub-heading | `subtitle` 18 / `title` 22 | inside a card |
| 4 | Body | `body` 14 / `lead` 15 | the content |
| 5 | Metadata | `caption` 12 / `micro` 10.5, muted | never competes |

### 3.2 One focal point per screen **[Observed]**
A tab opens with exactly one gold serif hero. Below it, one call-out card may hold
the gold edge permanently — *"for the one call-out per page that must read as
primary. Everything else earns it on hover."* Two focal points is zero focal points.

### 3.3 Numbers are a hierarchy of their own **[Observed]**
`metric` (22px, weight 700, `tabular-nums`, −0.02em) is the only way the app shows
a headline number. Prefer `StatStrip` — headline numbers as one hairline-divided
row — over a scatter of floating mini-cards. A row of numbers is a *comparison*;
mini-cards break the comparison into unrelated objects.

---

## 4. Color

### 4.1 The ramps

**Canvas — layered creams (dark → light).** Depth goes *lighter*, because the
light source is above the paper:

| Token | Hex | Role |
|---|---|---|
| `--app-bg` / `T.bg` | `#F0E9DF` | app + landing hero canvas |
| `--l1` / `T.surface2` | `#F4F0E8` | inset wells, chips |
| `--l2` / `T.surface` | `#FAF7F2` | raised panels (cards) |
| `--l3` `--l4` | `#FCFAF7` `#FEFCFA` | lighter steps |
| `--border` / `T.border` | `#E0D6C4` | hairlines on cream |

**Brand — the 5-step gold ramp:** `g1 #FFE880` → `g5 #6C4C00`. `g3 #C48808` is the
**core** (fills, dots, borders, icons); `g4` is hovers/links.

**Ink — warm umber:** `--t1 #2E2010` (AAA) · `--t2 #5C4030` (AAA) ·
`--text-muted #806044` (AA). All three clear WCAG AA on cream — `muted` was
deliberately deepened from a below-floor `#9A7A60` to stay recessive *and* legible.
**Recessive is a tone, not a contrast failure.**

**Status:** `success #15803D` · `warn #A16207` · `error #B42318`, deepened for the
light canvas. **Categorical** (`SEM`): teal/blue/cyan/violet/purple/magenta/clay —
for node/agent/stage *types*. These encode meaning, exactly like status does.

### 4.2 The gold budget **[Observed]**

The rules that already hold, and make the aesthetic reproducible:

- **One gold CTA per surface.** `Button variant="gold"` is *"the single primary CTA
  on a surface."* Everything else is `ghost` (secondary) or `quiet` (tertiary).
- **One permanently-gold card per page** (`Card accent`). Every other card earns
  gold on hover and gives it back.
- **One gold hero per tab** (`PageHeader`).
- **Gold is never body text.** The bright accent is ~2.5:1 as text. This is
  enforced *in the tokens*: `T.accentText` / `--gold-text` `#8A5A00` (~5:1 AA)
  exists specifically for gold-as-label/title/link. **Fills use `accent`; text uses
  `accentText`.** A contrast rule you can't get wrong is better than one you have
  to remember.
- **Gold is never a large background.** The one gold field in the app is the
  primary button, which is button-sized. The canvas is always cream.

**[Proposed]** A quantitative ceiling (e.g. "gold ≤ ~5% of visible pixels; ≤ 2 gold
icons per viewport") would make the budget checkable rather than cultural. Nothing
measures this today.

### 4.3 Tone, not color **[Enforced]**

A view names a **meaning**; the kit resolves it to a hex. `tone.js` is the single
translation table.

```jsx
<Pill tone="error">        ✅  a meaning
<Pill color="#B42318">     ❌  a decision made in the wrong file
```

Health thresholds are defined once, not per-panel: `scoreTone(v)` (≥80 success /
≥60 warn / else error) and `probTone(v)` (≥0.80 / ≥0.65). So "degraded" means the
same thing in every panel in the app.

**The one exception:** raw colors pass through `toneColor()` untouched — deliberately
narrow, for colors that are **data** (an agent's identity color from an API
payload), not styling. Forwarding one is fine; *writing* a literal is not.

---

## 5. Type & optics

Three self-hosted stacks — no CDN, so the desktop app renders fully offline:
**UI** `DM Sans` · **Display** `Cormorant Garamond` (serif; heroes) · **Mono**
`JetBrains Mono` · **Reading prose** `Charter`/`Source Serif` at 15px/1.72.

> Chat messages are set in a **serif** at a generous line-height while the UI is
> sans. The distinction is doing work: sans is *chrome*, serif is *content you
> read*. The app never confuses the two, so a wall of text never looks like a
> settings panel.

Type is **role-based, not size-based.** `TYPE` is eight ready-to-spread objects,
each carrying its own line-height, weight and tracking — so vertical rhythm lives
in the token, not in per-component guesswork:

```
display 36 · title 22 · subtitle 18 · lead 15 · body 14
small 13 · caption 12 · metric 22(tabular) · micro 10.5 · eyebrow 10.5(caps)
```

### Optical rules **[Observed]**

Type and icons are corrected *optically*, not mathematically — the code already
does all of this:

- **The tracking curve runs negative as size runs up.** `display` +0.01em →
  `title` −0.01em → `subtitle` −0.005em → `metric` −0.02em. Large type has too much
  air between letters at its natural spacing; small type has too little.
- **Uppercase gets tracking.** `eyebrow` carries 0.14em. Capitals are designed to
  sit next to lowercase, not next to each other — set them tight and they clot.
  (Note the deliberate exception: as a *stat label*, `eyebrow` drops to 0.08em —
  under a big number it's a caption, not a divider.)
- **Numerals align on a baseline grid.** `metric` and every score readout use
  `fontVariantNumeric: "tabular-nums"`, so a live-updating number doesn't make the
  column dance.
- **Icons are optically sized, not box-sized.** One 24×24 grid, artwork inset to
  ~3px, stroke-only at 1.6, `currentColor`. *"If it needs a different weight to
  read, it is drawn wrong, not weighted wrong."*
- **Hairlines are nudged out of their clip.** `StatStrip` pulls the row 1px left of
  a clipping wrapper so no wrapped row ever starts with a dangling divider.
- **A band of canvas on canvas must be full-bleed.** `PageHeader` spans `100vw`
  rather than sitting in the column, because *"a column-width band of canvas
  painted over a canvas background shows its own left and right edges, which read
  as a faint rectangle floating behind the title."* Its words still align to the
  body column, so the measure is unchanged.
- **Edges dissolve rather than cut.** The header's last 30px fade to transparent
  (matching the launcher's scroll mask), so content scrolling under it melts away
  instead of hitting a line.

---

## 6. Space, measure, composition

- **Space** — a 4px scale (`SPACE[1..10]` = 4…48). Every gap lands on it.
- **Radius** — `sm 6 · md 9 · lg 14 · xl 20`; cards 16; pills/buttons 40 (full round).

### Composition **[Observed]**
The scale matters less than how it's composed. What the kit actually does:

| Relationship | Gap | Where |
|---|---|---|
| Inside a control group | 8 (`Row gap="sm"`) | button clusters, pill runs |
| Between rows in a panel | 12 (`Stack gap="md"`) | the default stack |
| Between sections | 16–24 (`gap="lg"`/`"xl"`) | a tab's top-level stack |
| Card padding | 20/24 (`pad="lg"`) | `Card`; `Section` uses 16×20 |
| Page gutter | 28 × 24 (`LAYOUT.gutter`) | the scroll surface |

Proximity is the hierarchy: **related things share a gap, unrelated things get a
bigger one.** If two groups need a *line* between them to be readable, the gap was
wrong first — reach for space before you reach for a divider.

### Measure **[Enforced]**
Exactly **two** page widths, because there are two kinds of surface — and a third
is just somewhere for drift to hide:

- `content: 1060` — dashboards, tables, cards, graphs.
- `reading: 860` — prose (chat, research). Narrower on purpose.

**A view never centers itself.** The shell owns the column (`<Column>`); the view
fills what it's given. This is not taste — the app lost this fight once. A past
phase stripped `maxWidth + margin: 0 auto` from 16 tab roots to make `App` the sole
layout authority, and four had quietly grown it back by the time the kit landed.
`lint:ui` now fails on `margin: 0 auto` in a view.

> **Open question — the reading measure doesn't yet earn its rationale.**
> The textbook reason to narrow prose is line length: comprehension drops past
> ~66–90 characters. But `reading: 860`, less the thread's 24px padding, times the
> assistant bubble's 87%, lands **~95 characters** at 15px Charter — wider than the
> ideal it's presumably aiming at. So `860` is currently *a number that is smaller
> than 1060*, not a number derived from a principle. Either the measure should
> come down (~720px ≈ 80ch) or the rationale should be stated honestly as
> something else. Recorded rather than back-filled with a justification the code
> doesn't support.

---

## 7. Elevation & layering

### Three depths, and no more **[Observed]**

| Depth | Primitive | What it is |
|---|---|---|
| 0 | canvas | the cream field |
| 1 | `Card` / `Section` | a raised object on the field |
| 2 | `Well` | a recessed surface *inside* a Section |
| — | `Tile` | a readout inside a Well/Grid (no new depth) |

**Never nest a Card in a Card.** Card-in-card produces two gold hover borders and
a shadow inside a shadow — the eye reads it as a rendering bug. The dashboard
enforces this structurally: `.cog-cell-body .lux-card` strips the chrome off any
card that lands inside a cell, because **the cell *is* the card.**

**One card recipe** for the whole app (`--card-*` / `LUX.card*`): a warm centered
lift shadow + inset paper highlight + gold hairline. Hover adds a gold whisper
(28px, 13% alpha). Elevation is *centered*, not offset bottom-right — offset
shadows imply a light source you then have to honor on every other element.

### The layer stack

Observed z-indices: `PageHeader 30` → `Toast 40` → `☰ launcher 50` → (…`100`,
`2000`, `9000`) → launcher-open `9010` → paper grain `9999`.

The intent is sound and documented in-place — the offline alert sits *above* the
sticky header but *below* the launcher, so the menu stays reachable while an alert
is up.

**[Proposed]** These are ad-hoc literals, not tokens. A `Z` scale in `theme.js`
(`base/header/toast/launcher/modal/grain`) would make the ordering legible and stop
the next `9000` from being invented. The values already form a system; nothing
names it.

---

## 8. Motion & interaction

One easing language, four durations: `EASE.out` `cubic-bezier(0.22,1,0.36,1)`
(decelerate — enters, lifts) · `EASE.inOut` (symmetric — loops, toggles) ·
`DUR fast 140 · base 200 · slow 280 · slower 600`.

Tokens say *how fast*. These say **when motion is allowed at all** — the part that
actually determines whether an app feels calm:

### Motion explains state; it never decorates **[Observed]**
Every animation in the app is doing a job: `dotPulse`/`livePulse` means *live*,
the 600ms `ScoreBar` width means *this number changed*, `fadeIn` means *this view
is new*. There is no motion whose reason is "it looks nice."

### Containers stay still; only discrete objects move **[Observed]**
A card lifts (`translateY(-2px)`) **only** if it's `interactive` — a thing you can
click. A static container hovering gets the gold whisper and no geometry change.
Movement is a promise that something will happen if you click; a container that
lifts is lying.

### One axis at a time **[Observed]**
The hover lift is Y-only. Nothing in the kit translates and scales at once — a
2-axis move reads as a pop, and a pop is excitement, which is the one thing the
material is trying not to be.

### The layout must never lurch **[Observed]**
This is the strictest interaction rule in the codebase, and it's structural:
the offline alert renders in a `Toast` — absolutely positioned, `pointerEvents:
none` on the layer so it never steals a click meant for content beneath. *"An
alert is not part of the page. It must not take a row in the layout and shove every
card down by its own height."* When the engine drops and returns, the page does not
move. Async state changes the *content*, never the *furniture*.

### Interaction stays responsive under load **[Observed]**
Tab switches run in `startTransition` over `lazy()` chunks (one per tab; Chat and
Home eager so they paint with no fetch). React keeps the current view interactive
and swaps when the new tree is ready, rather than janking the click on a heavy
graph mount. **The old view staying interactive beats the new view arriving sooner.**

### Menus close on selection **[Observed]**
`navTo` dismisses the launcher immediately and *outside* the transition —
*"urgent: the menu dismisses instantly."* The navigation you asked for may take a
frame; the acknowledgement may not.

### Reduced motion is honored twice **[Observed]**
At the CSS level (`prefers-reduced-motion`) and via an in-app setting that injects
a global collapse. Animations go to ~0ms; **state changes still happen.** Reduced
motion removes the transition, never the information.

### Destructive actions confirm — but through the wrong door **[Observed]**
Deletes do ask first: Library removal, goal deletion, and clearing a chat all
gate on a confirmation. But all three call **`window.confirm()`** — a native OS
dialog. In an app this carefully made, the one moment the user is asked to be sure
is the one moment the material breaks: grey system chrome, a system font, buttons
the design system has never seen, and copy it can't set. `Button variant="danger"`
exists and is styled quiet-until-touched, but the kit has no confirm primitive to
pair it with.

**[Proposed]** A `<Confirm>` in the kit, and a stated contract for what needs one.
Also missing: a latency budget for what must feel instant (<100ms) vs. what earns
a `Loading` state (>300ms).

---

## 9. Editorial voice

The design system owns the words. Type and color are undone by copy that sounds
like three different products.

### One voice, enforced **[Enforced]**
All 35 navigation entries pass a linter that rejects the wrong voice. Each `desc`
must be a lower-case **noun phrase** naming what the thing *is* — "the routing
skill graph", never "browse the routing skill graph" — with no full stop, "and"
not "&", and ≤34 chars so it sits on one line.

> The menu used to speak in three voices at once: Title-Case imperatives on the
> surfaces ("Monitor system health"), lower-case verbs on some tabs ("talk to your
> agents"), nouns on the rest. **No two tiles scanned the same way.** A tile with
> no description is a shorter tile, and one short tile makes a whole grid row look
> broken — so it's all-or-nothing.

### The voice everywhere else **[Observed]**
The kit's own copy is consistent, and it's the reference for new strings:

- **An error names the state, then spells out the exact fix — with the command.**
  *"The engine is offline / Amagra runs entirely on your hardware. Start the local
  engine to bring the workspace online — `./start-agents.sh`."* Never "Something
  went wrong."
- **In-flight uses an ellipsis and the present participle:** "Connecting to the
  engine…", "Checking…", "Loading the Prompt IDE…". Never a bare "Please wait".
- **Empty means "not yet", never "nothing".** *"No data yet — run a query to
  populate this view."* An empty state names the action that fills it.
- **Sentence case everywhere.** Buttons are verbs ("Retry", "View all →"),
  not Title Case.
- **The em-dash is the house punctuation** — it carries the "state — then fix"
  rhythm above.
- Empty *pages* get room: serif headline, one line of prose (≤420px), **one** CTA,
  one hint. A first impression is allowed to breathe; a panel's empty state isn't.

---

## 10. Accessibility

### Holds today **[Observed]**
- **Contrast** — all three ink tiers clear AA on cream; primary/secondary reach
  AAA. The gold-as-text vs gold-as-fill split (§4.2) is a contrast fix baked into
  the token names.
- **Focus** — one on-brand gold `:focus-visible` ring (2px `g3`, 2px offset),
  keyboard-only, `!important` to beat the calm inline `outline: none`. Snug (1px)
  on inputs; suppressed on the chat textarea, where the composer pill already
  carries the focus affordance — *one* ring, never two concentric.
- **Reduced motion** — honored twice (§8).
- **Icons** — `aria-hidden`, decorative; affordances carry `aria-label`/`title`.
  An unknown icon name renders **nothing**, never a mystery box.
- **Keyboard** — a full map (`Ctrl+1..7` surfaces, `Ctrl+B` menu, `⌘K`
  search-focused launcher, `Ctrl+,` settings, `Ctrl+/` shortcuts) that ignores
  keystrokes while focus is in an input.
- **Async state is announced.** `Toast` is a polite live region and is mounted
  **permanently** — only its children come and go, because a region that appears
  at the same instant as its message is not reliably read. `Loading` is a
  `status`; `Notice` is an `alert` when it carries a failure and a `status`
  otherwise, so urgency matches the tone.
- **Hit-target floor: 24×24** (WCAG 2.2 SC 2.5.8), applied in the kit to
  `IconButton` and `RefreshButton`. Deliberately not Apple's 44×44: these sit in
  dense rows beside card titles, where 44px boxes would overlap and silently eat
  each other's clicks. The glyph keeps its size; only the box grows.
- **A dot is never the only channel.** `Dot` takes a `label` and becomes an image
  with an accessible name; without one it is `aria-hidden`, on the understanding
  that adjacent text carries the meaning. Prefer the text — a colour-blind
  *sighted* user can read a label but cannot hear an `aria-label`.

### Gaps **[Proposed]**
Real, and worth naming rather than glossing:

- **Streaming chat isn't announced.** The kit-level regions cover the offline
  banner, panel loading, and notices. A streaming assistant reply is a live
  update in `ChatTab.jsx` — 64KB, in `DEBT`, and needing a chunk-vs-final-answer
  decision (announcing every token would be unusable). The single biggest
  remaining a11y gap, and the one that needs design, not just a role attribute.
- **No documented error-copy contract for assistive tech** — §9's rules are visual
  prose rules; they don't yet say what gets announced.
- **Still no axe/Lighthouse pass, and nobody has driven this with a real screen
  reader.** The rules above are now *tested* (`npm test` — vitest + jsdom, and
  each assertion is mutation-checked: breaking the implementation fails exactly
  the test that names the rule, including re-introducing the conditional `Toast`).
  But a passing suite proves the attribute is present and the focus moves, not
  that the result is *pleasant to listen to*. Those are different questions and
  only the second one matters to the person using it.
- **jsdom does no layout**, so the 24×24 floor can only be asserted as a
  declaration. The test catches someone deleting the floor; it would not catch a
  parent squashing the button.

---

## 11. Anti-patterns

Never do these. Each is a real failure this codebase has met, is guarded against,
or would be broken by:

| ❌ Never | Why |
|---|---|
| **Nest a Card inside a Card** | two gold hover borders, shadow-in-shadow; the cell *is* the card |
| **Add a fourth elevation level** | three depths is the vocabulary; a fourth has no meaning left to carry |
| **Center a view yourself** (`margin: 0 auto`) | the shell owns the column — the app lost this fight once **[Enforced]** |
| **Write a hex, `rgb()`, or `style={{` in a view** | design decisions belong in the kit **[Enforced]** |
| **Import `@/styles/theme` from a tab** | a view names meanings, not tokens **[Enforced]** |
| **Two gold CTAs in one viewport** | two focal points is zero focal points |
| **Gold as body text or a large background** | ~2.5:1 contrast, and it spends the whole budget |
| **A new border radius / font size / duration** | the scale exists; a one-off is drift wearing a disguise |
| **A unicode glyph as an icon** | each comes from whatever font the machine has — they can never look like a set **[Enforced]** |
| **Re-weight an icon so it "reads"** | then it's drawn wrong, not weighted wrong |
| **Hand-roll `Loading…` in an italic div** | `Feedback.jsx` exists precisely so this stops |
| **Invent a button variant at the call site** | add the variant to the kit; the next view gets it free |
| **Animate a static container** | movement promises clickability |
| **Animate two axes at once** | reads as a pop; pops aren't calm |
| **Let an alert take a row in the layout** | the page lurches; use `Toast` |
| **Mount a live region with its message** | a region that appears with its content is not announced — the `Toast` layer is permanent on purpose **[Enforced]** |
| **Ship a modal without containing Tab** | `aria-modal` tells a screen reader the page behind is inert; the browser still tabs into it **[Enforced]** |
| **`window.confirm()`** | it drops out of the material at the exact moment trust matters — use `useConfirm()` |
| **A menu tile with no description** | one short tile makes the whole row look broken **[Enforced]** |
| **An imperative in a nav description** | name what the thing *is* **[Enforced]** |
| **"Something went wrong."** | name the state, spell out the fix, give the command |
| **Use `SEM` categoricals as decoration** | they encode meaning, exactly like status colors |
| **A third page measure** | somewhere for drift to hide |

---

## 12. Where this is going

Honest backlog, in rough priority — the difference between this system and a
world-class one, stated as work rather than aspiration:

1. **Announce streaming chat** (§10) — the last real a11y gap. The kit-level
   regions, the 24×24 hit-target floor and the `Dot` doctrine are **done**; this
   one needs a design decision (announce chunks or the settled answer?) inside a
   64KB `DEBT` file, which is why it didn't ride along with them.
2. **Resolve the reading measure** (§6) — bring `860` down to ~80ch or state its
   real rationale. A token whose *why* is missing is a token that drifts.
3. **Tokenize the z-scale** (§7) — the system exists; nothing names it.
4. **Make the gold budget checkable** (§4.2) — a cultural rule is one distracted
   afternoon from being untrue.
5. **State the interaction contracts** (§8) — destructive-action confirmation,
   latency budget.
6. **Document the radius rationale** — `6/9/14/20` and card-16 are observed, and
   no file says why 14 rather than 12. Either derive them (a card's radius should
   grow with its padding so the inner corner stays optically parallel) or admit
   they're inherited and pick one.
7. **Replace `window.confirm()`** (§8) — three native OS dialogs currently break
   the material at the exact moment the user is asked to be careful.
8. **Retire the debt** — the kit landed after most tabs existed, so most of the app
   still styles itself. That ratio is the honest headline of this whole document:
   the *system* is strong; the *codebase* is a minority of files into adopting it.
   **Run `npm run lint:ui` for the live count** — deliberately not pasted here,
   because a number that changes every time someone converts a tab is a number a
   document gets wrong. See the migration recipe in
   [`ui/src/README.md`](ui/src/README.md). The `DEBT` list only shrinks.
