// DocCard.jsx — one document as an object in a collection.
// Feature component: it composes the kit, it does not draw. No colors, no
// shapes, no style objects live here.
import {
  Card, Stack, Row, Spacer, FileEmblem, Menu, MenuItem, MenuLabel, MenuDivider,
  Body, Caption, Inline,
} from "@/components/ui";
import { typeOf, prettyTitle, docSubtitle } from "./docMeta";

function DocStatus({ status }) {
  if (status === "reading") return <Inline role="caption" tone="gold" weight={600} pulse>Reading…</Inline>;
  if (status === "error")   return <Inline role="caption" tone="error" weight={600}>Couldn't read</Inline>;
  return <Inline role="caption" tone="success" weight={600}>✓ Read</Inline>;
}

export function DocCard({ doc, collections, onMove, onRemove }) {
  const type = typeOf(doc.filename);

  return (
    <Card interactive pad="md">
      <Stack gap="md">
        <FileEmblem ext={type.ext} tone={type.tone} />

        <Stack gap="xs">
          <Body weight={600} clamp={2} title={doc.filename}>{prettyTitle(doc.filename)}</Body>
          <Caption>{docSubtitle(doc)}</Caption>
        </Stack>

        <Row gap="xs">
          <DocStatus status={doc.status} />
          <Spacer />
          <Menu title="Document actions">
            <MenuLabel>Move to</MenuLabel>
            {collections.filter(c => c !== doc.collection).map(c => (
              <MenuItem key={c} tone="subtle" onClick={() => onMove(doc, c)}>{c}</MenuItem>
            ))}
            <MenuItem italic onClick={() => {
              const name = window.prompt("New collection name:");
              if (name?.trim()) onMove(doc, name.trim());
            }}>
              New collection…
            </MenuItem>
            <MenuDivider />
            <MenuItem tone="error" onClick={() => onRemove(doc)}>Remove from Library</MenuItem>
          </Menu>
        </Row>
      </Stack>
    </Card>
  );
}
