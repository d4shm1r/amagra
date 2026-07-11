"""
OS-level sandbox isolation tests (#134).

The bwrap-specific tests prove the jail actually blocks host filesystem
reads and network egress; they skip on hosts without a usable bubblewrap
(the /sandbox/status consistency test runs everywhere).

POSIX-only; relies on conftest.py for LLM stubs.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not hasattr(os, "setsid"):
    pytest.skip("POSIX sandbox only", allow_module_level=True)

import tools.sandbox as sbx

_JAILED = sbx.isolation_mode() == "bwrap"
jail_only = pytest.mark.skipif(not _JAILED, reason="no usable bwrap on this host")

# A host file that exists and is readable by the server user — this test file.
_HOST_FILE = os.path.abspath(__file__)


def test_isolation_mode_is_valid_and_reported():
    assert sbx.isolation_mode() in ("bwrap", "rlimit-only")
    r = sbx.run_python("print('x')")
    assert r["isolation"] == sbx.isolation_mode()


def test_no_bwrap_escape_hatch(monkeypatch):
    monkeypatch.setenv("AMAGRA_SANDBOX_NO_BWRAP", "1")
    monkeypatch.setattr(sbx, "_isolation", None)  # drop the cached probe
    assert sbx.isolation_mode() == "rlimit-only"
    monkeypatch.setattr(sbx, "_isolation", None)  # re-probe for later tests


@jail_only
def test_host_filesystem_not_readable():
    r = sbx.run_python(f"print(open({_HOST_FILE!r}).read(10))")
    assert r["exit_code"] != 0
    assert "FileNotFoundError" in r["stderr"]


@jail_only
def test_home_not_visible():
    r = sbx.run_python("import os; print(os.listdir('/home'))")
    assert r["exit_code"] != 0
    assert "FileNotFoundError" in r["stderr"]


@jail_only
def test_network_egress_blocked():
    # --unshare-all gives the jail its own (empty) network namespace: no
    # route out, so this fails immediately — no packet ever leaves the host.
    r = sbx.run_python(
        "import socket\n"
        "s = socket.socket(); s.settimeout(3)\n"
        "s.connect(('1.1.1.1', 443))\n"
        "print('CONNECTED')"
    )
    assert r["exit_code"] != 0
    assert "CONNECTED" not in r["stdout"]
    assert "OSError" in r["stderr"] or "unreachable" in r["stderr"]


@jail_only
def test_traceback_line_numbers_survive_bootstrap():
    r = sbx.run_python("x = 1\nraise ValueError('second line')")
    assert "line 2" in r["stderr"]
    assert "ValueError" in r["stderr"]


@jail_only
def test_workdir_is_writable_inside_jail():
    r = sbx.run_python(
        "open('out.txt', 'w').write('data')\n"
        "print(open('out.txt').read())"
    )
    assert r["exit_code"] == 0
    assert r["stdout"].strip() == "data"


def test_status_route_reports_isolation_honestly():
    from fastapi.testclient import TestClient
    import core.api_keys as _ak
    from api import app

    # Key created at call time, against whatever DB_PATH is active by then —
    # test_auth.py re-points the keys DB during collection, which invalidates
    # keys minted earlier (e.g. conftest's session key).
    headers = {"X-API-Key": _ak.create_key(owner="sbx-iso@test.com", tier="developer")}
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/sandbox/status", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["isolation"] == sbx.isolation_mode()
    jailed = body["isolation"] == "bwrap"
    assert body["network_isolated"] is jailed
    assert body["filesystem_isolated"] is jailed
    # The blast-radius warning must appear exactly when there is no jail.
    assert ("warning" in body) is (not jailed)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
