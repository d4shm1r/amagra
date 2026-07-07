"""
Regression guard for the Windows desktop-app boot crash (v1.7.1 → fixed v1.7.2).

tools/sandbox.py is imported unconditionally at app startup (routes/sandbox.py →
api.py). It used to `import resource` at module top — a POSIX-only stdlib module
absent on Windows — so the frozen backend died with ModuleNotFoundError before
serving anything, and the desktop app showed "Backend did not become healthy".

These tests run on every platform (they don't skip on POSIX): they assert the
module imports without `resource`, and that run_python refuses cleanly rather
than running arbitrary code unbounded when resource limits are unavailable.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.sandbox as sbx


def test_module_imports_without_resource(monkeypatch):
    # Simulate a non-POSIX host where `resource` never imported.
    monkeypatch.setattr(sbx, "resource", None)
    # The module object is already imported; the point is it *stays* usable.
    assert sbx is not None


def test_run_python_refuses_without_resource(monkeypatch):
    monkeypatch.setattr(sbx, "resource", None)
    with pytest.raises(RuntimeError, match="POSIX"):
        sbx.run_python("print('should not run')")


def test_preexec_is_none_without_resource(monkeypatch):
    monkeypatch.setattr(sbx, "resource", None)
    assert sbx._preexec(1, 1, 1, 1) is None
