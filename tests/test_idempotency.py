"""Idempotency store (#197) — unit tests + middleware integration.

Unit tests exercise core/idempotency.py directly (begin/finish/release, replay,
409-in-flight, scope isolation, non-2xx not cached). The integration test drives
the real auth middleware via TestClient: two POSTs with the same Idempotency-Key
return the *same* stored response ("run once"), and carry Idempotent-Replay.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.idempotency as idem


def setup_function(_):
    idem._reset_for_tests()


class _FakeResp:
    """Stands in for the StreamingResponse call_next returns (has body_iterator)."""

    def __init__(self, body=b'{"ok":1}', status=200, headers=None):
        self._body = body if isinstance(body, bytes) else body.encode()
        self.status_code = status
        self.media_type = "application/json"
        self.headers = headers or {"content-type": "application/json"}

    @property
    def body_iterator(self):
        async def _gen():
            yield self._body
        return _gen()


# ── Unit: begin / finish / replay ─────────────────────────────────────────────

def test_reserve_then_inflight_then_replay():
    assert idem.begin("s", "k1") is None                       # first caller proceeds
    inflight = idem.begin("s", "k1")                           # concurrent duplicate
    assert inflight is not None and inflight.status_code == 409

    done = asyncio.run(idem.finish("s", "k1", _FakeResp(b'{"id":7}')))
    assert done.status_code == 200
    assert done.headers["Idempotent-Replay"] == "false"
    assert done.body == b'{"id":7}'

    replay = idem.begin("s", "k1")                             # now cached
    assert replay is not None and replay.status_code == 200
    assert replay.body == b'{"id":7}'
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.headers["content-type"].startswith("application/json")


def test_scope_isolation():
    assert idem.begin("key:1", "x") is None
    asyncio.run(idem.finish("key:1", "x", _FakeResp(b'{"a":1}')))
    # Same key, different caller scope → not a replay; proceeds fresh.
    assert idem.begin("key:2", "x") is None


def test_release_allows_retry():
    assert idem.begin("s", "k2") is None
    idem.release("s", "k2")
    assert idem.begin("s", "k2") is None   # reservation cleared → first again


def test_non_2xx_not_cached():
    assert idem.begin("s", "k3") is None
    out = asyncio.run(idem.finish("s", "k3", _FakeResp(b'{"e":1}', status=500)))
    assert out.status_code == 500
    # A transient failure must not pin the key — the retry runs fresh.
    assert idem.begin("s", "k3") is None


# ── Integration: real middleware via TestClient ───────────────────────────────

from fastapi.testclient import TestClient  # noqa: E402
from api import app  # noqa: E402
import core.api_keys as _ak  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
_key = _ak.create_key(owner="idem-test@test.com", tier="developer")
_H = {"X-API-Key": _key}


def test_same_key_replays_same_task():
    idem._reset_for_tests()
    h = {**_H, "Idempotency-Key": "int-same-1"}
    r1 = client.post("/tasks/create", json={"prompt": "idem work"}, headers=h)
    r2 = client.post("/tasks/create", json={"prompt": "idem work"}, headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["task_id"] == r2.json()["task_id"]        # ran once
    assert r2.headers.get("Idempotent-Replay") == "true"


def test_different_keys_run_again():
    idem._reset_for_tests()
    r1 = client.post("/tasks/create", json={"prompt": "a"}, headers={**_H, "Idempotency-Key": "int-A"})
    r2 = client.post("/tasks/create", json={"prompt": "a"}, headers={**_H, "Idempotency-Key": "int-B"})
    assert r1.json()["task_id"] != r2.json()["task_id"]


def test_no_header_is_unchanged():
    r1 = client.post("/tasks/create", json={"prompt": "a"}, headers=_H)
    r2 = client.post("/tasks/create", json={"prompt": "a"}, headers=_H)
    assert r1.json()["task_id"] != r2.json()["task_id"]
    assert "Idempotent-Replay" not in r1.headers
