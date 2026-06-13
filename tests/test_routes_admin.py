"""
Tests for admin and registration routes:
  GET  /usage
  POST /admin/keys
  GET  /admin/keys
  DELETE /admin/keys/{id}
  POST /admin/orgs
  GET  /admin/orgs
  POST /register/free
  GET  /pricing
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app
import api as _api

_ADMIN_TOKEN = "test-admin-token"
_orig_admin_token = None

def setup_module(module):
    global _orig_admin_token
    _orig_admin_token = _api._ADMIN_TOKEN
    _api._ADMIN_TOKEN = _ADMIN_TOKEN

def teardown_module(module):
    if _orig_admin_token is not None:
        _api._ADMIN_TOKEN = _orig_admin_token

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key      = _ak.create_key(owner="admin-test@test.com", tier="developer")
HEADERS   = {"X-API-Key": _key}
# Admin routes need both tokens when REQUIRE_AUTH=1 (set by test_auth.py import)
ADMIN_HDR = {"X-Admin-Token": _ADMIN_TOKEN, "X-API-Key": _key}


# ── GET /usage ────────────────────────────────────────────────────────────────

def test_usage_no_key():
    r = client.get("/usage")
    assert r.status_code == 401

def test_usage_invalid_key():
    r = client.get("/usage", headers={"X-API-Key": "invalid-key-xyz"})
    assert r.status_code == 403

def test_usage_valid_key():
    r = client.get("/usage", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "tier" in data
    assert data["tier"] == "developer"


# ── POST /admin/keys ──────────────────────────────────────────────────────────

def test_create_key_free():
    r = client.post("/admin/keys", json={"owner": "new@test.com", "tier": "free"}, headers=ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    assert "key" in data
    assert data["tier"] == "free"
    assert data["owner"] == "new@test.com"
    assert "note" in data

def test_create_key_developer():
    r = client.post("/admin/keys", json={"owner": "dev@test.com", "tier": "developer"}, headers=ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["tier"] == "developer"

def test_create_key_invalid_tier():
    r = client.post("/admin/keys", json={"owner": "x@test.com", "tier": "superadmin"}, headers=ADMIN_HDR)
    assert r.status_code == 400

def test_create_key_with_org_id():
    r = client.post("/admin/keys", json={
        "owner": "org@test.com", "tier": "team", "org_id": "org-abc123"
    }, headers=ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["org_id"] == "org-abc123"


# ── GET /admin/keys ───────────────────────────────────────────────────────────

def test_list_keys():
    r = client.get("/admin/keys", headers=ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    assert "keys" in data
    assert isinstance(data["keys"], list)
    assert len(data["keys"]) >= 1


# ── DELETE /admin/keys/{id} ───────────────────────────────────────────────────

def test_deactivate_key():
    r = client.post("/admin/keys", json={"owner": "del@test.com", "tier": "free"}, headers=ADMIN_HDR)
    assert r.status_code == 200

    keys = client.get("/admin/keys", headers=ADMIN_HDR).json()["keys"]
    key_id = next(k["id"] for k in keys if k["owner"] == "del@test.com")

    r = client.delete(f"/admin/keys/{key_id}", headers=ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["deactivated"] == key_id


# ── POST /admin/orgs ──────────────────────────────────────────────────────────

def test_create_org():
    r = client.post("/admin/orgs", json={"name": "Test Org", "owner_email": "org@test.com"}, headers=ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    assert "org_id" in data
    assert data["org_id"].startswith("org-")
    assert data["name"] == "Test Org"

def test_create_org_no_email():
    r = client.post("/admin/orgs", json={"name": "Anonymous Org"}, headers=ADMIN_HDR)
    assert r.status_code == 200
    assert "org_id" in r.json()


# ── GET /admin/orgs ───────────────────────────────────────────────────────────

def test_list_orgs():
    client.post("/admin/orgs", json={"name": "Listed Org"}, headers=ADMIN_HDR)
    r = client.get("/admin/orgs", headers=ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    assert "orgs" in data
    assert isinstance(data["orgs"], list)


# ── GET /pricing ──────────────────────────────────────────────────────────────

def test_pricing_public():
    r = client.get("/pricing")
    assert r.status_code == 200
    data = r.json()
    assert "plans" in data
    plans = {p["id"]: p for p in data["plans"]}
    assert "free" in plans
    assert "developer" in plans
    assert plans["free"]["price_usd"] == 0
    assert plans["developer"]["price_usd"] == 39


# ── POST /register/free ───────────────────────────────────────────────────────

def test_register_free_valid():
    import time
    email = f"newuser-{int(time.time()*1000)}@example.com"
    r = client.post("/register/free", json={"email": email, "name": "Test"})
    assert r.status_code == 200
    data = r.json()
    assert "key" in data
    assert data["tier"] == "free"
    assert data["daily_limit"] == 100

def test_register_free_no_name_uses_email():
    import time
    email = f"noname-{int(time.time()*1000)}@example.com"
    r = client.post("/register/free", json={"email": email})
    assert r.status_code == 200
    assert "key" in r.json()

def test_register_free_invalid_email():
    r = client.post("/register/free", json={"email": "not-an-email"})
    assert r.status_code == 422

def test_register_free_rate_limit():
    import time
    email = f"ratelimited-{int(time.time()*1000)}@example.com"
    for _ in range(3):
        r = client.post("/register/free", json={"email": email})
        assert r.status_code == 200
    r = client.post("/register/free", json={"email": email})
    assert r.status_code == 429
