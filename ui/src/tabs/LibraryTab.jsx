import { useEffect, useRef, useState, useCallback } from "react";
import { API } from "@/lib/api";
import {
  Page, PageHeader, DropZone, Grid, GridSpan, Notice, Loading, EmptyPage, EmptyState,
} from "@/components/ui";
import { SearchInput, FilePicker } from "@/components/forms";
import { DocCard } from "@/components/library/DocCard";
import { ACCEPTED, prettyTitle } from "@/components/library/docMeta";

// Library — the persistent knowledge layer. Documents are presented as objects
// in a collection, never as chunks or embeddings. Status language is
// "Reading… / Read", and the only verbs are Add, Move, Remove.

const DEFAULT_COLLECTIONS = ["Strategy", "Research", "Product", "Personal", "Archive"];

export default function LibraryTab() {
  const [docs,   setDocs]   = useState(null);   // null = loading
  const [query,  setQuery]  = useState("");
  const [notice, setNotice] = useState(null);
  const noticeTimer = useRef(null);

  const flash = (msg) => {
    setNotice(msg);
    clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(null), 3000);
  };

  const load = useCallback(() => {
    fetch(`${API}/documents`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setDocs((d?.documents || []).map(x => ({ ...x, status: "read" }))))
      .catch(() => setDocs([]));
  }, []);

  useEffect(() => { load(); }, [load]);

  const uploadFiles = useCallback(async (files) => {
    const target = "Unsorted";
    for (const file of files) {
      setDocs(prev => [
        { filename: file.name, collection: target, status: "reading", chars: file.size, added: new Date().toISOString() },
        ...(prev || []).filter(d => d.filename !== file.name),
      ]);
      const fd = new FormData();
      fd.append("file", file);
      fd.append("collection", target);
      try {
        const r = await fetch(`${API}/documents/upload`, { method: "POST", body: fd });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          setDocs(prev => (prev || []).map(d => d.filename === file.name ? { ...d, status: "error" } : d));
          flash(err.detail || `Couldn't read ${file.name}`);
          continue;
        }
        const data = await r.json();
        setDocs(prev => (prev || []).map(d => d.filename === data.filename
          ? { ...d, status: "read", chars: data.chars, chunks: data.chunks_stored } : d));
      } catch {
        setDocs(prev => (prev || []).map(d => d.filename === file.name ? { ...d, status: "error" } : d));
        flash("Backend offline — couldn't add the document.");
      }
    }
  }, []);

  const moveDoc = async (doc, collection) => {
    setDocs(prev => prev.map(d => d.filename === doc.filename ? { ...d, collection } : d));
    try {
      await fetch(`${API}/documents/${encodeURIComponent(doc.filename)}/collection`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collection }),
      });
    } catch { flash("Couldn't move the document — backend offline."); load(); }
  };

  const removeDoc = async (doc) => {
    if (!window.confirm(`Remove "${prettyTitle(doc.filename)}" from your Library?`)) return;
    setDocs(prev => prev.filter(d => d.filename !== doc.filename));
    try {
      await fetch(`${API}/documents/${encodeURIComponent(doc.filename)}`, { method: "DELETE" });
    } catch { flash("Couldn't remove the document — backend offline."); load(); }
  };

  // Collections present in the data, plus the defaults, for the Move menu.
  const present     = [...new Set((docs || []).map(d => d.collection || "Unsorted"))];
  const moveTargets = [...new Set([...DEFAULT_COLLECTIONS, ...present])].filter(c => c !== "Unsorted");

  const q       = query.trim().toLowerCase();
  const visible = (docs || []).filter(d =>
    !q || d.filename.toLowerCase().includes(q) || (d.collection || "").toLowerCase().includes(q)
  );

  return (
    <Page>
      <DropZone onDrop={uploadFiles} label="Drop to add to your Library">
        <PageHeader
          center
          title="Library"
          subtitle="Your saved documents and references — searchable and collection-tagged."
        >
          <SearchInput value={query} onChange={setQuery} placeholder="Search your library…" />
          <FilePicker onFiles={uploadFiles} accept={ACCEPTED}>＋ Add documents</FilePicker>
        </PageHeader>

        {notice && <Notice>{notice}</Notice>}

        {docs === null ? (
          <Loading msg="Opening your library…" />
        ) : docs.length === 0 ? (
          <EmptyPage
            title="Your library is empty."
            hint="or drop files anywhere on this page"
            action={
              <FilePicker onFiles={uploadFiles} accept={ACCEPTED} size="lg">
                ＋ Add your first document
              </FilePicker>
            }
          >
            Add documents and Amagra will read them, remember them, and draw on them in every
            conversation.
          </EmptyPage>
        ) : (
          <Grid min={218} gap="lg">
            {visible.map(doc => (
              <DocCard
                key={doc.filename}
                doc={doc}
                collections={moveTargets}
                onMove={moveDoc}
                onRemove={removeDoc}
              />
            ))}
            {visible.length === 0 && (
              <GridSpan>
                <EmptyState msg={`Nothing here${q ? " matches your search" : " yet"}.`} />
              </GridSpan>
            )}
          </Grid>
        )}
      </DropZone>
    </Page>
  );
}
