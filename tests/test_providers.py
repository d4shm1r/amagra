"""
Unit tests for providers/registry.py and providers/manifest.py — no LLM, no
network. Registry tests exercise the lazy-singleton caching and env-var backend
selection; manifest tests cover schema parsing, YAML loading, and the
KEYWORD_MAP conversion. The anthropic backend path is not exercised (it needs the
SDK + an API key); only the default-local paths are.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import providers.registry as registry
from providers.manifest import (
    AgentManifest,
    load_manifests,
    manifest_to_keyword_map,
)
from providers.ollama import OllamaEmbeddingProvider, OllamaProvider


# ── registry: get_provider ───────────────────────────────────────────────────

def _clear_registry_caches():
    registry._model_cache.clear()
    registry._embed_cache.clear()


def test_get_provider_signal_defaults_to_ollama(monkeypatch):
    _clear_registry_caches()
    monkeypatch.delenv("SIGNAL_PROVIDER", raising=False)
    p = registry.get_provider("signal")
    assert isinstance(p, OllamaProvider)


def test_get_provider_brain_defaults_to_ollama(monkeypatch):
    _clear_registry_caches()
    monkeypatch.delenv("BRAIN_PROVIDER", raising=False)
    p = registry.get_provider("brain")
    assert isinstance(p, OllamaProvider)


def test_get_provider_is_cached_singleton(monkeypatch):
    _clear_registry_caches()
    monkeypatch.delenv("BRAIN_PROVIDER", raising=False)
    first = registry.get_provider("brain")
    second = registry.get_provider("brain")
    assert first is second


def test_get_provider_signal_and_brain_are_distinct(monkeypatch):
    _clear_registry_caches()
    monkeypatch.delenv("SIGNAL_PROVIDER", raising=False)
    monkeypatch.delenv("BRAIN_PROVIDER", raising=False)
    # Different roles cache under different keys even with the same backend.
    assert registry.get_provider("signal") is not registry.get_provider("brain")


def test_get_provider_unknown_backend_falls_back_to_ollama(monkeypatch):
    _clear_registry_caches()
    monkeypatch.setenv("BRAIN_PROVIDER", "definitely-not-a-provider")
    assert isinstance(registry.get_provider("brain"), OllamaProvider)


# ── registry: get_embedding_provider ─────────────────────────────────────────

def test_get_embedding_provider_returns_ollama(monkeypatch):
    _clear_registry_caches()
    monkeypatch.delenv("EMBED_PROVIDER", raising=False)
    p = registry.get_embedding_provider()
    assert isinstance(p, OllamaEmbeddingProvider)


def test_get_embedding_provider_is_cached(monkeypatch):
    _clear_registry_caches()
    monkeypatch.delenv("EMBED_PROVIDER", raising=False)
    assert registry.get_embedding_provider() is registry.get_embedding_provider()


# ── manifest: AgentManifest.from_dict ────────────────────────────────────────

def test_manifest_from_dict_full():
    m = AgentManifest.from_dict({
        "id": "python_dev",
        "name": "Python Dev",
        "description": "Writes Python.",
        "skills": ["coding"],
        "keywords": ["python", "pytest"],
        "routing_examples": ["write a function"],
        "confidence_threshold": 0.9,
        "capabilities": ["coding", "execution"],
        "provider": "local",
        "entrypoint": "agents.python_dev:build",
    })
    assert m.id == "python_dev"
    assert m.keywords == ["python", "pytest"]
    assert m.confidence_threshold == 0.9
    assert m.capabilities == ["coding", "execution"]


def test_manifest_from_dict_applies_defaults():
    m = AgentManifest.from_dict({"id": "x", "name": "X"})
    assert m.description == ""
    assert m.skills == []
    assert m.keywords == []
    assert m.confidence_threshold == 0.75
    assert m.provider == "local"
    assert m.entrypoint == ""


def test_manifest_from_dict_coerces_threshold_to_float():
    m = AgentManifest.from_dict({"id": "x", "name": "X", "confidence_threshold": "0.5"})
    assert isinstance(m.confidence_threshold, float)
    assert m.confidence_threshold == 0.5


# ── manifest: load_manifests ─────────────────────────────────────────────────

def _write_yaml(path, text):
    path.write_text(text)


def test_load_manifests_from_extra_dir(tmp_path):
    _write_yaml(tmp_path / "a.yaml", "id: alpha\nname: Alpha\nkeywords: [foo, bar]\n")
    _write_yaml(tmp_path / "b.yaml", "id: beta\nname: Beta\n")
    out = load_manifests(extra_dirs=[str(tmp_path)])
    assert "alpha" in out and "beta" in out
    assert out["alpha"].keywords == ["foo", "bar"]


def test_load_manifests_skips_files_without_id(tmp_path):
    _write_yaml(tmp_path / "bad.yaml", "name: NoId\nkeywords: [x]\n")
    _write_yaml(tmp_path / "empty.yaml", "")
    out = load_manifests(extra_dirs=[str(tmp_path)])
    # Neither malformed file should appear; only bundled manifests (if any) remain.
    assert all(k != "NoId" for k in out)


def test_load_manifests_swallows_malformed_manifest(tmp_path, capsys):
    # Has "id" (passes the guard) but is missing the required "name" field, so
    # from_dict raises KeyError — load_manifests must catch it and keep going.
    _write_yaml(tmp_path / "broken.yaml", "id: broken\nkeywords: [x]\n")
    _write_yaml(tmp_path / "ok.yaml", "id: ok\nname: OK\n")
    out = load_manifests(extra_dirs=[str(tmp_path)])
    assert "broken" not in out
    assert "ok" in out
    assert "failed to load" in capsys.readouterr().out


def test_load_manifests_later_dir_wins_on_collision(tmp_path):
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    _write_yaml(d1 / "a.yaml", "id: dup\nname: First\n")
    _write_yaml(d2 / "a.yaml", "id: dup\nname: Second\n")
    out = load_manifests(extra_dirs=[str(d1), str(d2)])
    assert out["dup"].name == "Second"


def test_load_manifests_missing_dir_is_ignored(tmp_path):
    out = load_manifests(extra_dirs=[str(tmp_path / "does-not-exist")])
    assert isinstance(out, dict)


# ── manifest: manifest_to_keyword_map ────────────────────────────────────────

def test_manifest_to_keyword_map_builds_boundary_regex():
    manifests = {
        "py": AgentManifest.from_dict({"id": "py", "name": "Py", "keywords": ["python"]}),
    }
    km = manifest_to_keyword_map(manifests)
    assert km["py"] == [r"(?<!\w)python(?!\w)"]


def test_manifest_to_keyword_map_escapes_special_chars():
    manifests = {
        "net": AgentManifest.from_dict({"id": "net", "name": "Net", "keywords": ["c++"]}),
    }
    km = manifest_to_keyword_map(manifests)
    assert km["net"] == [r"(?<!\w)c\+\+(?!\w)"]


def test_manifest_to_keyword_map_skips_agents_without_keywords():
    manifests = {
        "empty": AgentManifest.from_dict({"id": "empty", "name": "Empty"}),
        "full": AgentManifest.from_dict({"id": "full", "name": "Full", "keywords": ["x"]}),
    }
    km = manifest_to_keyword_map(manifests)
    assert "empty" not in km
    assert "full" in km
