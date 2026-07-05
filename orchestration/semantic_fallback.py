"""
Semantic routing fallback — rescue for the `knowledge_learning` sink.

WHY
---
`adversarial_eval.py` (91 held-out, keyword-free prompts) showed the keyword
fast path scores 30.8% and dumps 81% of its misroutes into `knowledge_learning`
— the fallthrough bucket for "no keyword matched". `semantic_route_eval.py`
prototyped the fix: route by embedding k-NN to labelled exemplars from the
TRAINING set. Held-out results:

    keyword baseline   30.8%   (knowledge_learning sink = 51/63 misroutes)
    hybrid_fix         52.7%   (sink → 2/43)

This module is the productionised `hybrid_fix`. It is invoked ONLY where the
keyword/signal router would otherwise yield `knowledge_learning`, so confident
keyword routes and the factual/terse fast paths are never touched.

DESIGN CONSTRAINTS (mirror learned_router.py's contract)
--------------------------------------------------------
  * Never crashes think(). Every failure path returns None → caller keeps its
    existing behaviour.
  * OFF by default. Enable with AGENTIC_SEMANTIC_FALLBACK=1.
  * Exemplar embeddings are built once and cached to logs/; the hot path then
    costs a single embed() of the query plus an O(n) cosine scan (n=138).
  * If Ollama is unavailable, returns None (graceful, no exception surfaces).

Standalone:
    PYTHONPATH=. python3 orchestration/semantic_fallback.py            # build cache + self-test
    PYTHONPATH=. python3 orchestration/semantic_fallback.py --rebuild  # force re-embed
"""

import os
import sys
import json
import math
import time
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "logs", "semantic_exemplars.json"
)

# Similarity floor: below this, even the nearest exemplar is too far to trust,
# so we decline (return None) rather than force a low-quality route. Tunable via
# env; default 0.0 reproduces the prototype (always answer). Prod may raise it.
_MIN_SIM = float(os.getenv("AGENTIC_SEMANTIC_MIN_SIM", "0.0"))
_K = int(os.getenv("AGENTIC_SEMANTIC_K", "5"))

# Lazily-populated module singletons.
_EX_VECS: list[list[float]] | None = None
_EX_LABELS: list[str] | None = None
_PROVIDER = None
_DISABLED = False   # set True after an unrecoverable init failure (don't retry every call)


def is_enabled() -> bool:
    return os.getenv("AGENTIC_SEMANTIC_FALLBACK", "0") == "1"


# ── vector math ────────────────────────────────────────────────────────────
def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _exemplar_signature(pairs: list[tuple[str, str]], model: str) -> str:
    h = hashlib.sha1(model.encode())
    for label, text in pairs:
        h.update(label.encode())
        h.update(text.encode())
    return h.hexdigest()


def _exemplars() -> list[tuple[str, str]]:
    """(agent_label, text) from the training distribution — never the eval set."""
    from training.auto_train import PROMPTS
    return [(p[1], p[3]) for p in PROMPTS]


def _provider():
    """
    Embedding provider for the fallback. Backend chosen by AGENTIC_EMBED_BACKEND:
      ollama (default) — nomic-embed-text over Ollama's HTTP API (network round-trip)
      onnx             — local ONNX model, no network (see providers/onnx_embed.py)

    The exemplar cache is keyed by provider.model_id, so switching backends
    auto-invalidates the cache and rebuilds against the new vector space.
    """
    global _PROVIDER
    if _PROVIDER is None:
        backend = os.getenv("AGENTIC_EMBED_BACKEND", "ollama").lower()
        if backend == "onnx":
            from providers.onnx_embed import ONNXEmbeddingProvider
            _PROVIDER = ONNXEmbeddingProvider()
        else:
            from providers.ollama import OllamaEmbeddingProvider
            _PROVIDER = OllamaEmbeddingProvider()
    return _PROVIDER


def _build_index(rebuild: bool = False) -> bool:
    """
    Populate _EX_VECS / _EX_LABELS, from cache when the exemplar signature
    matches, otherwise by embedding every exemplar and writing the cache.
    Returns True on success. Never raises.
    """
    global _EX_VECS, _EX_LABELS, _DISABLED
    if _EX_VECS is not None and not rebuild:
        return True
    try:
        provider = _provider()
        pairs = _exemplars()
        sig = _exemplar_signature(pairs, provider.model_id)

        cached = None
        if not rebuild:
            try:
                with open(_CACHE_PATH) as fh:
                    blob = json.load(fh)
                if blob.get("signature") == sig:
                    cached = blob
            except (OSError, json.JSONDecodeError):
                cached = None

        if cached is not None:
            _EX_LABELS = cached["labels"]
            _EX_VECS = cached["vectors"]        # already unit-normalised on write
            return True

        labels = [lab for lab, _ in pairs]
        vecs = [_norm(provider.embed(text)) for _, text in pairs]
        _EX_LABELS, _EX_VECS = labels, vecs
        try:
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            with open(_CACHE_PATH, "w") as fh:
                json.dump({"signature": sig, "labels": labels, "vectors": vecs}, fh)
        except OSError:
            pass                                # cache write is best-effort
        return True
    except Exception as exc:                    # Ollama down, import error, etc.
        print(f"[semantic_fallback] index build failed ({exc}) → disabled for session")
        _DISABLED = True
        return False


def route(query: str) -> tuple[str, float] | None:
    """
    Return (agent, similarity) for the best semantic match, or None if the
    fallback is disabled, unavailable, or below the similarity floor.

    Crash-safe: any failure returns None so the caller keeps its behaviour.
    """
    if _DISABLED or not query or not query.strip():
        return None
    if not _build_index():
        return None
    try:
        qvec = _norm(_provider().embed(query))
        sims = sorted(
            ((sum(a * b for a, b in zip(qvec, ev)), lab)
             for ev, lab in zip(_EX_VECS, _EX_LABELS)),
            key=lambda t: -t[0],
        )
        top = sims[:_K]
        if not top or top[0][0] < _MIN_SIM:
            return None
        if _K == 1:
            return top[0][1], top[0][0]
        votes: dict = {}
        for rank, (_, lab) in enumerate(top):
            votes[lab] = votes.get(lab, 0.0) + 1.0 / (rank + 1)
        winner = max(votes.items(), key=lambda kv: kv[1])[0]
        best_sim = next(s for s, lab in top if lab == winner)
        return winner, best_sim
    except Exception as exc:
        print(f"[semantic_fallback] route failed ({exc}) → None")
        return None


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv
    t0 = time.time()
    ok = _build_index(rebuild=rebuild)
    print(f"index build: ok={ok}  ({len(_EX_LABELS or [])} exemplars, "
          f"{time.time() - t0:.1f}s, cache={_CACHE_PATH})")
    if ok:
        for q in [
            "My script silently stops halfway through a big loop and leaves no error.",
            "Clicking the button twice fast submits the form twice and creates duplicate orders.",
            "Why do people say you shouldn't store passwords the naive way?",
        ]:
            t = time.time()
            r = route(q)
            print(f"  {r}   ({1000*(time.time()-t):.0f}ms)   {q[:55]}")
