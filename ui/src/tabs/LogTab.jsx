import {
  Page, PageHeader, Card, Stack, Row, Button, Caption, Small, Micro, EmptyState,
} from "@/components/ui";

export default function LogTab({ sessionLog, onClear }) {
  const empty = sessionLog.length === 0;

  return (
    <Page>
      <PageHeader
        center
        title="Session Log"
        subtitle="Agent activity from this session — kept on this device between sessions."
      >
        <Caption>{sessionLog.length} event{sessionLog.length === 1 ? "" : "s"}</Caption>
        <Button variant="quiet" size="sm" onClick={onClear} disabled={empty}>Clear log</Button>
      </PageHeader>

      {empty ? (
        <Card>
          <EmptyState msg="No events yet — send a chat message to see activity here." />
        </Card>
      ) : (
        <Stack gap="sm">
          {[...sessionLog].reverse().map((e, i) => (
            // `e.color` is the responding agent's identity color, carried on the
            // log entry itself — data, not a styling decision made here.
            <Card key={i} pad="sm" rule={e.color}>
              <Row gap="lg">
                <Micro mono>{e.ts}</Micro>
                <Small tone={e.color} weight={600}>{e.msg}</Small>
              </Row>
            </Card>
          ))}
        </Stack>
      )}
    </Page>
  );
}
