import sys
import os
import asyncio
import sqlite3
import time
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env before anything else so env vars are available at import time
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)
except Exception:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import core.api_keys as _ak

_REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "0") == "1"
_ADMIN_TOKEN  = os.environ.get("ADMIN_TOKEN", "")

# Deny-by-default: only these paths bypass the customer key gate
_PUBLIC_PATHS    = {"/", "/health", "/usage", "/openapi.json", "/pricing", "/register/free", "/setup/status", "/setup/pull"}
_PUBLIC_PREFIXES = ("/docs", "/redoc")  # FastAPI UI and Amagra docs sub-paths

# Per-minute request caps per tier (0 = unlimited)
_MINUTE_LIMITS = {"free": 10, "developer": 60, "team": 300, "enterprise": 0}
# In-memory per-key minute windows: key_id -> (count, window_start_monotonic)
_minute_window: dict[int, tuple[int, float]] = {}

# CORS — set ALLOWED_ORIGINS env var (comma-separated) for production;
# defaults to localhost only so a drive-by page can't call the API.
_ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000"
    ).split(",")
    if o.strip()
]

from routes.maintenance import maintenance_loop
from routes.tasks import task_worker


_ENV = os.environ.get("ENV", "development").lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(maintenance_loop())

    # ── Auth safety check ─────────────────────────────────────
    if _ENV == "production" and not _REQUIRE_AUTH:
        raise RuntimeError(
            "REQUIRE_AUTH=0 in production ENV — set REQUIRE_AUTH=1 to protect endpoints"
        )
    if not _REQUIRE_AUTH:
        print("⚠  [startup] REQUIRE_AUTH=0 — all endpoints are open (dev mode)")
        print("⚠  [startup] Set REQUIRE_AUTH=1 before exposing to the internet")

    try:
        from memory_core.backend import get_backend, promote_if_needed
        backend  = get_backend()
        info     = backend.backend_info()
        promoted = promote_if_needed()
        if not promoted:
            print(f"[startup] Memory backend: {info['type']} ({info.get('total', '?')} entries)")
    except Exception as e:
        print(f"[startup] backend check failed: {e}")

    # ── Warm up the embedding model ────────────────────────────
    # The first embed call lazily loads nomic-embed-text in Ollama (3–8s).
    # Fire it in the background at startup so the first real user query
    # doesn't eat the cold-load latency. Failure is non-fatal.
    async def _warm_embeddings():
        try:
            import memory_core.db as _wdb
            await asyncio.to_thread(_wdb.get_embedding, "warmup")
            print("[startup] Embedding model warmed up")
        except Exception as e:
            print(f"[startup] embedding warm-up skipped: {e}")
    asyncio.create_task(_warm_embeddings())

    try:
        import memory_core.db as _mdb
        conn = sqlite3.connect(_mdb.DB_PATH, timeout=5)
        conn.execute("ALTER TABLE memories ADD COLUMN owner_key_id INTEGER")
        conn.commit()
        conn.close()
        print("[startup] Migrated memories table: added owner_key_id column")
    except sqlite3.OperationalError:
        pass
    except Exception as e:
        print(f"[startup] memory migration warning: {e}")

    try:
        from infrastructure.db import path as _dbpath
        conn = sqlite3.connect(_dbpath("tasks"))
        pending = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='pending'"
        ).fetchone()[0]
        conn.close()
        if pending:
            asyncio.create_task(task_worker())
    except Exception:
        pass

    # ── Enable WAL mode on all SQLite databases ────────────────
    # WAL allows concurrent readers + 1 writer, eliminating "database is locked"
    # errors under the async /ask path and any concurrent API calls.
    # Paths come from the central registry, so this honours single-file mode
    # (AMAGRA_DB) automatically and never drifts from the real DB layout.
    from infrastructure.db import distinct_paths as _distinct_db_paths
    for _path in _distinct_db_paths():
        if os.path.exists(_path):
            try:
                _c = sqlite3.connect(_path, timeout=3)
                _c.execute("PRAGMA journal_mode=WAL")
                _c.execute("PRAGMA synchronous=NORMAL")
                _c.close()
            except Exception:
                pass
    print("[startup] WAL mode enabled on all SQLite databases")

    yield


app = FastAPI(title="Amagra", version="1.0.4", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "X-Admin-Token", "Content-Type", "Authorization"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # ── Admin gate (always active, independent of REQUIRE_AUTH) ──────────────
    # Requires ADMIN_TOKEN to be explicitly set — no IP-based bypass, which
    # breaks behind any reverse proxy (nginx/Caddy/Traefik all forward as 127.0.0.1).
    if path.startswith("/admin/"):
        if not _ADMIN_TOKEN:
            return JSONResponse(
                {"detail": "Admin access disabled. Set ADMIN_TOKEN env var to enable."},
                status_code=503,
            )
        if request.headers.get("X-Admin-Token", "") != _ADMIN_TOKEN:
            return JSONResponse({"detail": "X-Admin-Token required"}, status_code=403)

    # ── Customer key gate (deny-by-default) ──────────────────────────────────
    _usage = None
    if _REQUIRE_AUTH:
        is_public = path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES)
        if not is_public:
            raw = request.headers.get("X-API-Key", "")
            if not raw:
                return JSONResponse({"detail": "X-API-Key header required"}, status_code=401)
            rec = _ak.verify_key(raw)
            if not rec:
                return JSONResponse({"detail": "Invalid or inactive API key"}, status_code=403)
            _usage = _ak.increment_usage(rec["id"])
            request.state.key_id = rec["id"]
            if rec.get("org_id"):
                request.state.org_id = rec["org_id"]

            # Daily limit check
            daily_limit = _usage.get("limit", 0)
            if daily_limit and _usage.get("requests_today", 0) > daily_limit:
                return JSONResponse(
                    {"detail": f"Daily limit ({daily_limit} req/day) exceeded"}, status_code=429
                )

            # Per-minute burst limit — prevents cost-of-goods attacks on free tier
            minute_limit = _MINUTE_LIMITS.get(_usage.get("tier", "free"), 10)
            if minute_limit:
                key_id = rec["id"]
                now = time.monotonic()
                count, window_start = _minute_window.get(key_id, (0, now - 61))
                if now - window_start >= 60:
                    count, window_start = 1, now
                else:
                    count += 1
                _minute_window[key_id] = (count, window_start)
                if count > minute_limit:
                    return JSONResponse(
                        {"detail": f"Rate limit exceeded: {minute_limit} req/minute"},
                        status_code=429,
                    )

    response = await call_next(request)

    # ── Rate-limit headers (standard API convention) ────────────────────────
    if _usage:
        lim       = _usage.get("limit", 0)
        used      = _usage.get("requests_today", 0)
        remaining = max(0, lim - used) if lim else None
        response.headers["X-RateLimit-Limit"]     = str(lim) if lim else "unlimited"
        response.headers["X-RateLimit-Used"]      = str(used)
        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)

    return response


from routes.core        import router as core_router
from routes.register    import router as register_router
from routes.cos         import router as cos_router
from routes.risk        import router as risk_router
from routes.memory      import router as memory_router
from routes.tasks       import router as tasks_router
from routes.goals       import router as goals_router
from routes.learning    import router as learning_router
from routes.feedback    import router as feedback_router
from routes.analysis    import router as analysis_router
from routes.maintenance import router as maintenance_router
from routes.snapshots   import router as snapshots_router
from routes.docs_api    import router as docs_router
from routes.admin       import router as admin_router
from routes.documents   import router as documents_router
from routes.setup       import router as setup_router
from routes.workspace   import router as workspace_router
from routes.sandbox     import router as sandbox_router
from routes.search      import router as search_router
from routes.tools       import router as tools_router

app.include_router(core_router)
app.include_router(register_router)
app.include_router(cos_router)
app.include_router(risk_router)
app.include_router(memory_router)
app.include_router(tasks_router)
app.include_router(goals_router)
app.include_router(learning_router)
app.include_router(feedback_router)
app.include_router(analysis_router)
app.include_router(maintenance_router)
app.include_router(snapshots_router)
app.include_router(docs_router)
app.include_router(admin_router)
app.include_router(documents_router)
app.include_router(setup_router)
app.include_router(workspace_router)
app.include_router(sandbox_router)
app.include_router(search_router)
app.include_router(tools_router)
