"""
routes/search.py — HTTP surface for tools/web.py (live web search).

GET /search/web?q=...   run a search via the configured provider
GET /search/status      which provider is active and whether it's configured
"""

from fastapi import APIRouter, HTTPException

import tools.web as web

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/status")
def status():
    provider = web.active_provider()
    return {"provider": provider, "configured": web.is_configured(provider)}


@router.get("/web")
def web_search(q: str, count: int = web.DEFAULT_COUNT, provider: str | None = None):
    try:
        return web.search_web(q, count=count, provider=provider)
    except web.NotConfigured as e:
        # 503: the feature exists but this deployment hasn't wired a backend.
        raise HTTPException(status_code=503, detail=str(e))
    except web.WebSearchError as e:
        raise HTTPException(status_code=400, detail=str(e))
