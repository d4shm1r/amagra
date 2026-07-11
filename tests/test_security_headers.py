"""
Security response-header tests (#133).

Proves every response — public routes, auth rejections, docs pages —
carries nosniff / X-Frame-Options / CSP, and that HSTS is emitted only
over HTTPS (direct or via a TLS-terminating reverse proxy).

Relies on conftest.py for LLM stubs and the temp api-keys DB.

Run: python3 -m pytest tests/test_security_headers.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import api as api_module
from api import app

client = TestClient(app, raise_server_exceptions=False)

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def _assert_base_headers(resp):
    for name, want in BASE_HEADERS.items():
        assert resp.headers.get(name) == want, f"{name} missing/wrong on {resp.url}"
    assert "Content-Security-Policy" in resp.headers


def test_public_route_has_security_headers():
    resp = client.get("/health")
    assert resp.status_code == 200
    _assert_base_headers(resp)
    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "cdn.jsdelivr.net" not in csp  # strict app CSP, not the docs one


def test_auth_rejection_has_security_headers(monkeypatch):
    # Outermost middleware must stamp headers even on the auth guard's
    # early-return 401.
    monkeypatch.setattr(api_module, "_REQUIRE_AUTH", True)
    resp = client.get("/tasks/status")
    assert resp.status_code == 401
    _assert_base_headers(resp)


def test_docs_page_gets_relaxed_csp():
    resp = client.get("/docs")
    assert resp.status_code == 200
    _assert_base_headers(resp)
    csp = resp.headers["Content-Security-Policy"]
    assert "https://cdn.jsdelivr.net" in csp  # swagger bundle host
    assert "frame-ancestors 'none'" in csp


def test_openapi_json_gets_strict_csp():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "cdn.jsdelivr.net" not in resp.headers["Content-Security-Policy"]


def test_no_hsts_over_plain_http():
    resp = client.get("/health")
    assert "Strict-Transport-Security" not in resp.headers


def test_hsts_over_https():
    https_client = TestClient(app, base_url="https://testserver",
                              raise_server_exceptions=False)
    resp = https_client.get("/health")
    assert resp.headers.get("Strict-Transport-Security", "").startswith("max-age=")


def test_hsts_behind_tls_terminating_proxy():
    resp = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert resp.headers.get("Strict-Transport-Security", "").startswith("max-age=")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
