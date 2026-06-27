"""Phase 3 — provenance taxonomy on the hierarchical metric stack.

Every numeric pillar input must disclose whether it is measured, a proxy, or an
assumed_constant fallback — so a dashboard can never show an assumed number as if
it were a live measurement. Mirrors OCAC's PROVED / PROOF-GAP / DEFINITION-GAP
honesty tagging.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from infrastructure.metrics_engine import hierarchical_metrics, _src, _PROVENANCE

# Diagnostic context keys that are not pillar *inputs* and so carry no source tag.
_CONTEXT_ONLY = {"score", "completed_tasks", "total_sessions", "mean_latency_ms"}


def test_src_helper_is_dynamic_and_honest():
    # cold start (no samples) is always assumed_constant, regardless of kind
    assert _src(0) == "assumed_constant"
    assert _src(0, kind="proxy") == "assumed_constant"
    assert _src(None) == "assumed_constant"
    # with data, the requested kind stands
    assert _src(5) == "measured"
    assert _src(5, kind="proxy") == "proxy"


def test_every_pillar_input_has_a_valid_source():
    h = hierarchical_metrics(force=True)
    assert set(h["provenance"]).issubset(set(_PROVENANCE))
    for name, layer in h["layers"].items():
        for key, val in layer.items():
            if key.endswith("_source"):
                assert val in _PROVENANCE, f"{name}.{key}={val!r} not in vocabulary"
                continue
            if key in _CONTEXT_ONLY:
                continue
            if isinstance(val, (int, float)):
                assert f"{key}_source" in layer, f"{name}.{key} missing provenance tag"


def test_provenance_summary_counts_match():
    h = hierarchical_metrics(force=True)
    counted = {k: 0 for k in _PROVENANCE}
    for layer in h["layers"].values():
        for key, val in layer.items():
            if key.endswith("_source"):
                counted[val] += 1
    assert h["provenance"] == counted
    # at least one tag exists, and the summary covers every source tag present
    assert sum(h["provenance"].values()) >= 1
