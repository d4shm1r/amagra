// components/ui — THE design system. One import surface for the whole app.
//
//   import { Page, Section, Stack, Button, Pill } from "@/components/ui";
//
// The contract, and the reason this file exists:
//
//   Colors, sizes, shadows, radii and shapes may be written HERE and in
//   styles/ — nowhere else. Tabs, panels and feature components compose these
//   primitives and pass TONES ("error", "success", "accent"), never hex.
//
// If a view needs something this kit doesn't have, the fix is to add it here,
// not to hand-roll it at the call site. `npm run lint:ui` enforces this.

export { Page, Column, Stack, Row, Grid, GridSpan, Pad, Scroll, Spacer, Divider } from "./Layout";
export { Display, Title, Subtitle, Lead, Body, Small, Caption, Micro, Eyebrow, Inline, Code, CodeBlock } from "./Text";
export { Button, IconButton, RefreshButton } from "./Button";
export { Card, CardHeader, Section, ObsPanel, Well, Tile, ListTile } from "./Card";
export { Disclosure, DisclosureBody, BulletList } from "./Disclosure";
export { CommandList } from "./CommandList";
export { Menu, MenuItem, MenuLabel, MenuDivider } from "./Menu";
export { Icon, ICON_NAMES } from "./Icon";
export { Pill, Tag, Dot } from "./Pill";
export { Wordmark } from "./Wordmark";
export { SegmentedControl } from "./SegmentedControl";
export { KeyChord } from "./KeyChord";
export { DataRow } from "./DataRow";
export { Table } from "./Table";
export { PageHeader } from "./PageHeader";
export { StatStrip, MetricCard, ScoreBar } from "./Stat";
export { Loading, EmptyState, EmptyPage, Notice, Toast, ApiOfflineBanner } from "./Feedback";
export { EventRow, eventMeta } from "./EventRow";
export { FileEmblem } from "./FileEmblem";
export { DropZone } from "./DropZone";
export { Markdown } from "./Markdown";
export { TONES, toneColor, scoreTone, probTone, hScore, hProb } from "./tone";
