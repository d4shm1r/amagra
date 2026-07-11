"""
Free-registration email canonicalization tests (#132).

Proves the 3-key cap can no longer be bypassed with plus-addressing or
gmail dot tricks, and that distinct mailboxes are still counted apart.

Relies on conftest.py for LLM stubs and the temp api-keys DB; points the
registrations DB at its own temp file so counts start from zero.

Run: python3 -m pytest tests/test_register_email_canonicalization.py -v
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import routes.register as reg
from api import app

client = TestClient(app, raise_server_exceptions=False)

_orig_reg_db = reg._REG_DB


def setup_module(module):
    tmp = tempfile.NamedTemporaryFile(suffix="_reg_test.db", delete=False)
    tmp.close()
    os.unlink(tmp.name)  # let _init_reg_db create it fresh
    reg._REG_DB = tmp.name
    reg._init_reg_db()


def teardown_module(module):
    try:
        os.unlink(reg._REG_DB)
    except OSError:
        pass
    reg._REG_DB = _orig_reg_db


def _register(email):
    return client.post("/register/free", json={"email": email, "name": "T"})


# ── Unit: _canonicalize_email ─────────────────────────────────

def test_plus_tag_stripped():
    assert reg._canonicalize_email("abuse+1@x.com") == "abuse@x.com"
    assert reg._canonicalize_email("abuse+a+b@x.com") == "abuse@x.com"


def test_gmail_dots_stripped():
    assert reg._canonicalize_email("f.o.o+tag@gmail.com") == "foo@gmail.com"
    assert reg._canonicalize_email("f.o.o@googlemail.com") == "foo@googlemail.com"


def test_dots_kept_for_other_domains():
    # Most providers treat dots as significant — distinct mailboxes.
    assert reg._canonicalize_email("f.o.o@x.com") == "f.o.o@x.com"


def test_plain_email_unchanged():
    assert reg._canonicalize_email("someone@example.com") == "someone@example.com"


# ── Route: the cap holds across aliases ───────────────────────

def test_cap_not_bypassed_by_plus_addressing():
    # Reproduction from #132: abuse+1..+5 minted 5 keys. Now the first 3
    # succeed and the aliases hit the cap.
    codes = [_register(f"abuse+{i}@test.com").status_code for i in range(1, 6)]
    assert codes == [200, 200, 200, 429, 429]


def test_cap_shared_between_plain_and_tagged():
    assert _register("shared@test.com").status_code == 200
    assert _register("shared+x@test.com").status_code == 200
    assert _register("s.h.a.r.e.d@gmail.com").status_code != 429  # different domain/mailbox
    assert _register("shared+y@test.com").status_code == 200
    assert _register("shared@test.com").status_code == 429


def test_distinct_mailboxes_not_conflated():
    # Dot variants outside gmail are different mailboxes and keep their own cap.
    assert _register("a.b@corp.com").status_code == 200
    assert _register("ab@corp.com").status_code == 200


def test_gmail_dot_variants_share_cap():
    for email in ("capg@gmail.com", "c.apg@gmail.com", "ca.pg@gmail.com"):
        assert _register(email).status_code == 200
    assert _register("c.a.p.g+z@gmail.com").status_code == 429


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
