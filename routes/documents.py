import os, json, sqlite3
from fastapi import APIRouter, UploadFile, File, Form, Body, HTTPException

router = APIRouter(prefix="/documents", tags=["documents"])

_SUPPORTED = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".html", ".css", ".sh",
    ".sql", ".csv", ".pdf", ".toml", ".cfg", ".conf", ".rst",
}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _ensure_db():
    """Create the memories schema if this is a fresh database."""
    try:
        from memory_core.db import init_db
        init_db()
    except Exception:
        pass


def _extract_text(data: bytes, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        try:
            import pypdf
            from io import BytesIO
            reader = pypdf.PdfReader(BytesIO(data))
            return "\n\n".join(p.extract_text() or "" for p in reader.pages)
        except ImportError:
            raise HTTPException(
                status_code=422,
                detail="PDF support requires: pip install pypdf",
            )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def _chunk(text: str, source_file: str, size: int = 800, overlap: int = 100) -> list[dict]:
    """Split text on paragraph boundaries with a hard-split fallback for long paragraphs."""
    paragraphs = text.split("\n\n")
    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                pieces.append(current)
            if len(para) <= size:
                current = para
            else:
                for i in range(0, len(para), size - overlap):
                    piece = para[i : i + size]
                    if piece.strip():
                        pieces.append(piece)
                current = ""
    if current:
        pieces.append(current)

    chunks = [p.strip() for p in pieces if p.strip()]
    return [
        {
            "content": c,
            "metadata": {
                "source_file": source_file,
                "chunk_index": i,
                "total_chunks": len(chunks),
            },
        }
        for i, c in enumerate(chunks)
    ]


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), collection: str = Form("Unsorted")):
    filename = (file.filename or "unknown").replace("/", "_").replace("..", "_")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _SUPPORTED:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported type '{ext}'. Supported: {', '.join(sorted(_SUPPORTED))}",
        )

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    text = _extract_text(data, filename)
    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text found in file")

    chunks = _chunk(text, filename)
    collection = (collection or "Unsorted").strip()[:60] or "Unsorted"
    for chunk in chunks:
        chunk["metadata"]["collection"] = collection

    _ensure_db()
    # Delete stale chunks for this file before re-upload so re-uploads are idempotent
    try:
        from memory_core.db import DB_PATH
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute(
            "DELETE FROM memories WHERE mem_type = 'document' "
            "AND json_extract(metadata, '$.source_file') = ?",
            (filename,),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    from memory_core.backend import get_backend
    backend = get_backend()
    stored = 0
    for chunk in chunks:
        try:
            ok = backend.store(
                content=chunk["content"],
                agent_name="document_rag",
                mem_type="document",
                metadata=chunk["metadata"],
                quality=1.0,
            )
            if ok:
                stored += 1
        except Exception:
            pass

    return {
        "filename": filename,
        "collection": collection,
        "chunks_stored": stored,
        "total_chunks": len(chunks),
        "chars": len(text),
    }


@router.get("")
def list_documents():
    _ensure_db()
    try:
        from memory_core.db import DB_PATH
        conn = sqlite3.connect(DB_PATH, timeout=5)
        rows = conn.execute(
            """SELECT json_extract(metadata, '$.source_file') AS sf,
                      COUNT(*) AS n,
                      MIN(timestamp) AS added,
                      SUM(LENGTH(content)) AS chars,
                      MAX(json_extract(metadata, '$.collection')) AS coll
               FROM memories
               WHERE mem_type = 'document' AND sf IS NOT NULL
               GROUP BY sf
               ORDER BY added DESC"""
        ).fetchall()
        conn.close()
        return {"documents": [
            {
                "filename": sf,
                "chunks": n,
                "added": added,
                "chars": chars or 0,
                "collection": coll or "Unsorted",
            }
            for sf, n, added, chars, coll in rows
        ]}
    except Exception as e:
        return {"documents": [], "error": str(e)}


@router.post("/{filename:path}/collection")
def move_document(filename: str, payload: dict = Body(...)):
    collection = (payload.get("collection") or "Unsorted").strip()[:60] or "Unsorted"
    try:
        from memory_core.db import DB_PATH
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.execute(
            "UPDATE memories SET metadata = json_set(COALESCE(metadata, '{}'), '$.collection', ?) "
            "WHERE mem_type = 'document' AND json_extract(metadata, '$.source_file') = ?",
            (collection, filename),
        )
        conn.commit()
        moved = cur.rowcount
        conn.close()
        return {"filename": filename, "collection": collection, "updated": moved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename:path}")
def delete_document(filename: str):
    try:
        from memory_core.db import DB_PATH
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.execute(
            "DELETE FROM memories WHERE mem_type = 'document' "
            "AND json_extract(metadata, '$.source_file') = ?",
            (filename,),
        )
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        return {"deleted": deleted, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
