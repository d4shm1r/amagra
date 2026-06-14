import os
import sqlite3
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import Response

from .deps import _ROOT, _CONTRADICTIONS_DB

router = APIRouter()


@router.get("/memory")
def get_memory():
    memory_dir = os.path.join(_ROOT, "memory")
    files = []
    for root, dirs, filenames in os.walk(memory_dir):
        for filename in filenames:
            if filename.startswith('.'): continue
            path  = os.path.join(root, filename)
            rel   = os.path.relpath(path, memory_dir)
            size  = os.path.getsize(path)
            from datetime import datetime
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
            files.append({"path": rel, "size": size, "modified": mtime})
    return {"files": sorted(files, key=lambda x: x["modified"], reverse=True)}


@router.get("/memory/records")
def get_memory_records(limit: int = 300, agent: str = "", mem_type: str = ""):
    try:
        from infrastructure.db import path as _dbpath
        DB = _dbpath("memory")
        conn = sqlite3.connect(DB, timeout=10)
        q = "SELECT id, timestamp, agent_name, mem_type, content, quality, use_count FROM memories"
        clauses, params = [], []
        if agent:    clauses.append("agent_name=?"); params.append(agent)
        if mem_type: clauses.append("mem_type=?");   params.append(mem_type)
        if clauses:  q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return [
            {"id": r[0], "timestamp": r[1], "agent": r[2], "type": r[3],
             "content": (r[4] or "")[:300], "quality": round(float(r[5] or 0), 3),
             "use_count": r[6] or 0}
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/memory/stats")
def get_memory_stats():
    try:
        import memory_core.db as memory_db
        from memory_core.backend import get_backend
        stats = memory_db.memory_stats()
        stats["backend"] = get_backend().backend_info()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/prune")
def preview_prune():
    try:
        import memory_core.db as memory_db
        return memory_db.prune(dry_run=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/prune")
def execute_prune():
    try:
        import memory_core.db as memory_db
        return memory_db.prune(dry_run=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/consolidate")
def preview_consolidate(threshold: float = 0.93):
    try:
        import memory_core.db as memory_db
        return memory_db.consolidate(threshold=threshold, dry_run=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/consolidate")
def execute_consolidate(threshold: float = 0.93):
    try:
        import memory_core.db as memory_db
        from memory_core.backend import get_backend
        result = memory_db.consolidate(threshold=threshold, dry_run=False)
        try:
            get_backend()._build_index()
        except Exception:
            pass
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/auto-resolve")
def preview_auto_resolve(threshold: float = 0.90):
    try:
        import memory_core.db as memory_db
        return memory_db.auto_resolve_conflicts(threshold=threshold, dry_run=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/auto-resolve")
def execute_auto_resolve(threshold: float = 0.90):
    try:
        import memory_core.db as memory_db
        from memory_core.backend import get_backend
        result = memory_db.auto_resolve_conflicts(threshold=threshold, dry_run=False)
        try:
            get_backend()._build_index()
        except Exception:
            pass
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/audit")
def get_memory_audit(limit: int = 20):
    try:
        import memory_core.db as memory_db
        audits = memory_db.get_recent_audits(limit=min(limit, 100))
        return {"audits": audits, "count": len(audits)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/for-query")
def get_memories_for_query(q: str = "", n: int = 5):
    import memory_core.db as _mdb
    return _mdb.get_last_accessed_content(q, n=n)


@router.get("/memory/at-risk")
def get_at_risk_memories(n: int = 30):
    try:
        import memory_core.db as _mdb
        return {"at_risk": _mdb.at_risk_memories(n=n)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/export.csv")
def export_memories_csv():
    try:
        import memory_core.db as _mdb
        csv_data = _mdb.export_memories_csv()
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=memories.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/export.json")
def export_memories_json(agent: str = "", embeddings: bool = True):
    """Full-fidelity JSON export (lossless re-import when embeddings=true)."""
    try:
        import memory_core.db as _mdb
        data = _mdb.export_memories_json(
            agent_name=agent or None, include_embeddings=embeddings
        )
        return Response(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=memories.json"},
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/memory/export.md")
def export_memories_markdown(agent: str = ""):
    """Human-readable Markdown export, grouped by agent."""
    try:
        import memory_core.db as _mdb
        data = _mdb.export_memories_markdown(agent_name=agent or None)
        return Response(
            content=data,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=memories.md"},
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/memory/import")
def import_memories(payload: dict = Body(...), reembed: bool = False):
    """Import a JSON memory export. Dedups, then rebuilds the search index."""
    try:
        import memory_core.db as _mdb
        result = _mdb.import_memories_json(payload, reembed=reembed)
        if result["imported"]:
            try:
                from memory_core.backend import get_backend
                get_backend()._build_index()
            except Exception:
                pass
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/coherence")
def get_coherence(window: int = 20):
    from cognition.coherence import current_coherence
    from dataclasses import asdict
    state = current_coherence(window)
    return asdict(state)


@router.get("/coherence/dynamics")
def get_coherence_dynamics(window: int = 20):
    from cognition.coherence import coherence_time_series
    return coherence_time_series(window)


@router.get("/coherence/memory")
def get_coherence_memory():
    from cognition.coherence import memory_coherence_history
    return memory_coherence_history()


@router.get("/coherence/reflection")
def get_reflection_gain():
    from cognition.coherence import reflection_gain_analysis
    return reflection_gain_analysis()


@router.get("/contradictions")
def get_contradictions(limit: int = 50):
    try:
        conn = sqlite3.connect(_CONTRADICTIONS_DB)
        rows = conn.execute(
            "SELECT id, timestamp, agent, query, response_snip, reflect_level "
            "FROM contradictions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [
            {"id": r[0], "timestamp": r[1], "agent": r[2],
             "query": r[3], "response_snip": r[4], "reflect_level": r[5]}
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
