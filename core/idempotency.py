"""In-memory idempotency store for metered/mutating POST requests (#197).

**Opt-in.** Nothing here runs unless a request carries an `Idempotency-Key`
header, so default traffic is byte-for-byte unchanged. When present, a completed
response is cached for `AMAGRA_IDEMPOTENCY_TTL` seconds (default 600), keyed by
`(scope, key)` where `scope` binds the caller identity so one tenant can never
replay another's response. A replay returns the stored response verbatim and the
caller skips both the work and the usage increment — "run once, count once"
(the acceptance criterion of #197).

Per-process and in-memory, matching the rate limiter (`api._check_minute_limit`):
it does not survive a restart and does not coordinate across replicas — the same
single-node coupling, acceptable for a local-first app and documented as such in
docs/records/OPEN_PROBLEMS.md.

Lifecycle from the middleware:

    hit = idempotency.begin(scope, key)
    if hit is not None:
        return hit                      # replay (200-cached) or 409 (in-flight)
    try:
        response = await call_next(request)
    except Exception:
        idempotency.release(scope, key) # let a retry proceed
        raise
    return await idempotency.finish(scope, key, response)
"""

import os
import threading
import time

from starlette.responses import JSONResponse, Response

try:
    _TTL = float(os.environ.get("AMAGRA_IDEMPOTENCY_TTL", "600"))
except ValueError:
    _TTL = 600.0

_SWEEP_INTERVAL = 60.0  # evict expired entries at most this often

# (scope, key) -> {"state": "inflight"|"done", "ts": monotonic, and for done:
#                  "status", "body", "media_type", "headers"}
_store: dict[tuple[str, str], dict] = {}
_lock = threading.Lock()
_last_sweep = 0.0


def _sweep(now: float) -> None:
    """Drop expired entries; caller holds _lock. Bounded to ≤once/_SWEEP_INTERVAL."""
    global _last_sweep
    if now - _last_sweep < _SWEEP_INTERVAL:
        return
    expired = [k for k, e in _store.items() if now - e["ts"] >= _TTL]
    for k in expired:
        del _store[k]
    _last_sweep = now


def _rebuild(status: int, body: bytes, headers: dict, replay: bool) -> Response:
    """Reconstruct a Response from stored parts.

    Copies the original headers (including content-type — after BaseHTTPMiddleware
    wrapping `response.media_type` is often None, so the content-type only survives
    in the headers) except content-length, which Response recomputes from the body.
    """
    r = Response(content=body, status_code=status)
    for name, value in headers.items():
        if name.lower() == "content-length":
            continue
        r.headers[name] = value
    r.headers["Idempotent-Replay"] = "true" if replay else "false"
    return r


def begin(scope: str, key: str) -> Response | None:
    """Reserve or resolve an idempotency slot for (scope, key).

    Returns None if the caller is the first to use this key (proceed, then call
    finish); a cached Response to return as-is on a completed replay; or a 409
    JSONResponse if an identical request is still in flight.
    """
    now = time.monotonic()
    with _lock:
        _sweep(now)
        entry = _store.get((scope, key))
        if entry is not None and now - entry["ts"] < _TTL:
            if entry["state"] == "done":
                return _rebuild(entry["status"], entry["body"], entry["headers"], replay=True)
            return JSONResponse(
                {"detail": "A request with this Idempotency-Key is already in progress"},
                status_code=409,
            )
        # New, or expired → (re)reserve as in-flight.
        _store[(scope, key)] = {"state": "inflight", "ts": now}
        return None


def release(scope: str, key: str) -> None:
    """Drop an in-flight reservation (e.g. the handler raised) so a retry can run."""
    with _lock:
        entry = _store.get((scope, key))
        if entry is not None and entry["state"] == "inflight":
            del _store[(scope, key)]


async def finish(scope: str, key: str, response: Response) -> Response:
    """Buffer the handler's response, cache it under (scope, key), and return a
    rebuilt Response (the original streaming body has been consumed).

    Only 2xx responses are cached — a client should be able to retry after a
    transient 5xx/4xx rather than have the failure pinned to the key.
    """
    body = b"".join([chunk async for chunk in response.body_iterator])
    now = time.monotonic()

    headers = dict(response.headers)
    if 200 <= response.status_code < 300:
        with _lock:
            _store[(scope, key)] = {
                "state":   "done",
                "ts":      now,
                "status":  response.status_code,
                "body":    body,
                "headers": headers,
            }
    else:
        release(scope, key)

    return _rebuild(response.status_code, body, headers, replay=False)


def _reset_for_tests() -> None:
    with _lock:
        _store.clear()
