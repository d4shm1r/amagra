"""
Unit tests for orchestration/learned_router.py pure functions:
  _onehot, extract_features, _trace_hash, stats (no model), predict (no model/fallback).
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import orchestration.learned_router as lr
import numpy as np


# ── _onehot ───────────────────────────────────────────────────────────────────

def test_onehot_match():
    vocab = ["a", "b", "c"]
    result = lr._onehot("b", vocab)
    assert result == [0, 1, 0]

def test_onehot_no_match():
    vocab = ["a", "b", "c"]
    result = lr._onehot("z", vocab)
    assert result == [0, 0, 0]

def test_onehot_first():
    vocab = ["a", "b", "c"]
    result = lr._onehot("a", vocab)
    assert result == [1, 0, 0]

def test_onehot_last():
    vocab = ["a", "b", "c"]
    result = lr._onehot("c", vocab)
    assert result == [0, 0, 1]

def test_onehot_empty_vocab():
    result = lr._onehot("x", [])
    assert result == []


# ── extract_features ──────────────────────────────────────────────────────────

def test_extract_features_returns_array():
    vec = lr.extract_features("python", 0.85, "code", "normal", "respond")
    assert isinstance(vec, np.ndarray)

def test_extract_features_length():
    vec = lr.extract_features("python", 0.85, "code", "normal", "respond")
    expected_len = (
        len(lr.DOMAINS)
        + 1  # domain_conf
        + len(lr.SHAPES)
        + len(lr.VERBOSITIES)
        + len(lr.ACTIONS)
    )
    assert len(vec) == expected_len

def test_extract_features_unknown_domain():
    vec = lr.extract_features("unknown_domain", 0.5, "explanation", "normal", "respond")
    assert isinstance(vec, np.ndarray)

def test_extract_features_confidence_clipped():
    vec1 = lr.extract_features("python", 1.0, "code", "normal", "respond")
    vec2 = lr.extract_features("python", 0.0, "code", "normal", "respond")
    # Different confidence → different vectors
    assert not np.array_equal(vec1, vec2)

def test_extract_features_dtype():
    vec = lr.extract_features("python", 0.7, "code", "verbose", "build")
    assert vec.dtype == np.float32


# ── _trace_hash ───────────────────────────────────────────────────────────────

def test_trace_hash_empty():
    h = lr._trace_hash([])
    assert isinstance(h, str)
    assert len(h) == 16

def test_trace_hash_deterministic():
    traces = [{"id": "t1"}, {"id": "t2"}]
    h1 = lr._trace_hash(traces)
    h2 = lr._trace_hash(traces)
    assert h1 == h2

def test_trace_hash_different_for_different_ids():
    t1 = [{"id": "a"}]
    t2 = [{"id": "b"}]
    assert lr._trace_hash(t1) != lr._trace_hash(t2)


# ── stats (no model loaded) ───────────────────────────────────────────────────

def test_stats_returns_dict():
    result = lr.stats()
    assert isinstance(result, dict)

def test_stats_has_expected_keys():
    result = lr.stats()
    # Either has model info or "no model" marker
    assert len(result) > 0


# ── train — graceful degradation guards ──────────────────────────────────────

def _trace(agent, _id):
    return {
        "id": f"t{_id}",
        "signal": {"domain": "python", "conf": 0.8, "shape": "code", "verbosity": "normal"},
        "routing": {"final_agent": agent, "action": "build"},
        "labels": {"correct_agent": agent, "label_trustworthy": True},
    }

def test_train_single_class_returns_error_not_crash():
    # All traces route to one agent → can't fit a classifier. Must return a
    # graceful error dict (→ 503), never raise (regression: stats endpoint 500).
    traces = [_trace("python_dev", i) for i in range(6)]
    result = lr.train(traces)
    assert result.get("error") == "insufficient class diversity to train"
    assert result["n_classes"] == 1

def test_train_two_classes_fits_and_reports_cv(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "_MODEL_PATH", str(tmp_path / "model.pkl"))
    traces = ([_trace("python_dev", i) for i in range(4)]
              + [_trace("ai_ml", 10 + i) for i in range(4)])
    result = lr.train(traces)
    assert "error" not in result
    assert result["n_samples"] == 8
    assert result["cv_accuracy"] is not None   # ≥2 per class → CV runs

def test_train_rare_class_skips_cv_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "_MODEL_PATH", str(tmp_path / "model.pkl"))
    # 5 python_dev + 1 ai_ml: 2 classes (fits) but rarest class < 2 → CV skipped.
    traces = ([_trace("python_dev", i) for i in range(5)] + [_trace("ai_ml", 99)])
    result = lr.train(traces)
    assert "error" not in result
    assert result["cv_accuracy"] is None


# ── predict (no traces = untrained model) ────────────────────────────────────

def test_predict_returns_result_or_none():
    result = lr.predict(
        domain="python",
        domain_conf=0.85,
        shape="code",
        verbosity="normal",
        action="respond",
    )
    # Returns None (no model) or a tuple/dict depending on model state
    assert result is None or isinstance(result, (dict, tuple))


# ── _load_traces ──────────────────────────────────────────────────────────────

def test_load_traces_nonexistent_file(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "_TRACE_PATH", str(tmp_path / "no_traces.jsonl"))
    result = lr._load_traces()
    assert result == []

def test_load_traces_with_valid_lines(tmp_path, monkeypatch):
    path = str(tmp_path / "traces.jsonl")
    with open(path, "w") as f:
        f.write(json.dumps({"id": "t1", "signal": {}}) + "\n")
        f.write(json.dumps({"id": "t2", "signal": {}}) + "\n")
    monkeypatch.setattr(lr, "_TRACE_PATH", path)
    result = lr._load_traces()
    assert len(result) == 2

def test_load_traces_skips_invalid_json(tmp_path, monkeypatch):
    path = str(tmp_path / "traces.jsonl")
    with open(path, "w") as f:
        f.write('{"id": "valid"}\n')
        f.write('not valid json\n')
        f.write('{"id": "also_valid"}\n')
    monkeypatch.setattr(lr, "_TRACE_PATH", path)
    result = lr._load_traces()
    assert len(result) == 2  # invalid line skipped


# ── train with no usable traces ───────────────────────────────────────────────

def test_train_empty_traces():
    result = lr.train(traces=[])
    assert "error" in result

def test_train_traces_no_valid_agents():
    # Traces where _features_from_trace returns None (unknown agents)
    traces = [{"signal": {}, "routing": {"final_agent": "unknown_xyz", "action": "respond"}, "labels": {}}]
    result = lr.train(traces=traces)
    assert "error" in result


# ── invalidate_cache ──────────────────────────────────────────────────────────

def test_invalidate_cache():
    lr.invalidate_cache()
    assert lr._cached_payload is None


# ── trustworthy-label gate (leakage guard, issue #19) ─────────────────────────

def test_is_trainable_rejects_fuzzy_join():
    assert lr._is_trainable({"labels": {"label_trustworthy": True}})
    assert not lr._is_trainable({"labels": {"label_trustworthy": False}})

def test_is_trainable_rejects_thumbs_down():
    t = {"labels": {"label_trustworthy": True}, "feedback": {"rating": -1}}
    assert not lr._is_trainable(t)
    t_up = {"labels": {"label_trustworthy": True}, "feedback": {"rating": 1}}
    assert lr._is_trainable(t_up)

def test_is_trainable_defaults_keep():
    # Missing fields → keep (eval seeds / unrated traces).
    assert lr._is_trainable({})
    assert lr._is_trainable({"labels": {}, "feedback": {}})

def test_train_drops_untrustworthy_traces(tmp_path, monkeypatch):
    # Don't clobber the real model on disk.
    monkeypatch.setattr(lr, "_MODEL_PATH", str(tmp_path / "router.pkl"))

    def _trace(agent, domain, trustworthy=True, rating=None):
        return {
            "signal": {"domain": domain, "conf": 0.7, "shape": "code",
                       "verbosity": "normal"},
            "routing": {"final_agent": agent, "action": "build"},
            "labels": {"correct_agent": agent, "label_trustworthy": trustworthy},
            "feedback": {"rating": rating},
        }
    # Two classes so LogisticRegression can fit.
    traces = (
        [_trace("python_dev", "python") for _ in range(6)]
        + [_trace("it_networking", "networking") for _ in range(6)]
        + [_trace("dotnet_dev", "blazor", trustworthy=False)]  # fuzzy → dropped
        + [_trace("ai_ml", "ai_ml", rating=-1)]                # 👎 → dropped
    )
    res = lr.train(traces, trustworthy_only=True)
    assert res.get("dropped_untrustworthy") == 2
    assert res["n_samples"] == 12
    res_all = lr.train(traces, trustworthy_only=False)
    assert res_all.get("dropped_untrustworthy") == 0
    assert res_all["n_samples"] == 14
