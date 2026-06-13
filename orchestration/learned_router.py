"""
Phase 27 — Tiny Learned Router

Trains a LogisticRegression classifier on the 312-trace dataset to predict
the correct agent from QuerySignal features + action.

Why:
  The rule-based signal router is 97% accurate but relies on fixed keyword
  sets and a DOMAIN_TO_AGENT table.  The learned router captures the joint
  distribution of (domain, shape, verbosity, action) → agent from observed
  decisions, including edge cases the keyword rules miss.

Usage in core_brain:
  - Runs alongside signal routing (never replaces it by itself)
  - If both agree  → +0.05 confidence boost
  - If they disagree AND learned_router confidence > 0.85 AND signal_conf < 0.50
    → learned_router wins (weak signal, strong model)
  - Model is re-trained automatically when a new trace JSONL is present

Standalone:
  python3 learned_router.py          # trains + shows accuracy + feature weights
  python3 learned_router.py --retrain  # forces full retrain
"""

import os
import sys
import json
import pickle
import hashlib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "learned_router.pkl")
_TRACE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "trace_dataset.jsonl")

# ── Feature vocabulary ────────────────────────────────────────
DOMAINS     = ["networking", "python", "blazor", "ai_ml", "general"]
SHAPES      = ["factual", "code", "debug", "procedural", "comparison", "explanation"]
VERBOSITIES = ["terse", "normal", "detailed"]
ACTIONS     = ["lookup", "debug", "build", "explain", "compare", "research", "plan", "unknown"]
AGENTS      = ["it_networking", "python_dev", "dotnet_dev", "ai_ml", "knowledge_learning", "terse"]

# Feature dimension: 5 + 1 + 6 + 3 + 8 = 23
N_FEATURES = len(DOMAINS) + 1 + len(SHAPES) + len(VERBOSITIES) + len(ACTIONS)


def _onehot(value: str, vocab: list) -> list:
    return [1 if v == value else 0 for v in vocab]


def extract_features(domain: str, domain_conf: float,
                     shape: str, verbosity: str, action: str) -> np.ndarray:
    """
    Convert a QuerySignal + action into a fixed-length feature vector.
    Pure function — no I/O, no model loading.
    """
    vec = (
        _onehot(domain, DOMAINS)
        + [round(float(domain_conf), 3)]
        + _onehot(shape, SHAPES)
        + _onehot(verbosity, VERBOSITIES)
        + _onehot(action, ACTIONS)
    )
    return np.array(vec, dtype=np.float32)


def _features_from_trace(t: dict) -> tuple[np.ndarray, str] | None:
    """Extract (feature_vector, agent_label) from one trace record."""
    sig    = t.get("signal", {})
    route  = t.get("routing", {})
    labels = t.get("labels", {})

    agent  = labels.get("correct_agent", route.get("final_agent", ""))
    if not agent or agent not in AGENTS:
        return None

    domain     = sig.get("domain", "general")
    domain_conf = float(sig.get("conf", 0.0))
    shape      = sig.get("shape", "explanation")
    verbosity  = sig.get("verbosity", "normal")
    action     = route.get("action", "unknown")

    return extract_features(domain, domain_conf, shape, verbosity, action), agent


def _load_traces() -> list:
    if not os.path.exists(_TRACE_PATH):
        return []
    traces = []
    with open(_TRACE_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return traces


def _trace_hash(traces: list) -> str:
    """Stable fingerprint of the trace list for cache invalidation."""
    raw = json.dumps([t.get("id") for t in traces], sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def train(traces: list = None, *, verbose: bool = False) -> dict:
    """
    Fit a LogisticRegression classifier and save to disk.

    Returns a stats dict with accuracy, class counts, and feature importances.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import LabelEncoder

    if traces is None:
        traces = _load_traces()

    rows = [_features_from_trace(t) for t in traces]
    rows = [r for r in rows if r is not None]
    if not rows:
        return {"error": "no usable traces"}

    X = np.vstack([r[0] for r in rows])
    y = np.array([r[1] for r in rows])

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    model = LogisticRegression(
        max_iter=1000,
        C=1.0,
        solver="lbfgs",
    )
    model.fit(X, y_enc)

    # 5-fold cross-validation accuracy
    cv_scores = cross_val_score(model, X, y_enc, cv=5, scoring="accuracy")
    cv_mean   = round(float(cv_scores.mean()), 4)
    cv_std    = round(float(cv_scores.std()), 4)

    # Train accuracy
    train_acc = round(float((model.predict(X) == y_enc).mean()), 4)

    # Class distribution
    unique, counts = np.unique(y, return_counts=True)
    class_counts   = {str(a): int(c) for a, c in zip(unique, counts)}

    # Feature importances (mean abs coef across classes)
    feat_names = (
        [f"dom_{d}" for d in DOMAINS]
        + ["domain_conf"]
        + [f"shp_{s}" for s in SHAPES]
        + [f"vrb_{v}" for v in VERBOSITIES]
        + [f"act_{a}" for a in ACTIONS]
    )
    mean_abs_coef = np.abs(model.coef_).mean(axis=0)
    top_features  = sorted(
        zip(feat_names, mean_abs_coef.tolist()),
        key=lambda x: -x[1]
    )[:10]

    payload = {
        "model":           model,
        "label_encoder":   le,
        "trace_hash":      _trace_hash(traces),
        "n_samples":       len(rows),
        "train_accuracy":  train_acc,
        "cv_accuracy":     cv_mean,
        "cv_std":          cv_std,
        "class_counts":    class_counts,
        "top_features":    [(n, round(v, 4)) for n, v in top_features],
    }

    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    with open(_MODEL_PATH, "wb") as f:
        pickle.dump(payload, f)

    if verbose:
        print(f"[learned_router] trained on {len(rows)} samples")
        print(f"  train_acc={train_acc:.3f}  cv={cv_mean:.3f}±{cv_std:.3f}")
        print(f"  class counts: {class_counts}")
        print(f"  top features: {[n for n, _ in top_features[:5]]}")

    return {k: v for k, v in payload.items() if k not in ("model", "label_encoder")}


# ── Module-level model cache ──────────────────────────────────
_cached_payload: dict | None = None


def _load_or_train() -> dict:
    """Return cached payload, load from disk, or train fresh."""
    global _cached_payload

    if _cached_payload is not None:
        return _cached_payload

    if os.path.exists(_MODEL_PATH):
        try:
            with open(_MODEL_PATH, "rb") as f:
                _cached_payload = pickle.load(f)
            return _cached_payload
        except Exception:
            pass

    # No model on disk → train now
    _cached_payload = train(verbose=False)
    # Inject model + encoder back into the dict if train succeeded
    if "model" not in _cached_payload:
        # train() strips model from the return dict for the stats API;
        # reload from disk to get the full payload
        try:
            with open(_MODEL_PATH, "rb") as f:
                _cached_payload = pickle.load(f)
        except Exception:
            pass

    return _cached_payload


def predict(domain: str, domain_conf: float,
            shape: str, verbosity: str, action: str) -> tuple[str, float]:
    """
    Predict the best agent and return (agent_name, confidence_prob).

    Returns ("knowledge_learning", 0.0) on any failure so callers never crash.
    """
    try:
        payload = _load_or_train()
        model   = payload.get("model")
        le      = payload.get("label_encoder")
        if model is None or le is None:
            return "knowledge_learning", 0.0

        x     = extract_features(domain, domain_conf, shape, verbosity, action).reshape(1, -1)
        proba = model.predict_proba(x)[0]
        idx   = int(np.argmax(proba))
        agent = le.inverse_transform([idx])[0]
        conf  = round(float(proba[idx]), 4)
        return agent, conf
    except Exception as e:
        print(f"[learned_router] predict error: {e}")
        return "knowledge_learning", 0.0


def stats() -> dict:
    """Return model stats without model/encoder objects (safe for JSON serialisation)."""
    payload = _load_or_train()
    return {k: v for k, v in payload.items() if k not in ("model", "label_encoder")}


def invalidate_cache():
    """Force reload from disk on next predict() call."""
    global _cached_payload
    _cached_payload = None


# ── Standalone entry point ───────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrain", action="store_true", help="force retrain even if model exists")
    args = parser.parse_args()

    if args.retrain and os.path.exists(_MODEL_PATH):
        os.remove(_MODEL_PATH)
        invalidate_cache()
        print("[learned_router] model cache cleared — retraining...")

    print("[learned_router] loading traces...")
    traces = _load_traces()
    print(f"  {len(traces)} traces loaded from {_TRACE_PATH}")

    print("\n[learned_router] training...")
    result = train(traces, verbose=True)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        sys.exit(1)

    print(f"\n  ✅ train_accuracy = {result['train_accuracy']:.1%}")
    print(f"     cv_accuracy    = {result['cv_accuracy']:.1%} ± {result['cv_std']:.3f}")
    print(f"     n_samples      = {result['n_samples']}")
    print(f"\n  Top features:")
    for name, weight in result["top_features"]:
        bar = "█" * int(weight * 20)
        print(f"    {name:<20} {bar} ({weight:.4f})")

    print(f"\n  Class distribution:")
    for agent, count in sorted(result["class_counts"].items(), key=lambda x: -x[1]):
        print(f"    {agent:<25} {count}")

    print("\n[learned_router] smoke test predictions:")
    tests = [
        ("networking", 0.70, "explanation", "normal", "explain", "it_networking"),
        ("python",     0.70, "code",        "normal", "build",   "python_dev"),
        ("blazor",     0.70, "code",        "normal", "build",   "dotnet_dev"),
        ("ai_ml",      0.70, "explanation", "normal", "explain", "ai_ml"),
        ("general",    0.00, "factual",     "terse",  "lookup",  "terse"),
        ("general",    0.00, "explanation", "terse",  "explain", "terse"),
    ]
    for domain, conf, shape, verb, action, expected in tests:
        agent, prob = predict(domain, conf, shape, verb, action)
        ok = "✓" if agent == expected else "✗"
        print(f"  {ok} ({domain},{shape},{verb},{action}) → {agent} ({prob:.2%})  [expected: {expected}]")
