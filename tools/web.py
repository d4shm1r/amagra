"""
tools/web.py — live web search behind a small provider abstraction.

The last v1.1 "tool-using agents" capability. Default provider is **SearXNG**
(self-hosted, no API key) so web search fits the "free, self-hosted, zero
third-party telemetry" posture; Brave and Tavily are opt-in keyed alternatives.

Configuration (env):
    WEB_SEARCH_PROVIDER   searxng | brave | tavily   (default: searxng)
    SEARXNG_URL           base URL of a SearXNG instance (e.g. http://localhost:8888)
    BRAVE_API_KEY         for provider=brave
    TAVILY_API_KEY        for provider=tavily

Every provider returns the same shape: a list of {title, url, snippet}.
"""

import os

import requests

DEFAULT_COUNT = 5
MAX_COUNT = 20
TIMEOUT = 10  # seconds


class WebSearchError(Exception):
    """Base for web-search errors."""


class NotConfigured(WebSearchError):
    """The selected provider is missing its configuration (URL or API key)."""


def active_provider() -> str:
    return os.environ.get("WEB_SEARCH_PROVIDER", "searxng").strip().lower() or "searxng"


def is_configured(provider: str | None = None) -> bool:
    """Whether the selected provider has everything it needs to run."""
    provider = provider or active_provider()
    if provider == "searxng":
        return bool(os.environ.get("SEARXNG_URL", "").strip())
    if provider == "brave":
        return bool(os.environ.get("BRAVE_API_KEY", "").strip())
    if provider == "tavily":
        return bool(os.environ.get("TAVILY_API_KEY", "").strip())
    return False


def _searxng(query: str, count: int) -> list[dict]:
    base = os.environ.get("SEARXNG_URL", "").strip().rstrip("/")
    if not base:
        raise NotConfigured("SEARXNG_URL is not set")
    r = requests.get(
        f"{base}/search",
        params={"q": query, "format": "json"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for item in (r.json().get("results") or [])[:count]:
        out.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "") or "",
        })
    return out


def _brave(query: str, count: int) -> list[dict]:
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not key:
        raise NotConfigured("BRAVE_API_KEY is not set")
    r = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": count},
        headers={"Accept": "application/json", "X-Subscription-Token": key},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    results = (r.json().get("web") or {}).get("results") or []
    return [
        {"title": it.get("title", ""), "url": it.get("url", ""),
         "snippet": it.get("description", "") or ""}
        for it in results[:count]
    ]


def _tavily(query: str, count: int) -> list[dict]:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise NotConfigured("TAVILY_API_KEY is not set")
    r = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": key, "query": query, "max_results": count},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return [
        {"title": it.get("title", ""), "url": it.get("url", ""),
         "snippet": it.get("content", "") or ""}
        for it in (r.json().get("results") or [])[:count]
    ]


_PROVIDERS = {"searxng": _searxng, "brave": _brave, "tavily": _tavily}


def search_web(query: str, count: int = DEFAULT_COUNT, provider: str | None = None) -> dict:
    """Run a web search. Returns {provider, query, count, results:[{title,url,snippet}]}.

    Raises NotConfigured if the provider lacks its URL/key, WebSearchError for
    an unknown provider or a transport failure.
    """
    if not query or not query.strip():
        raise WebSearchError("query must not be empty")
    provider = (provider or active_provider()).lower()
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise WebSearchError(f"unknown web-search provider: {provider!r}")
    count = max(1, min(int(count), MAX_COUNT))
    try:
        results = fn(query, count)
    except NotConfigured:
        raise
    except requests.RequestException as e:
        raise WebSearchError(f"{provider} request failed: {e}") from e
    return {"provider": provider, "query": query, "count": len(results), "results": results}
